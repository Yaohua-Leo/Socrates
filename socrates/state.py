"""Learning-state and eval-report helpers for Socrates v0.1."""

from __future__ import annotations

from dataclasses import dataclass, field
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


def _learning_state_dict(path: Path) -> dict[str, object]:
    loaded = read_json(path) if path.exists() else {}
    state = loaded if isinstance(loaded, dict) else {}
    for key in ("concept_mastery", "proof_skills", "misconceptions"):
        if not isinstance(state.get(key), dict):
            state[key] = {}
    return state


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
