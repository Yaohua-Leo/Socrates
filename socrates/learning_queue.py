"""Actionable queue summaries for ongoing learning projects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .context import load_project, read_json


@dataclass(frozen=True)
class QueueItem:
    """One actionable project artifact."""

    item_id: str
    path: str


@dataclass(frozen=True)
class LearningQueue:
    """Actionable artifact groups for CLI queue display."""

    notes_to_review: list[QueueItem]
    scheduled_reviews: list[QueueItem]
    exercise_drafts_to_approve: list[QueueItem]
    exercises_to_attempt: list[QueueItem]
    attempts_to_grade: list[QueueItem]


def collect_learning_queue(project_path: Path | str) -> LearningQueue:
    """Collect notes and exercises that need the next learner or reviewer action."""

    context = load_project(project_path)
    return LearningQueue(
        notes_to_review=_notes_to_review(context.root),
        scheduled_reviews=_scheduled_reviews(context.root),
        exercise_drafts_to_approve=_exercise_drafts_to_approve(context.root),
        exercises_to_attempt=_exercises_to_attempt(context.root),
        attempts_to_grade=_attempts_to_grade(context.root),
    )


def format_learning_queue(queue: LearningQueue) -> str:
    """Render a stable CLI queue summary."""

    lines = ["# Learning Queue", ""]
    lines.extend(_section("Notes To Review", queue.notes_to_review))
    lines.extend(_section("Scheduled Reviews", queue.scheduled_reviews))
    lines.extend(_section("Exercise Drafts To Approve", queue.exercise_drafts_to_approve))
    lines.extend(_section("Exercises To Attempt", queue.exercises_to_attempt))
    lines.extend(_section("Attempts To Grade", queue.attempts_to_grade))
    return "\n".join(lines).rstrip() + "\n"


def _notes_to_review(project_root: Path) -> list[QueueItem]:
    draft_dir = project_root / "04_atomic_notes" / "drafts"
    if not draft_dir.exists():
        return []
    reviewed_ids = _reviewed_note_ids(project_root)
    items: list[QueueItem] = []
    for draft_path in sorted(draft_dir.glob("*.md"), key=lambda path: path.stem):
        if draft_path.stem in reviewed_ids:
            continue
        items.append(_queue_item(draft_path, project_root))
    return items


def _reviewed_note_ids(project_root: Path) -> set[str]:
    notes_root = project_root / "04_atomic_notes"
    reviewed: set[str] = set()
    if not notes_root.exists():
        return reviewed
    for folder in sorted(notes_root.iterdir(), key=lambda path: path.name):
        if not folder.is_dir() or folder.name == "drafts":
            continue
        for note_path in folder.glob("*.md"):
            text = note_path.read_text(encoding="utf-8")
            if _frontmatter_value(text, "reviewed_by_user") == "true":
                reviewed.add(note_path.stem)
    return reviewed


def _exercise_drafts_to_approve(project_root: Path) -> list[QueueItem]:
    generated_dir = project_root / "05_exercises" / "generated"
    if not generated_dir.exists():
        return []
    items: list[QueueItem] = []
    for exercise_path in sorted(generated_dir.glob("*.md"), key=lambda path: path.stem):
        text = exercise_path.read_text(encoding="utf-8")
        if _is_approved_exercise(text):
            continue
        items.append(_queue_item(exercise_path, project_root))
    return items


def _scheduled_reviews(project_root: Path) -> list[QueueItem]:
    learning_state = project_root / "00_meta" / "learning_state.json"
    schedule_path = project_root / "02_learning_plan" / "review_schedule.md"
    if not learning_state.exists():
        return []
    state = read_json(learning_state)
    if not isinstance(state, dict):
        return []
    schedule = state.get("review_schedule", [])
    if not isinstance(schedule, list):
        return []
    items: list[QueueItem] = []
    for item in schedule:
        if not isinstance(item, dict):
            continue
        concept = str(item.get("concept", "review"))
        items.append(
            QueueItem(
                item_id=concept,
                path=schedule_path.relative_to(project_root).as_posix(),
            )
        )
    return items


def _exercises_to_attempt(project_root: Path) -> list[QueueItem]:
    generated_dir = project_root / "05_exercises" / "generated"
    if not generated_dir.exists():
        return []
    attempted_ids = _attempted_exercise_ids(project_root)
    items: list[QueueItem] = []
    for exercise_path in sorted(generated_dir.glob("*.md"), key=lambda path: path.stem):
        if not _is_approved_exercise(exercise_path.read_text(encoding="utf-8")):
            continue
        if exercise_path.stem in attempted_ids:
            continue
        items.append(_queue_item(exercise_path, project_root))
    return items


def _attempted_exercise_ids(project_root: Path) -> set[str]:
    attempted_dir = project_root / "05_exercises" / "attempted"
    attempted: set[str] = set()
    if not attempted_dir.exists():
        return attempted
    for attempt_path in attempted_dir.glob("*.md"):
        text = attempt_path.read_text(encoding="utf-8")
        exercise_id = (
            _frontmatter_value(text, "exercise_id")
            or _exercise_id_from_attempt(attempt_path.stem)
        )
        attempted.add(exercise_id)
    return attempted


def _attempts_to_grade(project_root: Path) -> list[QueueItem]:
    attempted_dir = project_root / "05_exercises" / "attempted"
    if not attempted_dir.exists():
        return []
    graded_attempts = _graded_attempt_ids(project_root)
    items: list[QueueItem] = []
    for attempt_path in sorted(attempted_dir.glob("*.md"), key=lambda path: path.stem):
        if attempt_path.stem in graded_attempts:
            continue
        items.append(_queue_item(attempt_path, project_root))
    return items


def _graded_attempt_ids(project_root: Path) -> set[str]:
    graded_dir = project_root / "05_exercises" / "graded"
    graded: set[str] = set()
    if not graded_dir.exists():
        return graded
    for grade_path in graded_dir.glob("*.md"):
        text = grade_path.read_text(encoding="utf-8")
        attempt_id = _frontmatter_value(text, "attempt_id") or grade_path.stem.removesuffix("_grade")
        graded.add(attempt_id)
    return graded


def _is_approved_exercise(text: str) -> bool:
    return (
        _frontmatter_value(text, "status") == "approved"
        and _frontmatter_value(text, "reviewed_by_user") == "true"
    )


def _frontmatter_value(text: str, key: str) -> str | None:
    if not text.startswith("---\n"):
        return None
    parts = text.split("---\n", 2)
    if len(parts) != 3:
        return None
    prefix = f"{key}:"
    for line in parts[1].splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip().strip('"')
    return None


def _exercise_id_from_attempt(attempt_id: str) -> str:
    marker = "_attempt_"
    if marker not in attempt_id:
        return attempt_id
    return attempt_id.split(marker, 1)[0]


def _queue_item(path: Path, project_root: Path) -> QueueItem:
    return QueueItem(
        item_id=path.stem,
        path=path.relative_to(project_root).as_posix(),
    )


def _section(title: str, items: list[QueueItem]) -> list[str]:
    lines = [f"## {title}", ""]
    if not items:
        lines.extend(["- none", ""])
        return lines
    lines.extend(f"- {item.item_id} | {item.path}" for item in items)
    lines.append("")
    return lines
