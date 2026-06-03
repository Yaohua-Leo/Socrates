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
    state["review_schedule"] = [
        {
            "concept": item.concept,
            "priority": item.priority,
            "due": item.due,
            "scheduled_for": item.scheduled_for,
            "reason": item.reason,
        }
        for item in items
    ]
    write_json(context.learning_state, state)

    schedule_path = context.learning_plan_dir / "review_schedule.md"
    write_text(schedule_path, _review_schedule_markdown(items))
    return schedule_path


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

    concept_mastery = state.get("concept_mastery", {})
    if isinstance(concept_mastery, dict):
        for concept, score_value in concept_mastery.items():
            score = float(score_value)
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
            )
        )
    return sorted(items, key=lambda item: (item.scheduled_for, item.concept))


def _scheduled_review_date(priority: str, as_of: date) -> str:
    if priority == "high":
        return as_of.isoformat()
    return (as_of + timedelta(days=3)).isoformat()


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
