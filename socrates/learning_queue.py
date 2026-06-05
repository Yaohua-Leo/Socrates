"""Actionable queue summaries for ongoing learning projects."""

from __future__ import annotations

from dataclasses import dataclass
from json import JSONDecodeError
from pathlib import Path

from .context import load_project, project_title, read_json
from .multi_session import (
    MULTI_SESSION_REGRESSION_MANIFEST_PATH,
    read_multi_session_regression_status,
)
from .obsidian import obsidian_exported_note_ids
from .project import slugify_topic
from .workflow_manifest import SESSION_CLOSEOUT_MANIFEST_PATH, read_session_closeout_status


QUEUE_SECTIONS = frozenset(
    {
        "summary",
        "repairs",
        "priority",
        "notes",
        "obsidian-exports",
        "misconceptions",
        "reviews",
        "exercise-drafts",
        "exercises",
        "attempts",
        "quality-checks",
        "tool-verifications",
        "workflow",
    }
)
QUEUE_QUALITY_BOUNDARY = "deterministic_learning_queue"


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
    obsidian_exports_to_run: list[QueueItem]
    misconception_notes_to_draft: list[QueueItem]
    scheduled_reviews: list[QueueItem]
    exercise_drafts_to_approve: list[QueueItem]
    exercises_to_attempt: list[QueueItem]
    attempts_to_grade: list[QueueItem]
    workflow_actions: list[QueueItem]
    quality_checks_to_fix: list[QueueItem]
    tool_verifications_to_fix: list[QueueItem]


def collect_learning_queue(project_path: Path | str) -> LearningQueue:
    """Collect notes and exercises that need the next learner or reviewer action."""

    context = load_project(project_path)
    return LearningQueue(
        notes_to_review=_notes_to_review(context.root),
        obsidian_exports_to_run=_obsidian_exports_to_run(context.root),
        misconception_notes_to_draft=_misconception_notes_to_draft(context.root),
        scheduled_reviews=_scheduled_reviews(context.root),
        exercise_drafts_to_approve=_exercise_drafts_to_approve(context.root),
        exercises_to_attempt=_exercises_to_attempt(context.root),
        attempts_to_grade=_attempts_to_grade(context.root),
        workflow_actions=_workflow_actions(context.root),
        quality_checks_to_fix=_artifact_quality_checks_to_fix(context.root),
        tool_verifications_to_fix=_tool_verifications_to_fix(context.root),
    )


def build_learning_queue_payload(
    project_path: Path | str,
    *,
    section: str = "all",
) -> dict[str, object]:
    """Build the machine-readable read-only queue payload."""

    _validate_queue_section(section)
    context = load_project(project_path)
    queue = collect_learning_queue(context.root)
    return {
        "schema_version": 1,
        "quality_boundary": QUEUE_QUALITY_BOUNDARY,
        "project": project_title(context.project_file, fallback=context.root.name),
        "root": str(context.root),
        "section": section,
        "action_summary": action_summary_record(queue),
        "sections": [_section_record(row) for row in _selected_queue_sections(queue, section)],
    }


def format_learning_queue(queue: LearningQueue, *, section: str = "all") -> str:
    """Render a stable CLI queue summary."""

    _validate_queue_section(section)

    lines = ["# Learning Queue", ""]
    if section in {"all", "summary"}:
        lines.extend(["## Action Summary", ""])
        lines.extend(action_summary_lines(queue))
        lines.append("")
        if section == "summary":
            return "\n".join(lines).rstrip() + "\n"

    if section in {"all", "repairs"}:
        lines.extend(_section("Repair Paths", repair_path_items(queue)))
        if section == "repairs":
            return "\n".join(lines).rstrip() + "\n"

    for section_id, title, items in _queue_sections(queue):
        if section != "all" and section != section_id:
            continue
        lines.extend(_section(title, items))
    return "\n".join(lines).rstrip() + "\n"


