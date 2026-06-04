"""Learning-state and eval-report helpers for Socrates v0.1."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from socrates.context import ProjectContext, read_json, write_json, write_text


@dataclass(frozen=True)
class MistakeRecord:
    """A mistake-bank entry and misconception update from one user attempt."""

    session_id: str
    concept: str
    misconception_id: str
    user_answer: str
    analysis: str
    repair_suggestion: str
    follow_up_exercises: list[str] = field(default_factory=list)
    status: str = "active"


@dataclass(frozen=True)
class LearningStatePatch:
    """Partial update for ``00_meta/learning_state.json``."""

    concept_mastery: dict[str, float] = field(default_factory=dict)
    proof_skills: dict[str, float] = field(default_factory=dict)
    mistakes: list[MistakeRecord] = field(default_factory=list)


@dataclass(frozen=True)
class EvalReportUpdate:
    """One checklist-style update for a v0.1 eval report."""

    report: str
    subject: str
    score: float
    summary: str
    strengths: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ReviewScheduleItem:
    """One review item derived from learning state."""

    concept: str
    priority: str
    due: str
    scheduled_for: str
    reason: str
    repair_context: tuple[dict[str, object], ...] = ()


@dataclass(frozen=True)
class MisconceptionSummary:
    """One persisted misconception state summary."""

    misconception_id: str
    status: str
    concept: str
    count: int
    last_session_id: str
    analysis: str
    repair_suggestion: str
    follow_up_exercises: tuple[str, ...]


@dataclass(frozen=True)
class LearningScoreSummary:
    """One concept or proof-skill score from learning state."""

    score_type: str
    item_id: str
    status: str
    score: float


EVAL_REPORTS = {
    "tutoring": ("tutoring_eval.md", "Tutoring Eval"),
    "exercise": ("exercise_eval.md", "Exercise Eval"),
    "note_quality": ("note_quality_eval.md", "Note Quality Eval"),
}


def update_learning_state(context: ProjectContext, patch: LearningStatePatch) -> None:
    """Merge learning-state scores and append any mistake-bank entries."""

    state = _learning_state_dict(context.learning_state)
    state["concept_mastery"].update(patch.concept_mastery)
    state["proof_skills"].update(patch.proof_skills)

    mistake_entries: list[str] = []
    for mistake in patch.mistakes:
        misconceptions = state["misconceptions"]
        existing = misconceptions.get(mistake.misconception_id, {})
        previous_count = int(existing.get("count", 0)) if isinstance(existing, dict) else 0
        misconceptions[mistake.misconception_id] = {
            "concept": mistake.concept,
            "count": previous_count + 1,
            "status": mistake.status,
            "last_session_id": mistake.session_id,
            "analysis": mistake.analysis,
            "repair_suggestion": mistake.repair_suggestion,
            "follow_up_exercises": list(mistake.follow_up_exercises),
        }
        mistake_entries.append(_mistake_bank_entry(mistake, is_recurrence=previous_count > 0))

    write_json(context.learning_state, state)
    if mistake_entries:
        _append_text(context.mistake_bank, "\n".join(mistake_entries))


def update_eval_report(context: ProjectContext, update: EvalReportUpdate) -> Path:
    """Append an update to one of the v0.1 eval report files."""

    if update.report not in EVAL_REPORTS:
        allowed = ", ".join(sorted(EVAL_REPORTS))
        raise ValueError(f"Unknown eval report {update.report!r}; expected one of: {allowed}")

    filename, title = EVAL_REPORTS[update.report]
    path = context.evals_dir / filename
    if not path.exists():
        write_text(path, f"# {title}\n\n")
    _append_text(path, _eval_report_entry(update))
    return path


def build_review_schedule(
    context: ProjectContext,
    *,
    mastery_threshold: float = 0.7,
    as_of: date | None = None,
) -> Path:
    """Build a first review schedule from weak concepts and active misconceptions."""

    state = _learning_state_dict(context.learning_state)
    items = _review_items(
        state,
        mastery_threshold=mastery_threshold,
        as_of=as_of or date.today(),
    )
    state["review_schedule"] = [_review_item_record(item) for item in items]
    write_json(context.learning_state, state)

    schedule_path = context.learning_plan_dir / "review_schedule.md"
    write_text(schedule_path, _review_schedule_markdown(items))
    return schedule_path


def repair_review_schedule(
    context: ProjectContext,
    *,
    as_of: date | None = None,
) -> tuple[int, Path]:
    """Repair missing or malformed scheduled review dates in persisted state."""

    state = _learning_state_dict(context.learning_state)
    repaired_count, items = _repaired_review_items(state, as_of=as_of or date.today())
    state["review_schedule"] = [_review_item_record(item) for item in items]
    write_json(context.learning_state, state)

    schedule_path = context.learning_plan_dir / "review_schedule.md"
    write_text(schedule_path, _review_schedule_markdown(items))
    return repaired_count, schedule_path


def resolve_active_misconceptions_for_concept(context: ProjectContext, concept: str) -> int:
    """Mark active misconception records for one concept as resolved."""

    state = _learning_state_dict(context.learning_state)
    misconceptions = state.get("misconceptions", {})
    if not isinstance(misconceptions, dict):
        return 0

    resolved_ids: list[str] = []
    for misconception_id, value in misconceptions.items():
        if not isinstance(value, dict):
            continue
        if str(value.get("concept", "")) != concept:
            continue
        if value.get("status", "active") != "active":
            continue
        value["status"] = "resolved"
        resolved_ids.append(str(misconception_id))

    if resolved_ids:
        write_json(context.learning_state, state)
        _append_text(context.mistake_bank, _resolution_entry(concept, resolved_ids))
    return len(resolved_ids)


def list_misconceptions(
    context: ProjectContext,
    *,
    status: str = "all",
) -> list[MisconceptionSummary]:
    """List persisted misconception states from the learning model."""

    allowed_statuses = {"all", "active", "resolved"}
    if status not in allowed_statuses:
        allowed = ", ".join(sorted(allowed_statuses))
        raise ValueError(
            f"Unknown misconception status {status!r}; expected one of: {allowed}"
        )

    state = _learning_state_dict(context.learning_state)
    misconceptions = state.get("misconceptions", {})
    if not isinstance(misconceptions, dict):
        return []

    summaries: list[MisconceptionSummary] = []
    for misconception_id, value in misconceptions.items():
        if not isinstance(value, dict):
            continue
        item_status = str(value.get("status", "active"))
        if status != "all" and item_status != status:
            continue
        summaries.append(
            MisconceptionSummary(
                misconception_id=str(misconception_id),
                status=item_status,
                concept=str(value.get("concept", "general")),
                count=_safe_count(value.get("count", 0)),
                last_session_id=str(value.get("last_session_id", "")),
                analysis=str(value.get("analysis", "")),
                repair_suggestion=str(value.get("repair_suggestion", "")),
                follow_up_exercises=tuple(
                    str(item)
                    for item in value.get("follow_up_exercises", [])
                    if str(item).strip()
                )
                if isinstance(value.get("follow_up_exercises"), list)
                else (),
            )
        )
    return sorted(
        summaries,
        key=lambda item: (
            _misconception_status_order(item.status),
            item.concept,
            item.misconception_id,
        ),
    )


def list_learning_scores(
    context: ProjectContext,
    *,
    score_type: str = "all",
    status: str = "all",
    threshold: float = 0.7,
) -> list[LearningScoreSummary]:
    """List concept mastery and proof-skill scores from learning state."""

    allowed_types = {"all", "concept", "proof_skill"}
    if score_type not in allowed_types:
        allowed = ", ".join(sorted(allowed_types))
        raise ValueError(f"Unknown score type {score_type!r}; expected one of: {allowed}")
    allowed_statuses = {"all", "weak", "ready"}
    if status not in allowed_statuses:
        allowed = ", ".join(sorted(allowed_statuses))
        raise ValueError(f"Unknown score status {status!r}; expected one of: {allowed}")

    state = _learning_state_dict(context.learning_state)
    summaries: list[LearningScoreSummary] = []
    if score_type in {"all", "concept"}:
        summaries.extend(
            _score_summaries(
                state.get("concept_mastery", {}),
                score_type="concept",
                threshold=threshold,
            )
        )
    if score_type in {"all", "proof_skill"}:
        summaries.extend(
            _score_summaries(
                state.get("proof_skills", {}),
                score_type="proof_skill",
                threshold=threshold,
            )
        )
    if status != "all":
        summaries = [item for item in summaries if item.status == status]
    return sorted(
        summaries,
        key=lambda item: (
            _score_status_order(item.status),
            _score_type_order(item.score_type),
            item.item_id,
        ),
    )


def _learning_state_dict(path: Path) -> dict[str, object]:
    loaded = read_json(path) if path.exists() else {}
    state = loaded if isinstance(loaded, dict) else {}
    for key in ("concept_mastery", "proof_skills", "misconceptions"):
        if not isinstance(state.get(key), dict):
            state[key] = {}
    if not isinstance(state.get("review_schedule"), list):
        state["review_schedule"] = []
    return state


def _review_items(
    state: dict[str, object],
    *,
    mastery_threshold: float,
    as_of: date,
) -> list[ReviewScheduleItem]:
    concept_reasons: dict[str, list[str]] = {}
    concept_priorities: dict[str, str] = {}
    concept_repair_context: dict[str, list[dict[str, object]]] = {}

    concept_mastery = state.get("concept_mastery", {})
    if isinstance(concept_mastery, dict):
        for concept, score_value in concept_mastery.items():
            score = _safe_score(score_value)
            if score >= mastery_threshold:
                continue
            concept_id = str(concept)
            concept_reasons.setdefault(concept_id, []).append(f"mastery {score:g}")
            concept_priorities[concept_id] = "high" if score < 0.5 else "medium"

    misconceptions = state.get("misconceptions", {})
    if isinstance(misconceptions, dict):
        for misconception_id, value in misconceptions.items():
            if not isinstance(value, dict):
                continue
            if value.get("status", "active") != "active":
                continue
            concept = str(value.get("concept", "general"))
            count = int(value.get("count", 1))
            concept_reasons.setdefault(concept, []).append(
                f"active misconception {misconception_id} x{count}"
            )
            concept_repair_context.setdefault(concept, []).append(
                _misconception_repair_context(misconception_id, value, count)
            )
            if count > 1 or concept_priorities.get(concept) != "high":
                concept_priorities[concept] = "high" if count > 1 else "medium"

    items: list[ReviewScheduleItem] = []
    for concept in sorted(concept_reasons):
        priority = concept_priorities.get(concept, "medium")
        due = "next_session" if priority == "high" else "within_3_days"
        items.append(
            ReviewScheduleItem(
                concept=concept,
                priority=priority,
                due=due,
                scheduled_for=_scheduled_review_date(priority, as_of),
                reason="; ".join(concept_reasons[concept]),
                repair_context=tuple(concept_repair_context.get(concept, [])),
            )
        )
    return sorted(items, key=lambda item: (item.scheduled_for, item.concept))


def _repaired_review_items(
    state: dict[str, object],
    *,
    as_of: date,
) -> tuple[int, list[ReviewScheduleItem]]:
    schedule = state.get("review_schedule", [])
    if not isinstance(schedule, list):
        return (0, [])

    repaired_count = 0
    items: list[ReviewScheduleItem] = []
    for raw_item in schedule:
        if not isinstance(raw_item, dict):
            continue
        item_repaired = False
        priority = str(raw_item.get("priority", "medium")).strip() or "medium"
        due = str(raw_item.get("due", "")).strip()
        if not due:
            due = "next_session" if priority == "high" else "within_3_days"
            item_repaired = True
        scheduled_for = str(raw_item.get("scheduled_for", "")).strip()
        if not _is_iso_date(scheduled_for):
            scheduled_for = _scheduled_review_date(priority, as_of)
            item_repaired = True
        if item_repaired:
            repaired_count += 1
        items.append(
            ReviewScheduleItem(
                concept=str(raw_item.get("concept", "review")),
                priority=priority,
                due=due,
                scheduled_for=scheduled_for,
                reason=str(raw_item.get("reason", "review scheduled")),
                repair_context=_repair_context_tuple(raw_item.get("repair_context", [])),
            )
        )
    return (
        repaired_count,
        sorted(items, key=lambda item: (item.scheduled_for, item.concept)),
    )


def _scheduled_review_date(priority: str, as_of: date) -> str:
    if priority == "high":
        return as_of.isoformat()
    return (as_of + timedelta(days=3)).isoformat()


def _is_iso_date(value: str) -> bool:
    if not value:
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _review_item_record(item: ReviewScheduleItem) -> dict[str, object]:
    record: dict[str, object] = {
        "concept": item.concept,
        "priority": item.priority,
        "due": item.due,
        "scheduled_for": item.scheduled_for,
        "reason": item.reason,
    }
    if item.repair_context:
        record["repair_context"] = [
            _repair_context_record(context) for context in item.repair_context
        ]
    return record


def _misconception_repair_context(
    misconception_id: object,
    value: dict[object, object],
    count: int,
) -> dict[str, object]:
    context: dict[str, object] = {
        "misconception_id": str(misconception_id),
        "count": count,
    }
    for source_key, target_key in (
        ("last_session_id", "last_session_id"),
        ("analysis", "analysis"),
        ("repair_suggestion", "repair_suggestion"),
    ):
        text = str(value.get(source_key, "")).strip()
        if text:
            context[target_key] = text
    follow_up_exercises = value.get("follow_up_exercises", [])
    if isinstance(follow_up_exercises, list):
        exercises = [str(item).strip() for item in follow_up_exercises if str(item).strip()]
        if exercises:
            context["follow_up_exercises"] = exercises
    return context


def _repair_context_tuple(value: object) -> tuple[dict[str, object], ...]:
    if not isinstance(value, list):
        return ()
    contexts: list[dict[str, object]] = []
    for raw_context in value:
        if not isinstance(raw_context, dict):
            continue
        misconception_id = str(raw_context.get("misconception_id", "")).strip()
        if not misconception_id:
            continue
        contexts.append(
            _misconception_repair_context(
                misconception_id,
                raw_context,
                _safe_count(raw_context.get("count", 1)) or 1,
            )
        )
    return tuple(contexts)


def _repair_context_record(context: dict[str, object]) -> dict[str, object]:
    record = dict(context)
    follow_up_exercises = record.get("follow_up_exercises", [])
    if isinstance(follow_up_exercises, tuple):
        record["follow_up_exercises"] = list(follow_up_exercises)
    return record


def _safe_count(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _misconception_status_order(status: str) -> int:
    return {"active": 0, "resolved": 1}.get(status, 2)


def _score_summaries(
    value: object,
    *,
    score_type: str,
    threshold: float,
) -> list[LearningScoreSummary]:
    if not isinstance(value, dict):
        return []
    summaries: list[LearningScoreSummary] = []
    for item_id, raw_score in value.items():
        score = _safe_score(raw_score)
        summaries.append(
            LearningScoreSummary(
                score_type=score_type,
                item_id=str(item_id),
                status="weak" if score < threshold else "ready",
                score=score,
            )
        )
    return summaries


def _safe_score(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _score_status_order(status: str) -> int:
    return {"weak": 0, "ready": 1}.get(status, 2)


def _score_type_order(score_type: str) -> int:
    return {"concept": 0, "proof_skill": 1}.get(score_type, 2)


def _review_schedule_markdown(items: list[ReviewScheduleItem]) -> str:
    lines = ["# Review Schedule", ""]
    if not items:
        lines.append("No review items scheduled.")
        return "\n".join(lines) + "\n"
    for item in items:
        lines.extend(
            [
                f"## {item.concept}",
                "",
                f"- Priority: {item.priority}",
                f"- Due: {item.due}",
                f"- Scheduled for: {item.scheduled_for}",
                f"- Reason: {item.reason}",
                "",
            ]
        )
        if item.repair_context:
            lines.extend(["### Repair Context", ""])
            for context in item.repair_context:
                misconception_id = str(context.get("misconception_id", "")).strip()
                count = _safe_count(context.get("count", 1)) or 1
                if not misconception_id:
                    continue
                lines.append(f"- Misconception: {misconception_id} (x{count})")
                last_session_id = str(context.get("last_session_id", "")).strip()
                if last_session_id:
                    lines.append(f"  - Last session: {last_session_id}")
                analysis = str(context.get("analysis", "")).strip()
                if analysis:
                    lines.append(f"  - Analysis: {analysis}")
                repair_suggestion = str(context.get("repair_suggestion", "")).strip()
                if repair_suggestion:
                    lines.append(f"  - Repair suggestion: {repair_suggestion}")
                follow_up_exercises = context.get("follow_up_exercises", [])
                if isinstance(follow_up_exercises, list) and follow_up_exercises:
                    lines.append(
                        "  - Follow-up exercises: "
                        + ", ".join(str(item) for item in follow_up_exercises)
                    )
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _mistake_bank_entry(mistake: MistakeRecord, *, is_recurrence: bool) -> str:
    lines = [
        f"## {mistake.session_id} - {mistake.concept}",
        "",
        f"- Misconception: {mistake.misconception_id}",
        f"- User answer: {mistake.user_answer}",
        f"- Analysis: {mistake.analysis}",
        f"- Repair suggestion: {mistake.repair_suggestion}",
        f"- Recurrence: {'yes' if is_recurrence else 'no'}",
    ]
    if mistake.follow_up_exercises:
        lines.append("- Follow-up exercises:")
        lines.extend(f"  - {exercise}" for exercise in mistake.follow_up_exercises)
    else:
        lines.append("- Follow-up exercises: none recorded")
    return "\n".join(lines) + "\n"


def _resolution_entry(concept: str, misconception_ids: list[str]) -> str:
    lines = [f"## resolved - {concept}", ""]
    for misconception_id in misconception_ids:
        lines.extend(
            [
                f"- Misconception: {misconception_id}",
                "- Status: resolved",
            ]
        )
    return "\n".join(lines) + "\n"


def _eval_report_entry(update: EvalReportUpdate) -> str:
    lines = [
        f"## {update.subject}",
        "",
        f"- Score: {update.score:g}",
        f"- Summary: {update.summary}",
        "",
        "### Strengths",
        *_bullet_list(update.strengths),
        "",
        "### Issues",
        *_bullet_list(update.issues),
        "",
        "### Next Actions",
        *_bullet_list(update.next_actions),
    ]
    return "\n".join(lines) + "\n"


def _bullet_list(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items] or ["- none recorded"]


def _append_text(path: Path, content: str) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    new_content = existing.rstrip() + "\n\n" + content.rstrip() + "\n"
    write_text(path, new_content)
