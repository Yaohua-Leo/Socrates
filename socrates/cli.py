"""Command line interface for Socrates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from .artifacts import (
    generate_atomic_note_draft,
    generate_exercise_drafts,
    generate_targeted_review_exercise_drafts,
)
from .context import load_project
from .exercises import approve_exercise_draft, grade_exercise_attempt, record_exercise_attempt
from .kb import build_reference_kb, find_counterexamples, search_reference_kb
from .learning_queue import collect_learning_queue, format_learning_queue
from .notes import export_reviewed_notes_to_obsidian, review_atomic_note
from .planning import adjust_short_term_plan_from_review_schedule, create_learning_plan
from .project import ProjectExistsError, ProjectSpec, create_project
from .project import slugify_topic
from .project_index import (
    build_cross_project_reference_graph,
    find_project_references,
    list_projects,
    scan_project_root,
)
from .quality import (
    audit_project_lifecycle,
    check_atomic_note_quality,
    check_generated_exercise_quality,
    check_reference_ingestion_quality,
    check_tutoring_session_quality,
    run_project_benchmark,
)
from .references import curate_reference, import_reference
from .reports import generate_monthly_report, generate_project_summary, generate_weekly_report
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

    queue_parser = subparsers.add_parser(
        "queue",
        help="List actionable notes and exercises for a Socrates project.",
    )
    queue_parser.add_argument("--project", required=True, help="Socrates project directory.")
    queue_parser.set_defaults(func=_handle_queue)

    lifecycle_parser = subparsers.add_parser(
        "lifecycle",
        help="Audit persisted artifacts for the full learning lifecycle.",
    )
    lifecycle_subparsers = lifecycle_parser.add_subparsers(dest="lifecycle_command", required=True)
    lifecycle_audit_parser = lifecycle_subparsers.add_parser(
        "audit",
        help="Write a lifecycle completion audit report.",
    )
    lifecycle_audit_parser.add_argument("--project", required=True, help="Socrates project directory.")
    lifecycle_audit_parser.set_defaults(func=_handle_lifecycle_audit)

    projects_parser = subparsers.add_parser(
        "projects",
        help="Manage a root containing multiple Socrates projects.",
    )
    projects_subparsers = projects_parser.add_subparsers(dest="projects_command", required=True)
    projects_scan_parser = projects_subparsers.add_parser(
        "scan",
        help="Scan a project collection root and write an index.",
    )
    projects_scan_parser.add_argument("--root", required=True, help="SocratesProjects root directory.")
    projects_scan_parser.set_defaults(func=_handle_projects_scan)
    projects_list_parser = projects_subparsers.add_parser(
        "list",
        help="List indexed Socrates projects under a root.",
    )
    projects_list_parser.add_argument("--root", required=True, help="SocratesProjects root directory.")
    projects_list_parser.set_defaults(func=_handle_projects_list)
    projects_refs_parser = projects_subparsers.add_parser(
        "refs",
        help="List reviewed atomic-note references across projects.",
    )
    projects_refs_parser.add_argument("--root", required=True, help="SocratesProjects root directory.")
    projects_refs_parser.add_argument("--query", default="", help="Optional text filter.")
    projects_refs_parser.set_defaults(func=_handle_projects_refs)
    projects_graph_parser = projects_subparsers.add_parser(
        "graph",
        help="Build the reviewed-note cross-project reference graph.",
    )
    projects_graph_parser.add_argument("--root", required=True, help="SocratesProjects root directory.")
    projects_graph_parser.set_defaults(func=_handle_projects_graph)

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
    kb_counterexamples_parser = kb_subparsers.add_parser(
        "counterexamples",
        help="Find counterexamples related to a concept.",
    )
    kb_counterexamples_parser.add_argument("--project", required=True, help="Socrates project directory.")
    kb_counterexamples_parser.add_argument("--concept", required=True, help="Concept to search counterexamples for.")
    kb_counterexamples_parser.add_argument("--limit", type=int, default=10, help="Maximum matches.")
    kb_counterexamples_parser.set_defaults(func=_handle_kb_counterexamples)
    kb_check_parser = kb_subparsers.add_parser(
        "check",
        help="Run checklist quality checks on curated references.",
    )
    kb_check_parser.add_argument("--project", required=True, help="Socrates project directory.")
    kb_check_parser.set_defaults(func=_handle_kb_check)

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
    note_check_parser = note_subparsers.add_parser(
        "check",
        help="Run checklist quality checks on atomic notes.",
    )
    note_check_parser.add_argument("--project", required=True, help="Socrates project directory.")
    note_check_parser.set_defaults(func=_handle_note_check)

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
    review_exercises_parser = review_subparsers.add_parser(
        "exercises",
        help="Generate targeted exercise drafts from the review schedule.",
    )
    review_exercises_parser.add_argument("--project", required=True, help="Socrates project directory.")
    review_exercises_parser.set_defaults(func=_handle_review_exercises)
    review_adjust_plan_parser = review_subparsers.add_parser(
        "adjust-plan",
        help="Update the short-term plan from the review schedule.",
    )
    review_adjust_plan_parser.add_argument("--project", required=True, help="Socrates project directory.")
    review_adjust_plan_parser.set_defaults(func=_handle_review_adjust_plan)

    exercise_parser = subparsers.add_parser(
        "exercise",
        help="Check and manage generated exercises.",
    )
    exercise_subparsers = exercise_parser.add_subparsers(dest="exercise_command", required=True)
    exercise_check_parser = exercise_subparsers.add_parser(
        "check",
        help="Run checklist quality checks on generated exercise drafts.",
    )
    exercise_check_parser.add_argument("--project", required=True, help="Socrates project directory.")
    exercise_check_parser.set_defaults(func=_handle_exercise_check)
    exercise_approve_parser = exercise_subparsers.add_parser(
        "approve",
        help="Approve one generated exercise draft after quality checks.",
    )
    exercise_approve_parser.add_argument("--project", required=True, help="Socrates project directory.")
    exercise_approve_parser.add_argument("--exercise", required=True, help="Generated exercise id, without .md.")
    exercise_approve_parser.set_defaults(func=_handle_exercise_approve)
    exercise_attempt_parser = exercise_subparsers.add_parser(
        "attempt",
        help="Record one answer for an approved exercise.",
    )
    exercise_attempt_parser.add_argument("--project", required=True, help="Socrates project directory.")
    exercise_attempt_parser.add_argument("--exercise", required=True, help="Generated exercise id, without .md.")
    exercise_attempt_parser.add_argument("--answer", required=True, help="Markdown/text answer file.")
    exercise_attempt_parser.set_defaults(func=_handle_exercise_attempt)
    exercise_grade_parser = exercise_subparsers.add_parser(
        "grade",
        help="Grade one recorded exercise attempt.",
    )
    exercise_grade_parser.add_argument("--project", required=True, help="Socrates project directory.")
    exercise_grade_parser.add_argument("--attempt", required=True, help="Attempt id, without .md.")
    exercise_grade_parser.add_argument("--score", type=float, required=True, help="Score from 0 to 1.")
    exercise_grade_parser.add_argument("--feedback", required=True, help="Markdown/text feedback file.")
    exercise_grade_parser.set_defaults(func=_handle_exercise_grade)

    session_parser = subparsers.add_parser(
        "session",
        help="Check and manage tutoring session artifacts.",
    )
    session_subparsers = session_parser.add_subparsers(dest="session_command", required=True)
    session_check_parser = session_subparsers.add_parser(
        "check",
        help="Run checklist quality checks on one tutoring session.",
    )
    session_check_parser.add_argument("--project", required=True, help="Socrates project directory.")
    session_check_parser.add_argument("--session-id", required=True, help="Session identifier.")
    session_check_parser.set_defaults(func=_handle_session_check)

    benchmark_parser = subparsers.add_parser(
        "benchmark",
        help="Run project-level quality benchmark suites.",
    )
    benchmark_subparsers = benchmark_parser.add_subparsers(dest="benchmark_command", required=True)
    benchmark_run_parser = benchmark_subparsers.add_parser(
        "run",
        help="Run the deterministic project quality benchmark.",
    )
    benchmark_run_parser.add_argument("--project", required=True, help="Socrates project directory.")
    benchmark_run_parser.add_argument("--session-id", required=True, help="Session identifier to check.")
    benchmark_run_parser.set_defaults(func=_handle_benchmark_run)

    report_parser = subparsers.add_parser(
        "report",
        help="Generate project learning reports.",
    )
    report_subparsers = report_parser.add_subparsers(dest="report_command", required=True)
    weekly_report_parser = report_subparsers.add_parser(
        "weekly",
        help="Generate a weekly learning report.",
    )
    weekly_report_parser.add_argument("--project", required=True, help="Socrates project directory.")
    weekly_report_parser.set_defaults(func=_handle_report_weekly)
    monthly_report_parser = report_subparsers.add_parser(
        "monthly",
        help="Generate a monthly learning review report.",
    )
    monthly_report_parser.add_argument("--project", required=True, help="Socrates project directory.")
    monthly_report_parser.set_defaults(func=_handle_report_monthly)
    project_summary_parser = report_subparsers.add_parser(
        "project-summary",
        help="Generate a project lifecycle summary report.",
    )
    project_summary_parser.add_argument("--project", required=True, help="Socrates project directory.")
    project_summary_parser.set_defaults(func=_handle_report_project_summary)

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
    path = curate_reference(args.project, args.source_id)
    if path.name.endswith(".conversion_pending.md"):
        print(f"Marked reference {args.source_id} conversion pending: {path}")
    else:
        print(f"Curated reference {args.source_id}: {path}")
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

    mistakes = _mistake_records_from_script(
        script=script,
        session_id=session_id,
        concept=concept,
        concept_id=concept_id,
        follow_up_exercises=[exercise.id for exercise in exercises[:2]],
    )
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
    draft_count = len(collect_learning_queue(context.root).notes_to_review)
    exercise_count = len(list(context.generated_exercises_dir.glob("*.md")))
    converted_count = _count_converted_references(context.references_dir)
    conversion_pending_count = _count_sources_with_status(
        context.source_registry,
        "conversion_pending",
    )
    curated_count = len(list((context.references_dir / "curated").glob("*.md")))
    kb_object_count = _count_kb_objects(context.root)
    reviewed_count = _count_reviewed_notes(context.root)
    obsidian_export_count = _count_obsidian_exports(context.root)
    scheduled_review_count = _count_scheduled_reviews(context.learning_state)
    active_misconception_count, resolved_misconception_count = _count_misconceptions_by_status(
        context.learning_state
    )
    approved_exercise_count = _count_approved_exercises(context.root)
    attempted_exercise_count = len(list((context.root / "05_exercises" / "attempted").glob("*.md")))
    graded_exercise_count = len(list((context.root / "05_exercises" / "graded").glob("*.md")))
    phase = "tutoring_complete" if latest_session != "none" else "initialization"

    print(f"Project: {context.root}")
    print(f"Current phase: {phase}")
    print(f"Imported sources: {source_count}")
    print(f"Converted references: {converted_count}")
    print(f"Conversion pending references: {conversion_pending_count}")
    print(f"Curated references: {curated_count}")
    print(f"KB objects: {kb_object_count}")
    print(f"Latest session: {latest_session}")
    print(f"Pending draft notes: {draft_count}")
    print(f"Reviewed notes: {reviewed_count}")
    print(f"Generated exercises: {exercise_count}")
    print(f"Approved exercises: {approved_exercise_count}")
    print(f"Attempted exercises: {attempted_exercise_count}")
    print(f"Graded exercises: {graded_exercise_count}")
    print(f"Obsidian exports: {obsidian_export_count}")
    print(f"Scheduled reviews: {scheduled_review_count}")
    print(f"Active misconceptions: {active_misconception_count}")
    print(f"Resolved misconceptions: {resolved_misconception_count}")
    return 0


def _handle_queue(args: argparse.Namespace) -> int:
    print(format_learning_queue(collect_learning_queue(args.project)), end="")
    return 0


def _handle_lifecycle_audit(args: argparse.Namespace) -> int:
    result = audit_project_lifecycle(args.project)
    print(
        f"Lifecycle audit passed {result.passed_checks}/{result.total_checks} checks: "
        f"{result.report_path}"
    )
    return 0 if result.passed_checks == result.total_checks else 1


def _handle_projects_scan(args: argparse.Namespace) -> int:
    index_path = scan_project_root(args.root)
    projects = list_projects(args.root)
    noun = "project" if len(projects) == 1 else "projects"
    print(f"Indexed {len(projects)} {noun}: {index_path}")
    return 0


def _handle_projects_list(args: argparse.Namespace) -> int:
    projects = list_projects(args.root)
    if not projects:
        print("No Socrates projects found")
        return 0
    for project in projects:
        print(
            f"{project['id']} | {project['title']} | "
            f"{project['status']} | {project['path']}"
        )
    return 0


def _handle_projects_refs(args: argparse.Namespace) -> int:
    references = find_project_references(args.root, query=args.query)
    if not references:
        print("No reviewed note references found")
        return 0
    for reference in references:
        print(
            f"{reference['ref']} | {reference['concept']} | "
            f"{reference['type']} | {reference['path']}"
        )
    return 0


def _handle_projects_graph(args: argparse.Namespace) -> int:
    graph_path = build_cross_project_reference_graph(args.root)
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    edges = graph.get("edges", []) if isinstance(graph, dict) else []
    edge_count = len(edges) if isinstance(edges, list) else 0
    noun = "edge" if edge_count == 1 else "edges"
    print(f"Wrote cross-project graph with {edge_count} {noun}: {graph_path}")
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
        location = _source_location(source)
        source_label = _source_label(source)
        object_label = _object_label(match)
        print(f"{object_label}{source_label} ({location})")
    return 0


def _handle_kb_counterexamples(args: argparse.Namespace) -> int:
    matches = find_counterexamples(args.project, args.concept, limit=args.limit)
    if not matches:
        print("No counterexamples found")
        return 0
    for match in matches:
        source = match.get("source", {})
        location = _source_location(source)
        source_label = _source_label(source)
        object_label = _object_label(match)
        print(f"{object_label}{source_label} ({location})")
    return 0


def _handle_kb_check(args: argparse.Namespace) -> int:
    result = check_reference_ingestion_quality(args.project)
    noun = "reference" if result.checked == 1 else "references"
    print(
        f"Checked {result.checked} curated {noun}: "
        f"{result.passed} passed, {result.failed} failed"
    )
    print(f"Ingestion quality report: {result.report_path}")
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


def _handle_note_check(args: argparse.Namespace) -> int:
    result = check_atomic_note_quality(args.project)
    print(
        f"Checked {result.checked} atomic note"
        f"{'' if result.checked == 1 else 's'}: {result.passed} passed, {result.failed} failed"
    )
    print(f"Note quality report: {result.report_path}")
    return 0


def _handle_review_schedule(args: argparse.Namespace) -> int:
    context = load_project(args.project)
    schedule_path = build_review_schedule(context)
    count = _count_scheduled_reviews(context.learning_state)
    noun = "item" if count == 1 else "items"
    print(f"Scheduled {count} review {noun}: {schedule_path}")
    return 0


def _handle_review_exercises(args: argparse.Namespace) -> int:
    exercises = generate_targeted_review_exercise_drafts(args.project)
    noun = "exercise" if len(exercises) == 1 else "exercises"
    print(f"Generated {len(exercises)} targeted review {noun}")
    return 0


def _handle_review_adjust_plan(args: argparse.Namespace) -> int:
    short_term_plan = adjust_short_term_plan_from_review_schedule(args.project)
    print(f"Adjusted short-term plan: {short_term_plan}")
    return 0


def _handle_exercise_check(args: argparse.Namespace) -> int:
    result = check_generated_exercise_quality(args.project)
    print(
        f"Checked {result.checked} exercise drafts: "
        f"{result.passed} passed, {result.failed} failed"
    )
    print(f"Exercise quality report: {result.report_path}")
    return 0


def _handle_exercise_approve(args: argparse.Namespace) -> int:
    approved = approve_exercise_draft(args.project, args.exercise)
    print(f"Approved exercise {args.exercise}: {approved}")
    return 0


def _handle_exercise_attempt(args: argparse.Namespace) -> int:
    attempt = record_exercise_attempt(args.project, args.exercise, args.answer)
    print(f"Recorded attempt for exercise {args.exercise}: {attempt}")
    return 0


def _handle_exercise_grade(args: argparse.Namespace) -> int:
    grade = grade_exercise_attempt(args.project, args.attempt, args.score, args.feedback)
    print(f"Graded attempt {args.attempt}: {grade}")
    return 0


def _handle_session_check(args: argparse.Namespace) -> int:
    result = check_tutoring_session_quality(args.project, session_id=args.session_id)
    print(f"Checked session {result.session_id}: {result.status}")
    print(f"Tutoring quality report: {result.report_path}")
    return 0


def _handle_benchmark_run(args: argparse.Namespace) -> int:
    result = run_project_benchmark(args.project, session_id=args.session_id)
    print(f"Benchmark passed {result.passed_gates}/{result.total_gates} gates")
    print(f"Benchmark report: {result.report_path}")
    return 0


def _handle_report_weekly(args: argparse.Namespace) -> int:
    report = generate_weekly_report(args.project)
    print(f"Wrote weekly report: {report}")
    return 0


def _handle_report_monthly(args: argparse.Namespace) -> int:
    report = generate_monthly_report(args.project)
    print(f"Wrote monthly report: {report}")
    return 0


def _handle_report_project_summary(args: argparse.Namespace) -> int:
    report = generate_project_summary(args.project)
    print(f"Wrote project summary: {report}")
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


def _mistake_records_from_script(
    *,
    script: dict[str, tuple[str, ...]],
    session_id: str,
    concept: str,
    concept_id: str,
    follow_up_exercises: list[str],
) -> list[MistakeRecord]:
    explicit = [
        (
            slugify_topic(misconception),
            "Detected during scripted tutoring session.",
        )
        for misconception in script.get("misconception", ())
    ]
    detected = _detect_common_misconceptions(concept, script.get("attempt", ()))
    seen = {misconception_id for misconception_id, _ in explicit}
    misconceptions = explicit + [
        item for item in detected if item[0] not in seen
    ]
    return [
        MistakeRecord(
            session_id=session_id,
            concept=concept_id,
            misconception_id=misconception_id,
            user_answer=_first(script, "attempt") or "No attempt recorded.",
            analysis=analysis,
            repair_suggestion=_first(script, "next") or f"Review the definition of {concept}.",
            follow_up_exercises=follow_up_exercises,
        )
        for misconception_id, analysis in misconceptions
    ]


def _detect_common_misconceptions(
    concept: str,
    attempts: tuple[str, ...],
) -> list[tuple[str, str]]:
    concept_text = concept.casefold()
    attempt_text = " ".join(attempts).casefold()
    if "normal" in concept_text and (
        "commut" in attempt_text
        or "central" in attempt_text
        or "center" in attempt_text
        or "abelian" in attempt_text
    ):
        return [
            (
                "normal_equals_central",
                "Confuses normality with commutativity or centrality.",
            )
        ]
    return []


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


def _count_sources_with_status(registry_path: Path, status: str) -> int:
    if not registry_path.exists():
        return 0
    return sum(
        1
        for line in registry_path.read_text(encoding="utf-8").splitlines()
        if line.strip() == f"status: {status}"
    )


def _count_converted_references(references_dir: Path) -> int:
    converted_dir = references_dir / "converted"
    if not converted_dir.exists():
        return 0
    return len(list(converted_dir.rglob("*.md")))


def _count_kb_objects(project_root: Path) -> int:
    index_path = project_root / "06_kb" / "chunks" / "reference_index.json"
    if not index_path.exists():
        return 0
    index = json.loads(index_path.read_text(encoding="utf-8"))
    objects = index.get("objects", [])
    return len(objects) if isinstance(objects, list) else 0


def _source_location(source: object) -> str:
    if not isinstance(source, dict):
        return "unknown"
    path = str(source.get("path", "unknown"))
    page = str(source.get("page", "")).strip()
    line = source.get("line")
    if page and line:
        return f"{path}:p{page}:{line}"
    if page:
        return f"{path}:p{page}"
    if line:
        return f"{path}:{line}"
    return path


def _object_label(match: dict[str, object]) -> str:
    object_type = str(match.get("type", "object"))
    number = str(match.get("number", "")).strip()
    title = str(match.get("title", "Untitled"))
    if number:
        return f"{object_type} {number}: {title}"
    return f"{object_type}: {title}"


def _source_label(source: object) -> str:
    if not isinstance(source, dict):
        return ""
    source_id = str(source.get("source_id", "")).strip()
    source_title = str(source.get("title", "")).strip()
    source_role = str(source.get("role", "")).strip()
    if source_title:
        label = source_title
        if source_role:
            label = f"{label} ({source_role})"
        if source_id:
            label = f"{label} [{source_id}]"
        return f" - {label}"
    if source_role:
        label = f"({source_role})"
        if source_id:
            label = f"{label} [{source_id}]"
        return f" {label}"
    return f" [{source_id}]" if source_id else ""


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


def _count_approved_exercises(project_root: Path) -> int:
    generated_root = project_root / "05_exercises" / "generated"
    approved = 0
    for exercise_path in generated_root.glob("*.md"):
        text = exercise_path.read_text(encoding="utf-8")
        if 'status: "approved"' in text and "reviewed_by_user: true" in text:
            approved += 1
    return approved


def _count_obsidian_exports(project_root: Path) -> int:
    obsidian_dir = project_root / "07_exports" / "obsidian"
    manifest_path = obsidian_dir / "export_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        exported_notes = manifest.get("exported_notes", []) if isinstance(manifest, dict) else []
        return len(exported_notes) if isinstance(exported_notes, list) else 0
    return len(
        [
            path
            for path in obsidian_dir.glob("*.md")
            if path.name != "_socrates_index.md"
        ]
    )


def _count_scheduled_reviews(learning_state: Path) -> int:
    if not learning_state.exists():
        return 0
    state = json.loads(learning_state.read_text(encoding="utf-8"))
    schedule = state.get("review_schedule", []) if isinstance(state, dict) else []
    return len(schedule) if isinstance(schedule, list) else 0


def _count_misconceptions_by_status(learning_state: Path) -> tuple[int, int]:
    if not learning_state.exists():
        return (0, 0)
    state = json.loads(learning_state.read_text(encoding="utf-8"))
    misconceptions = state.get("misconceptions", {}) if isinstance(state, dict) else {}
    if not isinstance(misconceptions, dict):
        return (0, 0)

    active = 0
    resolved = 0
    for value in misconceptions.values():
        if not isinstance(value, dict):
            continue
        status = value.get("status", "active")
        if status == "resolved":
            resolved += 1
        elif status == "active" or "status" not in value:
            active += 1
    return (active, resolved)