def _queue_sections(queue: LearningQueue) -> list[tuple[str, str, list[QueueItem]]]:
    return [
        ("priority", "Priority Actions", priority_queue_items(queue)),
        ("notes", "Notes To Review", queue.notes_to_review),
        ("obsidian-exports", "Obsidian Exports To Run", queue.obsidian_exports_to_run),
        ("misconceptions", "Misconception Notes To Draft", queue.misconception_notes_to_draft),
        ("reviews", "Scheduled Reviews", queue.scheduled_reviews),
        ("exercise-drafts", "Exercise Drafts To Approve", queue.exercise_drafts_to_approve),
        ("exercises", "Exercises To Attempt", queue.exercises_to_attempt),
        ("attempts", "Attempts To Grade", queue.attempts_to_grade),
        ("workflow", "Workflow Actions", queue.workflow_actions),
        ("quality-checks", "Quality Checks To Fix", queue.quality_checks_to_fix),
        ("tool-verifications", "Tool Verifications To Fix", queue.tool_verifications_to_fix),
    ]


def repair_path_items(queue: LearningQueue) -> list[QueueItem]:
    """Return blocker queue items in deterministic repair order."""

    return _prefixed_queue_items(
        (
            ("workflow", queue.workflow_actions),
            ("quality-checks", queue.quality_checks_to_fix),
            ("tool-verifications", queue.tool_verifications_to_fix),
        )
    )


def action_summary_lines(queue: LearningQueue) -> list[str]:
    """Return completion/blocker rows derived from existing queue buckets."""

    summary = action_summary_record(queue)
    return [
        f"- Completion: {summary['completion']}",
        f"- Open actions: {summary['open_actions']}",
        f"- Blockers: {summary['blockers']}",
        f"- Can continue learning: {summary['can_continue_learning']}",
        f"- Needs human review: {summary['needs_human_review']}",
        f"- Next action: {summary['next_action']}",
    ]


def action_summary_record(queue: LearningQueue) -> dict[str, object]:
    """Return structured completion/blocker fields from existing queue buckets."""

    blockers = (
        len(queue.workflow_actions)
        + len(queue.quality_checks_to_fix)
        + len(queue.tool_verifications_to_fix)
    )
    can_continue = len(queue.scheduled_reviews) + len(queue.exercises_to_attempt)
    human_review = (
        len(queue.obsidian_exports_to_run)
        + len(queue.notes_to_review)
        + len(queue.misconception_notes_to_draft)
        + len(queue.exercise_drafts_to_approve)
        + len(queue.attempts_to_grade)
    )
    open_actions = blockers + can_continue + human_review
    completion = "clear" if open_actions == 0 else "blocked" if blockers else "in_progress"
    next_actions = priority_queue_items(queue)
    next_action = "none"
    if next_actions:
        next_action = _queue_line(next_actions[0]).removeprefix("- ")
    return {
        "completion": completion,
        "open_actions": open_actions,
        "blockers": blockers,
        "can_continue_learning": can_continue,
        "needs_human_review": human_review,
        "next_action": next_action,
    }


def priority_queue_items(queue: LearningQueue) -> list[QueueItem]:
    """Return existing queue items in deterministic operator priority order."""

    return _priority_actions(queue)


def _priority_actions(queue: LearningQueue) -> list[QueueItem]:
    ordered_sections = (
        ("workflow", queue.workflow_actions),
        ("quality-checks", queue.quality_checks_to_fix),
        ("tool-verifications", queue.tool_verifications_to_fix),
        ("obsidian-exports", queue.obsidian_exports_to_run),
        ("notes", queue.notes_to_review),
        ("misconceptions", queue.misconception_notes_to_draft),
        ("reviews", queue.scheduled_reviews),
        ("exercise-drafts", queue.exercise_drafts_to_approve),
        ("exercises", queue.exercises_to_attempt),
        ("attempts", queue.attempts_to_grade),
    )
    return _prefixed_queue_items(ordered_sections)


