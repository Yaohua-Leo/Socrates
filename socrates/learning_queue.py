"""Actionable queue summaries for ongoing learning projects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .context import load_project, read_json
from .project import slugify_topic


@dataclass(frozen=True)
class QueueItem:
    """One actionable project artifact."""

    item_id: str
    path: str
    detail: str = ""


@dataclass(frozen=True)
class LearningQueue:
    """Actionable artifact groups for CLI queue display."""

    notes_to_review: list[QueueItem]
    misconception_notes_to_draft: list[QueueItem]
    scheduled_reviews: list[QueueItem]
    exercise_drafts_to_approve: list[QueueItem]
    exercises_to_attempt: list[QueueItem]
    attempts_to_grade: list[QueueItem]
    tool_verifications_to_fix: list[QueueItem]


def collect_learning_queue(project_path: Path | str) -> LearningQueue:
    """Collect notes and exercises that need the next learner or reviewer action."""

    context = load_project(project_path)
    return LearningQueue(
        notes_to_review=_notes_to_review(context.root),
        misconception_notes_to_draft=_misconception_notes_to_draft(context.root),
        scheduled_reviews=_scheduled_reviews(context.root),
        exercise_drafts_to_approve=_exercise_drafts_to_approve(context.root),
        exercises_to_attempt=_exercises_to_attempt(context.root),
        attempts_to_grade=_attempts_to_grade(context.root),
        tool_verifications_to_fix=_tool_verifications_to_fix(context.root),
    )


def format_learning_queue(queue: LearningQueue) -> str:
    """Render a stable CLI queue summary."""

    lines = ["# Learning Queue", ""]
    lines.extend(_section("Notes To Review", queue.notes_to_review))
    lines.extend(
        _section("Misconception Notes To Draft", queue.misconception_notes_to_draft)
    )
    lines.extend(_section("Scheduled Reviews", queue.scheduled_reviews))
    lines.extend(_section("Exercise Drafts To Approve", queue.exercise_drafts_to_approve))
    lines.extend(_section("Exercises To Attempt", queue.exercises_to_attempt))
    lines.extend(_section("Attempts To Grade", queue.attempts_to_grade))
    lines.extend(_section("Tool Verifications To Fix", queue.tool_verifications_to_fix))
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


def _misconception_notes_to_draft(project_root: Path) -> list[QueueItem]:
    learning_state = project_root / "00_meta" / "learning_state.json"
    if not learning_state.exists():
        return []
    state = read_json(learning_state)
    if not isinstance(state, dict):
        return []
    misconceptions = state.get("misconceptions", {})
    if not isinstance(misconceptions, dict):
        return []

    covered_ids = _covered_note_ids(project_root)
    items: list[QueueItem] = []
    for misconception_id, value in sorted(
        misconceptions.items(),
        key=lambda item: str(item[0]),
    ):
        if not isinstance(value, dict):
            continue
        note_id = slugify_topic(str(misconception_id))
        if note_id in covered_ids:
            continue
        concept = str(value.get("concept", "general"))
        status = str(value.get("status", "active"))
        items.append(
            QueueItem(
                item_id=note_id,
                path=learning_state.relative_to(project_root).as_posix(),
                detail=(
                    f"concept: {concept}; status: {status}; "
                    "draft with: socrates note draft-misconceptions --status all"
                ),
            )
        )
    return items


def _covered_note_ids(project_root: Path) -> set[str]:
    covered = set(_reviewed_note_ids(project_root))
    draft_dir = project_root / "04_atomic_notes" / "drafts"
    if draft_dir.exists():
        covered.update(path.stem for path in draft_dir.glob("*.md"))
    return covered


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
    for item in sorted(schedule, key=_scheduled_review_sort_key):
        if not isinstance(item, dict):
            continue
        concept = str(item.get("concept", "review"))
        items.append(
            QueueItem(
                item_id=concept,
                path=schedule_path.relative_to(project_root).as_posix(),
                detail=_scheduled_review_detail(item),
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


def _tool_verifications_to_fix(project_root: Path) -> list[QueueItem]:
    manifest_path = project_root / "08_evals" / "tool_verification_quality_manifest.json"
    if not manifest_path.exists():
        return []
    manifest = read_json(manifest_path)
    if not isinstance(manifest, dict):
        return []
    records = manifest.get("records", [])
    if not isinstance(records, list):
        return []

    report_path = project_root / "08_evals" / "tool_verification_eval.md"
    queue_path = report_path if report_path.exists() else manifest_path
    items: list[QueueItem] = []
    manifest_issues = _tool_verification_issue_items(manifest.get("issues", []))
    if manifest_issues:
        items.append(
            QueueItem(
                item_id="tool_verification_manifest",
                path=queue_path.relative_to(project_root).as_posix(),
                detail=(
                    "quality: fail; "
                    f"issues: {_tool_verification_issue_text(manifest_issues)}; "
                    "rerun with: socrates tool check --project <project>"
                ),
            )
        )
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            continue
        if str(record.get("quality_status", "")).strip() != "fail":
            continue
        object_id = str(record.get("object_id") or f"record_{index}")
        record_status = str(record.get("record_status") or "unknown")
        issues = _tool_verification_issue_text(
            _tool_verification_issue_items(record.get("issues", []))
        )
        detail = (
            f"quality: fail; status: {record_status}; "
            f"issues: {issues}; "
            "rerun with: socrates tool check --project <project>"
        )
        items.append(
            QueueItem(
                item_id=object_id,
                path=queue_path.relative_to(project_root).as_posix(),
                detail=detail,
            )
        )
    return items


def _tool_verification_issue_items(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(issue).strip() for issue in value if str(issue).strip()]


def _tool_verification_issue_text(issues: list[str]) -> str:
    if not issues:
        return "none recorded"
    return "; ".join(issues)


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


def _scheduled_review_detail(item: dict[str, object]) -> str:
    details: list[str] = []
    scheduled_for = str(item.get("scheduled_for", "")).strip()
    if scheduled_for:
        details.append(f"scheduled for {scheduled_for}")
    reason = str(item.get("reason", "")).strip()
    if reason:
        details.append(f"reason: {reason}")
    repair_suggestions = _scheduled_repair_suggestions(item.get("repair_context", []))
    if repair_suggestions:
        details.append(f"repair: {'; '.join(repair_suggestions)}")
    return "; ".join(details)


def _scheduled_repair_suggestions(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    suggestions: list[str] = []
    seen: set[str] = set()
    for raw_context in value:
        if not isinstance(raw_context, dict):
            continue
        suggestion = str(raw_context.get("repair_suggestion", "")).strip()
        if not suggestion or suggestion in seen:
            continue
        seen.add(suggestion)
        suggestions.append(suggestion)
    return suggestions


def _scheduled_review_sort_key(item: object) -> tuple[str, str]:
    if not isinstance(item, dict):
        return ("9999-99-99", "")
    return (
        str(item.get("scheduled_for", "9999-99-99")),
        str(item.get("concept", "review")),
    )


def _section(title: str, items: list[QueueItem]) -> list[str]:
    lines = [f"## {title}", ""]
    if not items:
        lines.extend(["- none", ""])
        return lines
    lines.extend(_queue_line(item) for item in items)
    lines.append("")
    return lines


def _queue_line(item: QueueItem) -> str:
    line = f"- {item.item_id} | {item.path}"
    if item.detail:
        line = f"{line} | {item.detail}"
    return line
