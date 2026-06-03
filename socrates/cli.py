"""Command line interface for Socrates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from .artifacts import generate_atomic_note_draft, generate_exercise_drafts
from .context import load_project
from .kb import build_reference_kb, search_reference_kb
from .notes import export_reviewed_notes_to_obsidian, review_atomic_note
from .planning import create_learning_plan
from .project import ProjectExistsError, ProjectSpec, create_project
from .project import slugify_topic
from .references import curate_reference, import_reference
from .state import (
    EvalReportUpdate,
    LearningStatePatch,
    MistakeRecord,
    build_review_schedule,
    update_eval_report,
    update_learning_state,
)
from .tutoring import run_scripted_tutoring_session


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="socrates",
        description="Project-based mathematics learning CLI.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser(
        "init",
        help="Create a Socrates learning project.",
    )
    init_parser.add_argument("--topic", required=True, help="Learning topic.")
    init_parser.add_argument("--path", required=True, help="Project directory.")
    init_parser.add_argument(
        "--goal",
        default="",
        help="User learning goal for this project.",
    )
    init_parser.add_argument(
        "--main-reference",
        default=None,
        help="Optional main reference title or path.",
    )
    init_parser.add_argument(
        "--target-level",
        default="advanced_undergraduate",
        help="Target mathematical level.",
    )
    init_parser.add_argument(
        "--preferred-style",
        default="proof_oriented",
        help="Preferred learning style.",
    )
    init_parser.set_defaults(func=_handle_init)

    import_parser = subparsers.add_parser(
        "import",
        help="Import a local reference into a Socrates project.",
    )
    import_parser.add_argument("--project", required=True, help="Socrates project directory.")
    import_parser.add_argument("file", help="Local reference file to import.")
    import_parser.add_argument("--role", required=True, help="Reference role.")
    import_parser.add_argument("--title", default=None, help="Optional source title.")
    import_parser.add_argument("--priority", type=int, default=1, help="Source priority.")
    import_parser.add_argument("--notes", default="", help="Optional source notes.")
    import_parser.set_defaults(func=_handle_import)

    curate_parser = subparsers.add_parser(
        "curate",
        help="Create a curated Markdown draft from an imported text reference.",
    )
    curate_parser.add_argument("--project", required=True, help="Socrates project directory.")
    curate_parser.add_argument("--source-id", required=True, help="Source id from source_registry.yaml.")
    curate_parser.set_defaults(func=_handle_curate)

    plan_parser = subparsers.add_parser(
        "plan",
        help="Create initial learning-plan files for a Socrates project.",
    )
    plan_parser.add_argument("--project", required=True, help="Socrates project directory.")
    plan_parser.add_argument("--weeks", type=int, default=1, help="Reserved for later planning depth.")
    plan_parser.set_defaults(func=_handle_plan)

    teach_parser = subparsers.add_parser(
        "teach",
        help="Run a deterministic scripted tutoring session.",
    )
    teach_parser.add_argument("--project", required=True, help="Socrates project directory.")
    teach_parser.add_argument("--session-id", required=True, help="Session identifier.")
    teach_parser.add_argument("--script", required=True, help="Script file for deterministic MVP mode.")
    teach_parser.set_defaults(func=_handle_teach)

    status_parser = subparsers.add_parser(
        "status",
        help="Show a Socrates project status summary.",
    )
    status_parser.add_argument("--project", required=True, help="Socrates project directory.")
    status_parser.set_defaults(func=_handle_status)

    kb_parser = subparsers.add_parser(
        "kb",
        help="Build and search the curated reference knowledge base.",
    )
    kb_subparsers = kb_parser.add_subparsers(dest="kb_command", required=True)
    kb_build_parser = kb_subparsers.add_parser("build", help="Build the reference KB.")
    kb_build_parser.add_argument("--project", required=True, help="Socrates project directory.")
    kb_build_parser.set_defaults(func=_handle_kb_build)
    kb_search_parser = kb_subparsers.add_parser("search", help="Search the reference KB.")
    kb_search_parser.add_argument("--project", required=True, help="Socrates project directory.")
    kb_search_parser.add_argument("--query", required=True, help="Search query.")
    kb_search_parser.add_argument("--limit", type=int, default=10, help="Maximum matches.")
    kb_search_parser.set_defaults(func=_handle_kb_search)

    note_parser = subparsers.add_parser(
        "note",
        help="Review and export atomic notes.",
    )
    note_subparsers = note_parser.add_subparsers(dest="note_command", required=True)
    note_review_parser = note_subparsers.add_parser("review", help="Review one draft note.")
    note_review_parser.add_argument("--project", required=True, help="Socrates project directory.")
    note_review_parser.add_argument("--note", required=True, help="Draft note id, without .md.")
    note_review_parser.set_defaults(func=_handle_note_review)
    note_export_parser = note_subparsers.add_parser(
        "export-obsidian",
        help="Export reviewed notes to the Obsidian directory.",
    )
    note_export_parser.add_argument("--project", required=True, help="Socrates project directory.")
    note_export_parser.set_defaults(func=_handle_note_export_obsidian)

    review_parser = subparsers.add_parser(
        "review",
        help="Schedule review from the current learning state.",
    )
    review_subparsers = review_parser.add_subparsers(dest="review_command", required=True)
    review_schedule_parser = review_subparsers.add_parser(
        "schedule",
        help="Build a review schedule from weak concepts and active misconceptions.",
    )
    review_schedule_parser.add_argument("--project", required=True, help="Socrates project directory.")
    review_schedule_parser.set_defaults(func=_handle_review_schedule)

    return parser


def _handle_init(args: argparse.Namespace) -> int:
    spec = ProjectSpec(
        topic=args.topic,
        path=Path(args.path),
        goal=args.goal,
        main_reference=args.main_reference,
        target_level=args.target_level,
        preferred_style=args.preferred_style,
    )
    created_path = create_project(spec)
    print(f"Created Socrates project at {created_path}")
    return 0


def _handle_import(args: argparse.Namespace) -> int:
    record = import_reference(
        args.project,
        args.file,
        role=args.role,
        title=args.title,
        priority=args.priority,
        notes=args.notes,
    )
    print(f"Imported reference {record.id} at {record.local_path}")
    return 0


def _handle_curate(args: argparse.Namespace) -> int:
    curated = curate_reference(args.project, args.source_id)
    print(f"Curated reference {args.source_id}: {curated}")
    return 0


def _handle_plan(args: argparse.Namespace) -> int:
    written = create_learning_plan(args.project)
    print(f"Created {len(written)} learning plan files")
    return 0


def _handle_teach(args: argparse.Namespace) -> int:
    context = load_project(args.project)
    script = _read_script_fields(Path(args.script))
    session_id = args.session_id
    run_scripted_tutoring_session(context.root, args.script, session_id=session_id)

    concept = _first(script, "topic") or "Session Concept"
    concept_id = slugify_topic(concept)
    source_id, source_title = _first_source(context.source_registry)
    note = generate_atomic_note_draft(
        context.root,
        concept=concept,
        note_type="definition",
        body=_note_body(concept, session_id),
        source_id=source_id,
        source_title=source_title,
        source_location=session_id,
    )
    exercises = generate_exercise_drafts(
        context.root,
        concept=concept,
        source_id=source_id,
        prerequisites=script.get("prerequisite", ()),
        count=5,
    )

    mistakes = [
        MistakeRecord(
            session_id=session_id,
            concept=concept_id,
            misconception_id=slugify_topic(misconception),
            user_answer=_first(script, "attempt") or "No attempt recorded.",
            analysis="Detected during scripted tutoring session.",
            repair_suggestion=_first(script, "next") or f"Review the definition of {concept}.",
            follow_up_exercises=[exercise.id for exercise in exercises[:2]],
        )
        for misconception in script.get("misconception", ())
    ]
    update_learning_state(
        context,
        LearningStatePatch(
            concept_mastery={concept_id: 0.5},
            proof_skills={"guided_reasoning": 0.5},
            mistakes=mistakes,
        ),
    )
    _write_teaching_eval_reports(context, session_id, note.path, [exercise.path for exercise in exercises])

    print(f"Completed tutoring session {session_id}")
    print(f"Draft note: {note.path}")
    print(f"Generated exercises: {len(exercises)}")
    return 0


def _handle_status(args: argparse.Namespace) -> int:
    context = load_project(args.project)
    latest_session = _latest_session(context.sessions_dir)
    source_count = _count_sources(context.source_registry)
    draft_count = len(list(context.atomic_note_drafts_dir.glob("*.md")))
    exercise_count = len(list(context.generated_exercises_dir.glob("*.md")))
    curated_count = len(list((context.references_dir / "curated").glob("*.md")))
    kb_object_count = _count_kb_objects(context.root)
    reviewed_count = _count_reviewed_notes(context.root)
    obsidian_export_count = len(list((context.root / "07_exports" / "obsidian").glob("*.md")))
    scheduled_review_count = _count_scheduled_reviews(context.learning_state)
    phase = "tutoring_complete" if latest_session != "none" else "initialization"

    print(f"Project: {context.root}")
    print(f"Current phase: {phase}")
    print(f"Imported sources: {source_count}")
    print(f"Curated references: {curated_count}")
    print(f"KB objects: {kb_object_count}")
    print(f"Latest session: {latest_session}")
    print(f"Pending draft notes: {draft_count}")
    print(f"Reviewed notes: {reviewed_count}")
    print(f"Generated exercises: {exercise_count}")
    print(f"Obsidian exports: {obsidian_export_count}")
    print(f"Scheduled reviews: {scheduled_review_count}")
    return 0


def _handle_kb_build(args: argparse.Namespace) -> int:
    result = build_reference_kb(args.project)
    noun = "object" if result.object_count == 1 else "objects"
    print(f"Indexed {result.object_count} reference {noun}")
    print(f"Reference index: {result.index_path}")
    return 0


def _handle_kb_search(args: argparse.Namespace) -> int:
    matches = search_reference_kb(args.project, args.query, limit=args.limit)
    if not matches:
        print("No reference matches")
        return 0
    for match in matches:
        source = match.get("source", {})
        path = source.get("path", "unknown") if isinstance(source, dict) else "unknown"
        print(f"{match['type']}: {match['title']} ({path})")
    return 0


def _handle_note_review(args: argparse.Namespace) -> int:
    reviewed = review_atomic_note(args.project, args.note)
    print(f"Reviewed note {args.note}: {reviewed}")
    return 0


def _handle_note_export_obsidian(args: argparse.Namespace) -> int:
    exported = export_reviewed_notes_to_obsidian(args.project)
    noun = "note" if len(exported) == 1 else "notes"
    print(f"Exported {len(exported)} reviewed {noun}")
    return 0


def _handle_review_schedule(args: argparse.Namespace) -> int:
    context = load_project(args.project)
    schedule_path = build_review_schedule(context)
    count = _count_scheduled_reviews(context.learning_state)
    noun = "item" if count == 1 else "items"
    print(f"Scheduled {count} review {noun}: {schedule_path}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except ProjectExistsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _read_script_fields(script_path: Path) -> dict[str, tuple[str, ...]]:
    fields: dict[str, list[str]] = {}
    for raw_line in script_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition(":")
        if separator:
            fields.setdefault(key.strip().lower(), []).append(value.strip())
    return {key: tuple(values) for key, values in fields.items()}


def _first(fields: dict[str, tuple[str, ...]], key: str) -> str | None:
    values = fields.get(key)
    if not values:
        return None
    return values[0]


def _first_source(registry_path: Path) -> tuple[str, str | None]:
    source_id = "manual"
    title: str | None = None
    for line in registry_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("- id:") and source_id == "manual":
            source_id = stripped.removeprefix("- id:").strip()
        elif stripped.startswith("title:") and title is None:
            title = _yaml_like_string(stripped.removeprefix("title:").strip())
        if source_id != "manual" and title is not None:
            break
    return source_id, title


def _yaml_like_string(value: str) -> str:
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value == "null":
        return ""
    return value


def _note_body(concept: str, session_id: str) -> str:
    return (
        f"This draft records the first working understanding of {concept} from {session_id}.\n\n"
        "## Review Questions\n\n"
        f"- What definition must be checked when using {concept}?\n"
        "- Which example distinguishes the concept from nearby false equivalences?\n"
    )


def _write_teaching_eval_reports(
    context,
    session_id: str,
    note_path: str,
    exercise_paths: list[str],
) -> None:
    update_eval_report(
        context,
        EvalReportUpdate(
            report="tutoring",
            subject=session_id,
            score=0.75,
            summary="Scripted session completed with Socratic hints and persisted artifacts.",
            strengths=["Session transcript and next actions were written."],
            issues=["Human review is still required for mathematical depth."],
            next_actions=["Review the generated draft note before export."],
        ),
    )
    update_eval_report(
        context,
        EvalReportUpdate(
            report="exercise",
            subject=session_id,
            score=0.7,
            summary=f"Generated {len(exercise_paths)} draft exercises.",
            strengths=["Each exercise includes hints, solution outline, and rubric."],
            issues=["Exercises are deterministic scaffolds in v0.1."],
            next_actions=["Replace scaffolds with source-grounded problems in a later phase."],
        ),
    )
    update_eval_report(
        context,
        EvalReportUpdate(
            report="note_quality",
            subject=note_path,
            score=0.7,
            summary="Generated one Obsidian-compatible draft note.",
            strengths=["Frontmatter records draft and source metadata."],
            issues=["User review is required before promoting to the personal KB."],
            next_actions=["Audit statement and examples before export."],
        ),
    )


def _latest_session(sessions_dir: Path) -> str:
    sessions = sorted(path.name for path in sessions_dir.iterdir() if path.is_dir())
    return sessions[-1] if sessions else "none"


def _count_sources(registry_path: Path) -> int:
    if not registry_path.exists():
        return 0
    return sum(1 for line in registry_path.read_text(encoding="utf-8").splitlines() if line.strip().startswith("- id:"))


def _count_kb_objects(project_root: Path) -> int:
    index_path = project_root / "06_kb" / "chunks" / "reference_index.json"
    if not index_path.exists():
        return 0
    index = json.loads(index_path.read_text(encoding="utf-8"))
    objects = index.get("objects", [])
    return len(objects) if isinstance(objects, list) else 0


def _count_reviewed_notes(project_root: Path) -> int:
    reviewed = 0
    notes_root = project_root / "04_atomic_notes"
    for folder in notes_root.iterdir():
        if not folder.is_dir() or folder.name == "drafts":
            continue
        for note_path in folder.glob("*.md"):
            text = note_path.read_text(encoding="utf-8")
            if "reviewed_by_user: true" in text:
                reviewed += 1
    return reviewed


def _count_scheduled_reviews(learning_state: Path) -> int:
    if not learning_state.exists():
        return 0
    state = json.loads(learning_state.read_text(encoding="utf-8"))
    schedule = state.get("review_schedule", []) if isinstance(state, dict) else []
    return len(schedule) if isinstance(schedule, list) else 0