def _prefixed_queue_items(
    ordered_sections: tuple[tuple[str, list[QueueItem]], ...],
) -> list[QueueItem]:
    actions: list[QueueItem] = []
    for section_id, items in ordered_sections:
        actions.extend(
            QueueItem(
                item_id=f"{section_id}:{item.item_id}",
                path=item.path,
                detail=item.detail,
            )
            for item in items
        )
    return actions


def _validate_queue_section(section: str) -> None:
    if section != "all" and section not in QUEUE_SECTIONS:
        allowed = ", ".join(sorted({"all", *QUEUE_SECTIONS}))
        raise ValueError(f"Unknown queue section {section!r}; expected one of: {allowed}")


def _selected_queue_sections(
    queue: LearningQueue,
    section: str,
) -> list[tuple[str, str, list[QueueItem]]]:
    repair_paths = ("repairs", "Repair Paths", repair_path_items(queue))
    if section == "summary":
        return []
    if section == "repairs":
        return [repair_paths]
    sections = _queue_sections(queue)
    if section == "all":
        return [repair_paths, *sections]
    return [row for row in sections if row[0] == section]


def _section_record(row: tuple[str, str, list[QueueItem]]) -> dict[str, object]:
    section_id, title, items = row
    return {
        "section": section_id,
        "title": title,
        "count": len(items),
        "items": [_queue_item_record(item) for item in items],
    }


def _queue_item_record(item: QueueItem) -> dict[str, str]:
    return {
        "item_id": item.item_id,
        "path": item.path,
        "detail": item.detail,
    }


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


def _obsidian_exports_to_run(project_root: Path) -> list[QueueItem]:
    notes_root = project_root / "04_atomic_notes"
    if not notes_root.exists():
        return []
    exported_ids = obsidian_exported_note_ids(project_root)
    items: list[QueueItem] = []
    for folder in sorted(notes_root.iterdir(), key=lambda path: path.name):
        if not folder.is_dir() or folder.name == "drafts":
            continue
        for note_path in sorted(folder.glob("*.md"), key=lambda path: path.stem):
            if note_path.stem in exported_ids:
                continue
            text = note_path.read_text(encoding="utf-8")
            if _frontmatter_value(text, "reviewed_by_user") != "true":
                continue
            items.append(
                QueueItem(
                    item_id=note_path.stem,
                    path=note_path.relative_to(project_root).as_posix(),
                    detail="export with: socrates note export-obsidian --project <project>",
                )
            )
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
    state = _read_learning_state(learning_state)
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
    state = _read_learning_state(learning_state)
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


def _read_learning_state(learning_state: Path) -> dict[str, object]:
    if not learning_state.exists():
        return {}
    try:
        state = read_json(learning_state)
    except JSONDecodeError:
        return {}
    return state if isinstance(state, dict) else {}


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


def _workflow_actions(project_root: Path) -> list[QueueItem]:
    closeout = read_session_closeout_status(project_root)
    regression = read_multi_session_regression_status(project_root)
    if regression is None and closeout is not None and closeout.get("status") == "ready":
        return [
            QueueItem(
                item_id="multi_session_regression",
                path=SESSION_CLOSEOUT_MANIFEST_PATH.as_posix(),
                detail=(
                    "status: not_run; "
                    "run with: socrates lifecycle regression --project <project>"
                ),
            )
        ]
    if regression is not None and regression.get("status") == "invalid":
        return [
            QueueItem(
                item_id="multi_session_regression",
                path=MULTI_SESSION_REGRESSION_MANIFEST_PATH.as_posix(),
                detail=(
                    "status: invalid; "
                    "rerun with: socrates lifecycle regression --project <project>"
                ),
            )
        ]
    if regression is not None and regression.get("status") == "fail":
        issues = regression.get("issues", [])
        return [
            QueueItem(
                item_id="multi_session_regression",
                path=MULTI_SESSION_REGRESSION_MANIFEST_PATH.as_posix(),
                detail=(
                    "status: fail; "
                    f"issues: {_workflow_issue_text(issues)}; "
                    "rerun with: socrates lifecycle regression --project <project>"
                ),
            )
        ]
    return []


