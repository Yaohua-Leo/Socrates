"""Learning report generation for Socrates projects."""

from __future__ import annotations

import json
from pathlib import Path

from .context import append_project_log, load_project, write_text


def generate_weekly_report(project_path: Path | str) -> Path:
    """Write a compact weekly report from persisted project artifacts."""

    context = load_project(project_path)
    report_path = context.root / "07_exports" / "reports" / "weekly_report.md"
    state = _read_learning_state(context.learning_state)
    write_text(
        report_path,
        _weekly_report_text(
            sessions_completed=_count_dirs(context.sessions_dir),
            reviewed_notes=_count_reviewed_notes(context.root),
            generated_exercises=_count_markdown(context.generated_exercises_dir),
            attempted_exercises=_count_markdown(context.root / "05_exercises" / "attempted"),
            graded_exercises=_count_markdown(context.root / "05_exercises" / "graded"),
            state=state,
        ),
    )
    append_project_log(context, "Generated weekly learning report.")
    return report_path


def _weekly_report_text(
    *,
    sessions_completed: int,
    reviewed_notes: int,
    generated_exercises: int,
    attempted_exercises: int,
    graded_exercises: int,
    state: dict[str, object],
) -> str:
    lines = [
        "# Weekly Learning Report",
        "",
        "## Activity",
        "",
        f"- Sessions completed: {sessions_completed}",
        f"- Reviewed notes: {reviewed_notes}",
        f"- Generated exercises: {generated_exercises}",
        f"- Attempted exercises: {attempted_exercises}",
        f"- Graded exercises: {graded_exercises}",
        "",
        "## Learning State",
        "",
        *_score_lines(state.get("concept_mastery", {})),
        "",
        "## Proof Skills",
        "",
        *_score_lines(state.get("proof_skills", {})),
        "",
        "## Scheduled Review",
        "",
        *_review_lines(state.get("review_schedule", [])),
    ]
    return "\n".join(lines).rstrip() + "\n"


def _read_learning_state(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def _count_dirs(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for item in path.iterdir() if item.is_dir())


def _count_markdown(path: Path) -> int:
    if not path.exists():
        return 0
    return len(list(path.glob("*.md")))


def _count_reviewed_notes(project_root: Path) -> int:
    notes_root = project_root / "04_atomic_notes"
    if not notes_root.exists():
        return 0
    reviewed = 0
    for folder in notes_root.iterdir():
        if not folder.is_dir() or folder.name == "drafts":
            continue
        for note_path in folder.glob("*.md"):
            if "reviewed_by_user: true" in note_path.read_text(encoding="utf-8"):
                reviewed += 1
    return reviewed


def _score_lines(value: object) -> list[str]:
    if not isinstance(value, dict) or not value:
        return ["- none recorded"]
    return [f"- {key}: {float(score):g}" for key, score in sorted(value.items())]


def _review_lines(value: object) -> list[str]:
    if not isinstance(value, list) or not value:
        return ["- none scheduled"]
    lines: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        concept = str(item.get("concept", "review"))
        priority = str(item.get("priority", "medium"))
        due = str(item.get("due", "within_3_days"))
        reason = str(item.get("reason", "review scheduled"))
        lines.append(f"- {concept}: {priority}, {due} - {reason}")
    return lines or ["- none scheduled"]