def _workflow_issue_text(value: object) -> str:
    if not isinstance(value, list):
        return "none recorded"
    issues = [str(issue).strip() for issue in value if str(issue).strip()]
    return "; ".join(issues) if issues else "none recorded"


def _artifact_quality_checks_to_fix(project_root: Path) -> list[QueueItem]:
    specs = (
        {
            "item_id": "ingestion_quality",
            "manifest": "ingestion_quality_manifest.json",
            "report": "ingestion_eval.md",
            "records": "curated_references",
            "command": "socrates kb check --project <project>",
        },
        {
            "item_id": "note_quality",
            "manifest": "note_quality_manifest.json",
            "report": "note_quality_eval.md",
            "records": "notes",
            "command": "socrates note check --project <project>",
        },
        {
            "item_id": "exercise_quality",
            "manifest": "exercise_quality_manifest.json",
            "report": "exercise_quality_eval.md",
            "records": "exercises",
            "command": "socrates exercise check --project <project>",
        },
        {
            "item_id": "tutoring_quality",
            "manifest": "tutoring_quality_manifest.json",
            "report": "tutoring_eval.md",
            "records": "sessions",
            "command": "socrates session check --project <project> --session-id <id>",
        },
    )
    items: list[QueueItem] = []
    for spec in specs:
        item = _artifact_quality_check_item(project_root, spec)
        if item is not None:
            items.append(item)
    return items


def _artifact_quality_check_item(
    project_root: Path,
    spec: dict[str, str],
) -> QueueItem | None:
    manifest_path = project_root / "08_evals" / spec["manifest"]
    if not manifest_path.exists():
        return None
    report_path = project_root / "08_evals" / spec["report"]
    queue_path = report_path if report_path.exists() else manifest_path
    command = spec["command"]
    item_id = spec["item_id"]
    try:
        manifest = read_json(manifest_path)
    except JSONDecodeError:
        return _artifact_quality_manifest_item(
            project_root,
            manifest_path,
            item_id=item_id,
            issue=f"invalid {item_id} manifest JSON",
            command=command,
        )
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        return _artifact_quality_manifest_item(
            project_root,
            manifest_path,
            item_id=item_id,
            issue=f"invalid {item_id} manifest schema",
            command=command,
        )
    checked = manifest.get("checked")
    passed = manifest.get("passed")
    failed = manifest.get("failed")
    if not all(isinstance(value, int) for value in (checked, passed, failed)):
        return _artifact_quality_manifest_item(
            project_root,
            manifest_path,
            item_id=item_id,
            issue=f"invalid {item_id} manifest counts",
            command=command,
        )
    if checked < 0 or passed < 0 or failed < 0 or passed + failed != checked:
        return _artifact_quality_manifest_item(
            project_root,
            manifest_path,
            item_id=item_id,
            issue=f"invalid {item_id} manifest counts",
            command=command,
        )
    if failed == 0:
        return None
    issues = _artifact_quality_issue_items(
        manifest.get(spec["records"], []),
    )
    return QueueItem(
        item_id=item_id,
        path=queue_path.relative_to(project_root).as_posix(),
        detail=(
            "quality: fail; "
            f"failed: {failed}/{checked}; "
            f"issues: {_artifact_quality_issue_text(issues)}; "
            f"rerun with: {command}"
        ),
    )


def _artifact_quality_manifest_item(
    project_root: Path,
    manifest_path: Path,
    *,
    item_id: str,
    issue: str,
    command: str,
) -> QueueItem:
    return QueueItem(
        item_id=item_id,
        path=manifest_path.relative_to(project_root).as_posix(),
        detail=(
            "quality: fail; "
            f"issues: {issue}; "
            f"rerun with: {command}"
        ),
    )


def _artifact_quality_issue_items(records: object) -> list[str]:
    if not isinstance(records, list):
        return []
    issues: list[str] = []
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            continue
        status = str(record.get("quality_status") or record.get("status") or "").strip()
        if status != "fail":
            continue
        record_id = (
            str(record.get("id") or record.get("session_id") or record.get("file") or "").strip()
            or f"record_{index}"
        )
        record_issues = _artifact_quality_record_issues(record.get("issues", []))
        if record_issues:
            issues.append(f"{record_id}: {'; '.join(record_issues)}")
        else:
            issues.append(f"{record_id}: no issue details recorded")
    return issues


def _artifact_quality_record_issues(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(issue).strip() for issue in value if str(issue).strip()]


def _artifact_quality_issue_text(issues: list[str]) -> str:
    if not issues:
        return "none recorded"
    return "; ".join(issues)


def _tool_verifications_to_fix(project_root: Path) -> list[QueueItem]:
    manifest_path = project_root / "08_evals" / "tool_verification_quality_manifest.json"
    if not manifest_path.exists():
        return []
    try:
        manifest = read_json(manifest_path)
    except JSONDecodeError:
        return [
            _tool_quality_manifest_item(
                project_root,
                manifest_path,
                issue="invalid tool-verification quality manifest JSON",
            )
        ]
    if not isinstance(manifest, dict):
        return [
            _tool_quality_manifest_item(
                project_root,
                manifest_path,
                issue="invalid tool-verification quality manifest schema",
            )
        ]
    records = manifest.get("records", [])
    if not isinstance(records, list):
        return [
            _tool_quality_manifest_item(
                project_root,
                manifest_path,
                issue="invalid tool-verification quality manifest records",
            )
        ]

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
            items.append(
                QueueItem(
                    item_id=f"record_{index}",
                    path=manifest_path.relative_to(project_root).as_posix(),
                    detail=(
                        "quality: fail; status: invalid_record; "
                        "issues: invalid tool-verification quality manifest record; "
                        "rerun with: socrates tool check --project <project>"
                    ),
                )
            )
            continue
        quality_status = str(record.get("quality_status", "")).strip()
        if not quality_status:
            items.append(
                _tool_quality_record_item(
                    project_root,
                    manifest_path,
                    item_id=str(record.get("object_id") or f"record_{index}"),
                    record_status="invalid_quality_status",
                    issues=["missing tool-verification quality status"],
                )
            )
            continue
        if quality_status == "pass":
            continue
        if quality_status != "fail":
            issues = [
                f"unexpected tool-verification quality status: {quality_status}",
                *_tool_verification_issue_items(record.get("issues", [])),
            ]
            items.append(
                _tool_quality_record_item(
                    project_root,
                    manifest_path,
                    item_id=str(record.get("object_id") or f"record_{index}"),
                    record_status="invalid_quality_status",
                    issues=issues,
                )
            )
            continue
        object_id = str(record.get("object_id") or f"record_{index}")
        record_status = str(record.get("record_status") or "unknown")
        items.append(
            _tool_quality_record_item(
                project_root,
                queue_path,
                item_id=object_id,
                record_status=record_status,
                issues=_tool_verification_issue_items(record.get("issues", [])),
            )
        )
    return items


def _tool_quality_record_item(
    project_root: Path,
    path: Path,
    *,
    item_id: str,
    record_status: str,
    issues: list[str],
) -> QueueItem:
    return QueueItem(
        item_id=item_id,
        path=path.relative_to(project_root).as_posix(),
        detail=(
            "quality: fail; "
            f"status: {record_status}; "
            f"issues: {_tool_verification_issue_text(issues)}; "
            "rerun with: socrates tool check --project <project>"
        ),
    )


def _tool_quality_manifest_item(
    project_root: Path,
    manifest_path: Path,
    *,
    issue: str,
) -> QueueItem:
    return QueueItem(
        item_id="tool_verification_quality_manifest",
        path=manifest_path.relative_to(project_root).as_posix(),
        detail=(
            "quality: fail; "
            f"issues: {issue}; "
            "rerun with: socrates tool check --project <project>"
        ),
    )


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
