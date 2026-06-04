"""Command line interface for Socrates."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys
from typing import Sequence

from .deepseek import DeepSeekClient
from .artifacts import (
    generate_atomic_note_draft,
    generate_exercise_drafts,
    generate_misconception_note_drafts,
    generate_targeted_review_exercise_drafts,
)
from .context import load_project
from .contracts import REVIEW_PRIORITY_FILTERS
from .exercise_bank import build_exercise_bank, read_exercise_bank
from .exercises import (
    EXERCISE_TYPES,
    ExerciseSummary,
    approve_exercise_draft,
    grade_exercise_attempt,
    list_exercises,
    record_exercise_attempt,
    suggest_exercise_feedback_with_llm,
)
from .exercise_validation import validate_exercise, validate_project_exercises
from .kb import (
    CONCEPT_RELATIONSHIP_TYPES,
    OBJECT_TYPES,
    build_reference_kb,
    find_counterexamples,
    list_reference_kb_objects,
    list_reference_kb_relationships,
    reference_kb_status,
    read_reference_chapter_index,
    search_reference_kb,
)
from .learning_queue import QUEUE_SECTIONS, collect_learning_queue, format_learning_queue
from .llm import LlmMessage, LlmProviderError, LlmRequest
from .llm_artifacts import list_llm_suggestions
from .llm_config import load_llm_config
from .llm_judge import suggest_session_judge_with_llm
from .multi_session import (
    read_multi_session_regression_status,
    run_multi_session_regression,
)
from .notes import (
    AtomicNoteSummary,
    NOTE_TYPES,
    export_reviewed_notes_to_obsidian,
    list_atomic_notes,
    review_atomic_note,
)
from .obsidian import (
    obsidian_backlink_count as count_obsidian_backlinks,
    obsidian_export_count as count_obsidian_exports,
)
from .planning import (
    adjust_short_term_plan_from_review_schedule,
    create_learning_plan,
    create_next_session_plan,
)
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
from .references import (
    CorrectionPatchSummary,
    SourceSummary,
    attach_converted_markdown,
    apply_correction_patch,
    create_correction_patch,
    curate_reference,
    import_reference,
    list_correction_patches,
    list_source_registry,
    review_correction_patch,
    suggest_correction_patch_with_llm,
)
from .reports import (
    REPORT_TYPES,
    ReportHistorySummary,
    ReportSummary,
    generate_monthly_report,
    generate_project_summary,
    generate_weekly_report,
    list_learning_reports,
    summarize_report_history,
)
from .session_score import score_teaching_session
from .state import (
    EvalReportUpdate,
    LearningScoreSummary,
    LearningStatePatch,
    MisconceptionSummary,
    MistakeRecord,
    build_review_schedule,
    ensure_learning_state_readable,
    list_learning_scores,
    list_misconceptions,
    repair_review_schedule,
    resolve_active_misconceptions_for_concept,
    update_eval_report,
    update_learning_state,
)
from .tool_verification import (
    check_tool_verification_records,
    check_lean_file,
    GapGroupOrderResult,
    LeanDependencyMapResult,
    LeanCheckResult,
    SageGroupOrderResult,
    map_lean_dependencies,
    search_sympy_counterexample,
    SympyCounterexampleResult,
    SympyIdentityResult,
    ToolInventoryResult,
    ToolVerificationCheckResult,
    ToolVerificationSummary,
    generate_lean_statement_skeleton,
    list_tool_verification_records,
    verify_gap_group_order,
    verify_sage_group_order,
    verify_sympy_identity,
    write_tool_inventory,
)
from .workflow import close_tutoring_session
from .workflow_manifest import read_session_closeout_status
from .tutoring import (
    TutoringSessionSummary,
    list_tutoring_sessions,
    run_scripted_tutoring_session,
    suggest_next_question_with_llm,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="socrates",
        description="Project-based mathematics learning CLI.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    llm_parser = subparsers.add_parser(
        "llm",
        help="Inspect and smoke-test the configured local LLM provider.",
    )
    llm_subparsers = llm_parser.add_subparsers(dest="llm_command", required=True)
    llm_config_parser = llm_subparsers.add_parser(
        "config",
        help="Print redacted LLM provider configuration.",
    )
    llm_config_parser.add_argument("--root", default=".", help="Directory containing .env.")
    llm_config_parser.set_defaults(func=_handle_llm_config)
    llm_smoke_parser = llm_subparsers.add_parser(
        "smoke",
        help="Call the configured LLM provider with a short prompt.",
    )
    llm_smoke_parser.add_argument("--root", default=".", help="Directory containing .env.")
    llm_smoke_parser.add_argument("--prompt", required=True, help="Short smoke-test prompt.")
    llm_smoke_parser.set_defaults(func=_handle_llm_smoke)

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

    sources_parser = subparsers.add_parser(
        "sources",
        help="Inspect imported source registry entries.",
    )
    sources_subparsers = sources_parser.add_subparsers(dest="sources_command", required=True)
    sources_list_parser = sources_subparsers.add_parser(
        "list",
        help="List imported references and processing status.",
    )
    sources_list_parser.add_argument("--project", required=True, help="Socrates project directory.")
    sources_list_parser.add_argument(
        "--status",
        default="all",
        help="Filter by exact source status; defaults to all.",
    )
    sources_list_parser.add_argument(
        "--role",
        default="all",
        help="Filter by exact source role; defaults to all.",
    )
    sources_list_parser.add_argument(
        "--type",
        default="all",
        help="Filter by exact source type; defaults to all.",
    )
    sources_list_parser.set_defaults(func=_handle_sources_list)
    sources_attach_parser = sources_subparsers.add_parser(
        "attach-conversion",
        help="Attach an externally converted Markdown file to an imported source.",
    )
    sources_attach_parser.add_argument("--project", required=True, help="Socrates project directory.")
    sources_attach_parser.add_argument("--source-id", required=True, help="Source id from source_registry.yaml.")
    sources_attach_parser.add_argument("--markdown", required=True, help="External converted Markdown file.")
    sources_attach_parser.set_defaults(func=_handle_sources_attach_conversion)

    curate_parser = subparsers.add_parser(
        "curate",
        help="Create a curated Markdown draft from an imported text reference.",
    )
    curate_parser.add_argument("--project", required=True, help="Socrates project directory.")
    curate_parser.add_argument("--source-id", required=True, help="Source id from source_registry.yaml.")
    curate_parser.set_defaults(func=_handle_curate)

    patch_parser = subparsers.add_parser(
        "patch",
        help="Write a patch-only correction proposal for a converted reference.",
    )
    patch_parser.add_argument("--project", required=True, help="Socrates project directory.")
    patch_parser.add_argument(
        "--source-id",
        required=True,
        help="Source id from source_registry.yaml.",
    )
    patch_parser.add_argument(
        "--location",
        required=True,
        help="Reference location for the proposed correction.",
    )
    patch_parser.add_argument("--original", required=True, help="Original text needing correction.")
    patch_parser.add_argument(
        "--proposed-correction",
        required=True,
        help="Proposed replacement text.",
    )
    patch_parser.add_argument("--reason", required=True, help="Reason for the correction proposal.")
    patch_parser.add_argument(
        "--risk-level",
        choices=("low", "medium", "high"),
        default="low",
        help="Risk level for applying this correction; defaults to low.",
    )
    patch_parser.set_defaults(func=_handle_patch)

    patches_parser = subparsers.add_parser(
        "patches",
        help="Inspect patch-only correction proposals.",
    )
    patches_subparsers = patches_parser.add_subparsers(dest="patches_command", required=True)
    patches_list_parser = patches_subparsers.add_parser(
        "list",
        help="List correction patches awaiting human review.",
    )
    patches_list_parser.add_argument("--project", required=True, help="Socrates project directory.")
    patches_list_parser.add_argument(
        "--source-id",
        default=None,
        help="Filter by source registry id.",
    )
    patches_list_parser.set_defaults(func=_handle_patches_list)
    patches_suggest_parser = patches_subparsers.add_parser(
        "suggest",
        help="Ask the configured LLM for one patch-only reference correction proposal.",
    )
    patches_suggest_parser.add_argument("--project", required=True, help="Socrates project directory.")
    patches_suggest_parser.add_argument("--source-id", required=True, help="Reference source id.")
    patches_suggest_parser.add_argument(
        "--location-hint",
        default="",
        help="Optional section or line hint to focus the LLM review.",
    )
    patches_suggest_parser.set_defaults(func=_handle_patches_suggest)
    patches_review_parser = patches_subparsers.add_parser(
        "review",
        help="Record a human review decision on a correction patch.",
    )
    patches_review_parser.add_argument("--project", required=True, help="Socrates project directory.")
    patches_review_parser.add_argument("--patch", required=True, help="Patch id, without .patch.md.")
    patches_review_parser.add_argument(
        "--decision",
        choices=("accepted", "rejected"),
        required=True,
        help="Human review decision for this patch.",
    )
    patches_review_parser.add_argument(
        "--note",
        default="",
        help="Optional review note.",
    )
    patches_review_parser.set_defaults(func=_handle_patches_review)
    patches_apply_parser = patches_subparsers.add_parser(
        "apply",
        help="Apply an accepted correction patch to its curated draft.",
    )
    patches_apply_parser.add_argument("--project", required=True, help="Socrates project directory.")
    patches_apply_parser.add_argument("--patch", required=True, help="Patch id, without .patch.md.")
    patches_apply_parser.set_defaults(func=_handle_patches_apply)

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
    queue_parser.add_argument(
        "--section",
        choices=("all", *sorted(QUEUE_SECTIONS)),
        default="all",
        help="Show one queue section; defaults to all.",
    )
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
    lifecycle_regression_parser = lifecycle_subparsers.add_parser(
        "regression",
        help="Run deterministic multi-session product-loop regression.",
    )
    lifecycle_regression_parser.add_argument(
        "--project",
        required=True,
        help="Socrates project directory.",
    )
    lifecycle_regression_parser.set_defaults(func=_handle_lifecycle_regression)

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
    kb_list_parser = kb_subparsers.add_parser(
        "list",
        help="List indexed reference KB objects.",
    )
    kb_list_parser.add_argument("--project", required=True, help="Socrates project directory.")
    kb_list_parser.add_argument(
        "--type",
        choices=("all", *sorted(OBJECT_TYPES)),
        default="all",
        help="Filter by reference object type; defaults to all.",
    )
    kb_list_parser.add_argument(
        "--source-id",
        help="Filter by source registry id.",
    )
    kb_list_parser.set_defaults(func=_handle_kb_list)
    kb_chapters_parser = kb_subparsers.add_parser(
        "chapters",
        help="List the generated chapter and section index.",
    )
    kb_chapters_parser.add_argument("--project", required=True, help="Socrates project directory.")
    kb_chapters_parser.set_defaults(func=_handle_kb_chapters)
    kb_search_parser = kb_subparsers.add_parser("search", help="Search the reference KB.")
    kb_search_parser.add_argument("--project", required=True, help="Socrates project directory.")
    kb_search_parser.add_argument("--query", required=True, help="Search query.")
    kb_search_parser.add_argument(
        "--type",
        choices=("all", *sorted(OBJECT_TYPES)),
        default="all",
        help="Filter matches by reference object type; defaults to all.",
    )
    kb_search_parser.add_argument(
        "--source-id",
        help="Filter matches by source registry id.",
    )
    kb_search_parser.add_argument(
        "--relationship-type",
        choices=("all", *sorted(CONCEPT_RELATIONSHIP_TYPES)),
        default="all",
        help="Filter matches by explicit concept relationship type; defaults to all.",
    )
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
    kb_relationships_parser = kb_subparsers.add_parser(
        "relationships",
        help="List explicit concept-graph relationships from the Reference KB.",
    )
    kb_relationships_parser.add_argument("--project", required=True, help="Socrates project directory.")
    kb_relationships_parser.add_argument(
        "--type",
        choices=("all", *sorted(CONCEPT_RELATIONSHIP_TYPES)),
        default="all",
        help="Filter by relationship type; defaults to all explicit non-prerequisite relationships.",
    )
    kb_relationships_parser.set_defaults(func=_handle_kb_relationships)
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
    note_list_parser = note_subparsers.add_parser(
        "list",
        help="List atomic notes by review/export status.",
    )
    note_list_parser.add_argument("--project", required=True, help="Socrates project directory.")
    note_list_parser.add_argument(
        "--status",
        choices=("all", "pending", "reviewed", "exported"),
        default="all",
        help="Filter notes by lifecycle status; defaults to all.",
    )
    note_list_parser.add_argument(
        "--type",
        choices=("all", *sorted(NOTE_TYPES)),
        default="all",
        help="Filter notes by atomic note type; defaults to all.",
    )
    note_list_parser.set_defaults(func=_handle_note_list)
    note_review_parser = note_subparsers.add_parser("review", help="Review one draft note.")
    note_review_parser.add_argument("--project", required=True, help="Socrates project directory.")
    note_review_parser.add_argument("--note", required=True, help="Draft note id, without .md.")
    note_review_parser.set_defaults(func=_handle_note_review)
    note_misconception_parser = note_subparsers.add_parser(
        "draft-misconceptions",
        help="Draft misconception atomic notes from learning state.",
    )
    note_misconception_parser.add_argument(
        "--project",
        required=True,
        help="Socrates project directory.",
    )
    note_misconception_parser.add_argument(
        "--status",
        choices=("active", "resolved", "all"),
        default="active",
        help="Misconception status to draft; defaults to active.",
    )
    note_misconception_parser.set_defaults(func=_handle_note_draft_misconceptions)
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
    review_schedule_parser.add_argument(
        "--threshold",
        type=float,
        default=0.7,
        help="Mastery score below this value is scheduled for review; defaults to 0.7.",
    )
    review_schedule_parser.add_argument(
        "--as-of",
        default=None,
        help="ISO date used when assigning review dates; defaults to today.",
    )
    review_schedule_parser.set_defaults(func=_handle_review_schedule)
    review_exercises_parser = review_subparsers.add_parser(
        "exercises",
        help="Generate targeted exercise drafts from the review schedule.",
    )
    review_exercises_parser.add_argument("--project", required=True, help="Socrates project directory.")
    review_exercises_parser.add_argument(
        "--due-by",
        default=None,
        help="Only generate exercises for review items due on or before this ISO date.",
    )
    review_exercises_parser.add_argument(
        "--priority",
        choices=REVIEW_PRIORITY_FILTERS,
        default="all",
        help="Only generate exercises for review items with this priority; defaults to all.",
    )
    review_exercises_parser.set_defaults(func=_handle_review_exercises)
    review_adjust_plan_parser = review_subparsers.add_parser(
        "adjust-plan",
        help="Update the short-term plan from the review schedule.",
    )
    review_adjust_plan_parser.add_argument("--project", required=True, help="Socrates project directory.")
    review_adjust_plan_parser.set_defaults(func=_handle_review_adjust_plan)
    review_due_parser = review_subparsers.add_parser(
        "due",
        help="List review items due on or before a date.",
    )
    review_due_parser.add_argument("--project", required=True, help="Socrates project directory.")
    review_due_parser.add_argument(
        "--as-of",
        default=None,
        help="ISO date used as the due-review cutoff; defaults to today.",
    )
    review_due_parser.add_argument(
        "--priority",
        choices=REVIEW_PRIORITY_FILTERS,
        default="all",
        help="Filter due reviews by priority; defaults to all.",
    )
    review_due_parser.set_defaults(func=_handle_review_due)
    review_repair_parser = review_subparsers.add_parser(
        "repair-schedule",
        help="Repair missing or invalid review scheduled_for dates.",
    )
    review_repair_parser.add_argument("--project", required=True, help="Socrates project directory.")
    review_repair_parser.add_argument(
        "--as-of",
        default=None,
        help="ISO date used to repair missing or invalid dates; defaults to today.",
    )
    review_repair_parser.set_defaults(func=_handle_review_repair_schedule)
    review_resolve_parser = review_subparsers.add_parser(
        "resolve",
        help="Mark active misconceptions for a concept as resolved.",
    )
    review_resolve_parser.add_argument(
        "--project",
        required=True,
        help="Socrates project directory.",
    )
    review_resolve_parser.add_argument(
        "--concept",
        required=True,
        help="Concept whose misconceptions were repaired.",
    )
    review_resolve_parser.set_defaults(func=_handle_review_resolve)
    review_misconceptions_parser = review_subparsers.add_parser(
        "misconceptions",
        help="List active and resolved misconceptions from learning state.",
    )
    review_misconceptions_parser.add_argument(
        "--project",
        required=True,
        help="Socrates project directory.",
    )
    review_misconceptions_parser.add_argument(
        "--status",
        choices=("all", "active", "resolved"),
        default="all",
        help="Filter misconceptions by status; defaults to all.",
    )
    review_misconceptions_parser.set_defaults(func=_handle_review_misconceptions)
    review_mastery_parser = review_subparsers.add_parser(
        "mastery",
        help="List concept mastery and proof-skill scores.",
    )
    review_mastery_parser.add_argument(
        "--project",
        required=True,
        help="Socrates project directory.",
    )
    review_mastery_parser.add_argument(
        "--kind",
        choices=("all", "concept", "proof_skill"),
        default="all",
        help="Filter by score kind; defaults to all.",
    )
    review_mastery_parser.add_argument(
        "--status",
        choices=("all", "weak", "ready"),
        default="all",
        help="Filter scores by threshold status; defaults to all.",
    )
    review_mastery_parser.add_argument(
        "--threshold",
        type=float,
        default=0.7,
        help="Weak/ready cutoff; defaults to 0.7.",
    )
    review_mastery_parser.set_defaults(func=_handle_review_mastery)

    exercise_parser = subparsers.add_parser(
        "exercise",
        help="Check and manage generated exercises.",
    )
    exercise_subparsers = exercise_parser.add_subparsers(dest="exercise_command", required=True)
    exercise_list_parser = exercise_subparsers.add_parser(
        "list",
        help="List generated exercises by learner/reviewer status.",
    )
    exercise_list_parser.add_argument("--project", required=True, help="Socrates project directory.")
    exercise_list_parser.add_argument(
        "--status",
        choices=("all", "draft", "approved", "attempted", "graded"),
        default="all",
        help="Filter exercises by lifecycle status; defaults to all.",
    )
    exercise_list_parser.add_argument(
        "--type",
        choices=("all", *sorted(EXERCISE_TYPES)),
        default="all",
        help="Filter exercises by exercise type; defaults to all.",
    )
    exercise_list_parser.set_defaults(func=_handle_exercise_list)
    exercise_check_parser = exercise_subparsers.add_parser(
        "check",
        help="Run checklist quality checks on generated exercise drafts.",
    )
    exercise_check_parser.add_argument("--project", required=True, help="Socrates project directory.")
    exercise_check_parser.set_defaults(func=_handle_exercise_check)
    exercise_validate_parser = exercise_subparsers.add_parser(
        "validate",
        help="Run v0.4 schema and evidence validation for generated exercise drafts.",
    )
    exercise_validate_parser.add_argument("--project", required=True, help="Socrates project directory.")
    validation_target = exercise_validate_parser.add_mutually_exclusive_group(required=True)
    validation_target.add_argument("--all", action="store_true", help="Validate all generated exercises.")
    validation_target.add_argument("--exercise", help="Generated exercise id, without .md.")
    exercise_validate_parser.set_defaults(func=_handle_exercise_validate)
    exercise_bank_parser = exercise_subparsers.add_parser(
        "bank",
        help="Build or inspect the approved exercise bank.",
    )
    exercise_bank_subparsers = exercise_bank_parser.add_subparsers(
        dest="exercise_bank_command",
        required=True,
    )
    exercise_bank_build_parser = exercise_bank_subparsers.add_parser(
        "build",
        help="Build the bank manifest from approved, passing validation exercises.",
    )
    exercise_bank_build_parser.add_argument("--project", required=True, help="Socrates project directory.")
    exercise_bank_build_parser.set_defaults(func=_handle_exercise_bank_build)
    exercise_bank_status_parser = exercise_bank_subparsers.add_parser(
        "status",
        help="Show the current exercise bank manifest.",
    )
    exercise_bank_status_parser.add_argument("--project", required=True, help="Socrates project directory.")
    exercise_bank_status_parser.set_defaults(func=_handle_exercise_bank_status)
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
    exercise_grade_parser.add_argument(
        "--misconception",
        help="Optional misconception id to record in the mistake bank.",
    )
    exercise_grade_parser.add_argument(
        "--analysis",
        help="Optional concise mistake analysis; requires --misconception to be recorded.",
    )
    exercise_grade_parser.add_argument(
        "--repair-suggestion",
        help="Optional repair suggestion; defaults to the feedback text when a misconception is recorded.",
    )
    exercise_grade_parser.set_defaults(func=_handle_exercise_grade)
    exercise_suggest_feedback_parser = exercise_subparsers.add_parser(
        "suggest-feedback",
        help="Ask the configured LLM for draft feedback on one exercise attempt.",
    )
    exercise_suggest_feedback_parser.add_argument("--project", required=True, help="Socrates project directory.")
    exercise_suggest_feedback_parser.add_argument("--attempt", required=True, help="Attempt id, without .md.")
    exercise_suggest_feedback_parser.set_defaults(func=_handle_exercise_suggest_feedback)

    session_parser = subparsers.add_parser(
        "session",
        help="Check and manage tutoring session artifacts.",
    )
    session_subparsers = session_parser.add_subparsers(dest="session_command", required=True)
    session_list_parser = session_subparsers.add_parser(
        "list",
        help="List tutoring sessions and artifact completeness.",
    )
    session_list_parser.add_argument("--project", required=True, help="Socrates project directory.")
    session_list_parser.add_argument(
        "--status",
        choices=("all", "complete", "incomplete"),
        default="all",
        help="Filter sessions by artifact completeness; defaults to all.",
    )
    session_list_parser.set_defaults(func=_handle_session_list)
    session_check_parser = session_subparsers.add_parser(
        "check",
        help="Run checklist quality checks on one tutoring session.",
    )
    session_check_parser.add_argument("--project", required=True, help="Socrates project directory.")
    session_check_parser.add_argument("--session-id", required=True, help="Session identifier.")
    session_check_parser.set_defaults(func=_handle_session_check)
    session_score_parser = session_subparsers.add_parser(
        "score",
        help="Write a session score report from deterministic quality gates.",
    )
    session_score_parser.add_argument("--project", required=True, help="Socrates project directory.")
    session_score_parser.add_argument("--session-id", required=True, help="Session identifier.")
    session_score_parser.set_defaults(func=_handle_session_score)
    session_plan_next_parser = session_subparsers.add_parser(
        "plan-next",
        help="Create a deterministic handoff plan for the next tutoring session.",
    )
    session_plan_next_parser.add_argument("--project", required=True, help="Socrates project directory.")
    session_plan_next_parser.add_argument("--session-id", required=True, help="Next session identifier.")
    session_plan_next_parser.add_argument(
        "--as-of",
        default=None,
        help="ISO date used as the due-review cutoff; defaults to today.",
    )
    session_plan_next_parser.set_defaults(func=_handle_session_plan_next)
    session_closeout_parser = session_subparsers.add_parser(
        "closeout",
        help="Run deterministic post-session score, next-plan, and summary closeout.",
    )
    session_closeout_parser.add_argument("--project", required=True, help="Socrates project directory.")
    session_closeout_parser.add_argument("--session-id", required=True, help="Completed tutoring session id.")
    session_closeout_parser.add_argument("--next-session-id", required=True, help="Next tutoring session id.")
    session_closeout_parser.add_argument(
        "--as-of",
        default=None,
        help="ISO date used as the due-review cutoff; defaults to today.",
    )
    session_closeout_parser.set_defaults(func=_handle_session_closeout)
    session_suggest_parser = session_subparsers.add_parser(
        "suggest-next",
        help="Ask the configured LLM for a draft next Socratic question.",
    )
    session_suggest_parser.add_argument("--project", required=True, help="Socrates project directory.")
    session_suggest_parser.add_argument("--session-id", required=True, help="Tutoring session id.")
    session_suggest_parser.set_defaults(func=_handle_session_suggest_next)
    session_judge_suggest_parser = session_subparsers.add_parser(
        "judge-suggest",
        help="Ask the configured LLM for a review-only session judge draft.",
    )
    session_judge_suggest_parser.add_argument("--project", required=True, help="Socrates project directory.")
    session_judge_suggest_parser.add_argument("--session-id", required=True, help="Tutoring session id.")
    session_judge_suggest_parser.set_defaults(func=_handle_session_judge_suggest)

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
    benchmark_status_parser = benchmark_subparsers.add_parser(
        "status",
        help="Show the latest persisted benchmark manifest.",
    )
    benchmark_status_parser.add_argument("--project", required=True, help="Socrates project directory.")
    benchmark_status_parser.set_defaults(func=_handle_benchmark_status)

    report_parser = subparsers.add_parser(
        "report",
        help="Generate project learning reports.",
    )
    report_subparsers = report_parser.add_subparsers(dest="report_command", required=True)
    report_list_parser = report_subparsers.add_parser(
        "list",
        help="List expected learning reports and generation status.",
    )
    report_list_parser.add_argument("--project", required=True, help="Socrates project directory.")
    report_list_parser.add_argument(
        "--status",
        choices=("all", "generated", "missing", "stale"),
        default="all",
        help="Filter reports by generation/freshness status; defaults to all.",
    )
    report_list_parser.add_argument(
        "--type",
        choices=("all", *sorted(REPORT_TYPES)),
        default="all",
        help="Filter reports by report type; defaults to all.",
    )
    report_list_parser.set_defaults(func=_handle_report_list)
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

    tool_parser = subparsers.add_parser(
        "tool",
        help="Generate tool-verification artifacts.",
    )
    tool_subparsers = tool_parser.add_subparsers(dest="tool_command", required=True)
    lean_skeleton_parser = tool_subparsers.add_parser(
        "lean-skeleton",
        help="Generate an unchecked Lean statement skeleton from a reference KB object.",
    )
    lean_skeleton_parser.add_argument("--project", required=True, help="Socrates project directory.")
    lean_skeleton_parser.add_argument("--object-id", required=True, help="Reference KB object id.")
    lean_skeleton_parser.add_argument(
        "--namespace",
        default="Socrates",
        help="Lean namespace to use in the generated skeleton.",
    )
    lean_skeleton_parser.set_defaults(func=_handle_tool_lean_skeleton)
    lean_check_parser = tool_subparsers.add_parser(
        "lean-check",
        help="Run optional Lean frontend checking on a project-local .lean file.",
    )
    lean_check_parser.add_argument("--project", required=True, help="Socrates project directory.")
    lean_check_parser.add_argument("--file", required=True, help="Project-local Lean file to check.")
    lean_check_parser.add_argument("--object-id", default=None, help="Optional stable object id for this check.")
    lean_check_parser.add_argument("--title", default=None, help="Optional title for reports.")
    lean_check_parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=10,
        help="Maximum seconds to wait for Lean; defaults to 10.",
    )
    lean_check_parser.set_defaults(func=_handle_tool_lean_check)
    lean_deps_parser = tool_subparsers.add_parser(
        "lean-deps",
        help="Map a reference KB object's dependencies for Lean formalization.",
    )
    lean_deps_parser.add_argument("--project", required=True, help="Socrates project directory.")
    lean_deps_parser.add_argument("--object-id", required=True, help="Reference KB object id.")
    lean_deps_parser.set_defaults(func=_handle_tool_lean_deps)
    tool_inventory_parser = tool_subparsers.add_parser(
        "inventory",
        help="Record local availability of optional math verification tools.",
    )
    tool_inventory_parser.add_argument("--project", required=True, help="Socrates project directory.")
    tool_inventory_parser.set_defaults(func=_handle_tool_inventory)
    sympy_identity_parser = tool_subparsers.add_parser(
        "sympy-identity",
        help="Use optional SymPy to check whether lhs - rhs simplifies to zero.",
    )
    sympy_identity_parser.add_argument("--project", required=True, help="Socrates project directory.")
    sympy_identity_parser.add_argument("--object-id", required=True, help="Stable object id for this check.")
    sympy_identity_parser.add_argument("--lhs", required=True, help="Left-hand expression.")
    sympy_identity_parser.add_argument("--rhs", required=True, help="Right-hand expression.")
    sympy_identity_parser.add_argument("--title", default=None, help="Optional title for reports.")
    sympy_identity_parser.set_defaults(func=_handle_tool_sympy_identity)
    sympy_counterexample_parser = tool_subparsers.add_parser(
        "sympy-counterexample",
        help="Use optional SymPy to search finite integer samples for a counterexample.",
    )
    sympy_counterexample_parser.add_argument("--project", required=True, help="Socrates project directory.")
    sympy_counterexample_parser.add_argument("--object-id", required=True, help="Stable object id for this search.")
    sympy_counterexample_parser.add_argument("--lhs", required=True, help="Left-hand expression.")
    sympy_counterexample_parser.add_argument("--rhs", required=True, help="Right-hand expression.")
    sympy_counterexample_parser.add_argument(
        "--samples",
        default="-2,-1,0,1,2",
        help="Comma-separated integer samples for each variable.",
    )
    sympy_counterexample_parser.add_argument("--title", default=None, help="Optional title for reports.")
    sympy_counterexample_parser.set_defaults(func=_handle_tool_sympy_counterexample)
    gap_order_parser = tool_subparsers.add_parser(
        "gap-order",
        help="Use optional GAP to check the order of a finite group expression.",
    )
    gap_order_parser.add_argument("--project", required=True, help="Socrates project directory.")
    gap_order_parser.add_argument("--object-id", required=True, help="Stable object id for this check.")
    gap_order_parser.add_argument("--group", required=True, help="GAP group expression, for example Group((1,2,3)).")
    gap_order_parser.add_argument(
        "--expected-order",
        type=int,
        required=True,
        help="Expected finite group order.",
    )
    gap_order_parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=10,
        help="Maximum seconds to wait for GAP; defaults to 10.",
    )
    gap_order_parser.add_argument("--title", default=None, help="Optional title for reports.")
    gap_order_parser.set_defaults(func=_handle_tool_gap_order)
    sage_order_parser = tool_subparsers.add_parser(
        "sage-order",
        help="Use optional SageMath to check the order of a finite group expression.",
    )
    sage_order_parser.add_argument("--project", required=True, help="Socrates project directory.")
    sage_order_parser.add_argument("--object-id", required=True, help="Stable object id for this check.")
    sage_order_parser.add_argument(
        "--group",
        required=True,
        help="Sage group expression, for example PermutationGroup([[(1,2,3)]]).",
    )
    sage_order_parser.add_argument(
        "--expected-order",
        type=int,
        required=True,
        help="Expected finite group order.",
    )
    sage_order_parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=30,
        help="Maximum seconds to wait for Sage; defaults to 30.",
    )
    sage_order_parser.add_argument("--title", default=None, help="Optional title for reports.")
    sage_order_parser.set_defaults(func=_handle_tool_sage_order)
    tool_list_parser = tool_subparsers.add_parser(
        "list",
        help="List persisted tool-verification records.",
    )
    tool_list_parser.add_argument("--project", required=True, help="Socrates project directory.")
    tool_list_parser.add_argument(
        "--status",
        choices=(
            "all",
            "available",
            "counterexample_found",
            "failed",
            "lean_checked",
            "mapped",
            "no_counterexample_found",
            "partial",
            "stale_reference_kb",
            "unchecked_skeleton",
            "unavailable",
            "verified",
        ),
        default="all",
        help="Filter records by verification status; defaults to all.",
    )
    tool_list_parser.set_defaults(func=_handle_tool_list)
    tool_check_parser = tool_subparsers.add_parser(
        "check",
        help="Run checklist checks on persisted tool-verification records.",
    )
    tool_check_parser.add_argument("--project", required=True, help="Socrates project directory.")
    tool_check_parser.set_defaults(func=_handle_tool_check)

    return parser


def _handle_llm_config(args: argparse.Namespace) -> int:
    config = load_llm_config(Path(args.root))
    print(config.redacted_summary(), end="")
    return 0


def _handle_llm_smoke(args: argparse.Namespace) -> int:
    config = load_llm_config(Path(args.root))
    if not config.api_key_present:
        print("error: DEEPSEEK_API_KEY is missing", file=sys.stderr)
        return 1
    client = DeepSeekClient(config)
    try:
        response = client.complete(
            LlmRequest(
                purpose="cli_smoke",
                messages=(LlmMessage(role="user", content=args.prompt),),
                temperature=0.0,
                max_tokens=64,
            )
        )
    except LlmProviderError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(response.content)
    return 0


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


def _handle_sources_list(args: argparse.Namespace) -> int:
    sources = list_source_registry(
        args.project,
        status=args.status,
        role=args.role,
        source_type=args.type,
    )
    print(_source_registry_text(sources), end="")
    return 0


def _source_registry_text(sources: list[SourceSummary]) -> str:
    lines = ["# Source Registry", ""]
    if not sources:
        lines.append("- none")
        return "\n".join(lines) + "\n"

    for source in sources:
        lines.append(
            (
                f"- {source.id} | {source.status} | {source.type} | "
                f"{source.role} | priority {source.priority} | {source.title}"
            )
        )
        lines.append(f"  - raw: {_display_path(source.local_path)}")
        lines.append(f"  - markdown: {_display_path(source.markdown_path)}")
        lines.append(f"  - curated: {_display_path(source.curated_path)}")
        if source.curated_quality_status:
            lines.append(f"  - curated quality: {source.curated_quality_status}")
        if source.notes:
            lines.append(f"  - notes: {source.notes}")
    return "\n".join(lines) + "\n"


def _display_path(value: str) -> str:
    return value if value else "none"


def _handle_sources_attach_conversion(args: argparse.Namespace) -> int:
    curated_path = attach_converted_markdown(args.project, args.source_id, args.markdown)
    context = load_project(args.project)
    converted_path = context.references_dir / "converted" / "markdown" / f"{args.source_id}.md"
    print(f"Attached converted reference {args.source_id}")
    print(f"Converted markdown: {converted_path}")
    print(f"Curated reference: {curated_path}")
    return 0


def _handle_curate(args: argparse.Namespace) -> int:
    path = curate_reference(args.project, args.source_id)
    if path.name.endswith(".conversion_pending.md"):
        print(f"Marked reference {args.source_id} conversion pending: {path}")
    else:
        print(f"Curated reference {args.source_id}: {path}")
    return 0


def _handle_patch(args: argparse.Namespace) -> int:
    patch = create_correction_patch(
        args.project,
        args.source_id,
        location=args.location,
        original=args.original,
        proposed_correction=args.proposed_correction,
        reason=args.reason,
        risk_level=args.risk_level,
    )
    print(f"Wrote correction patch for {args.source_id}: {patch}")
    return 0


def _handle_patches_list(args: argparse.Namespace) -> int:
    patches = list_correction_patches(args.project, source_id=args.source_id)
    print(_correction_patches_text(patches), end="")
    return 0


def _handle_patches_suggest(args: argparse.Namespace) -> int:
    config = load_llm_config(Path.cwd())
    client = DeepSeekClient(config)
    try:
        patch = suggest_correction_patch_with_llm(
            args.project,
            args.source_id,
            client=client,
            location_hint=args.location_hint,
        )
    except (OSError, ValueError, LlmProviderError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote LLM correction patch for {args.source_id}: {patch}")
    return 0


def _handle_patches_review(args: argparse.Namespace) -> int:
    review_correction_patch(
        args.project,
        args.patch,
        decision=args.decision,
        note=args.note,
    )
    print(f"Reviewed correction patch {args.patch}: {args.decision}")
    return 0


def _handle_patches_apply(args: argparse.Namespace) -> int:
    target = apply_correction_patch(args.project, args.patch)
    print(f"Applied correction patch {args.patch}: {target}")
    return 0


def _correction_patches_text(patches: list[CorrectionPatchSummary]) -> str:
    lines = ["# Correction Patches", ""]
    if not patches:
        lines.append("- none")
        return "\n".join(lines) + "\n"
    lines.extend(
        (
            f"- {patch.patch_id} | {patch.status} | {patch.source_id} | "
            f"{patch.risk_level} | {patch.location} | {patch.path}"
        )
        for patch in patches
    )
    return "\n".join(lines) + "\n"


def _handle_plan(args: argparse.Namespace) -> int:
    _warn_if_reference_kb_stale(args.project)
    written = create_learning_plan(args.project)
    print(f"Created {len(written)} learning plan files")
    return 0


def _handle_teach(args: argparse.Namespace) -> int:
    context = load_project(args.project)
    script = _read_script_fields(Path(args.script))
    session_id = args.session_id
    ensure_learning_state_readable(
        context.learning_state,
        action="running tutoring sessions",
    )
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
    queue = collect_learning_queue(context.root)
    draft_count = len(queue.notes_to_review)
    misconception_note_draft_count = len(queue.misconception_notes_to_draft)
    obsidian_exports_to_run_count = len(queue.obsidian_exports_to_run)
    quality_checks_to_fix_count = len(queue.quality_checks_to_fix)
    workflow_action_count = len(queue.workflow_actions)
    exercise_count = len(list(context.generated_exercises_dir.glob("*.md")))
    converted_count = _count_converted_references(context.references_dir)
    conversion_pending_count = _count_sources_with_status(
        context.source_registry,
        "conversion_pending",
    )
    correction_patches = list_correction_patches(context.root)
    correction_patch_count = len(correction_patches)
    pending_correction_patch_count = sum(
        1 for patch in correction_patches if patch.status == "pending"
    )
    llm_suggestion_draft_count = _count_llm_suggestion_drafts(context.root)
    curated_count = len(list((context.references_dir / "curated").glob("*.md")))
    kb_status = reference_kb_status(context.root)
    kb_object_count = kb_status.object_count
    reviewed_count = _count_reviewed_notes(context.root)
    obsidian_export_count = count_obsidian_exports(context.root)
    obsidian_backlink_count = count_obsidian_backlinks(context.root)
    scheduled_review_count = _count_scheduled_reviews(context.learning_state)
    next_review = _next_scheduled_review(context.learning_state)
    report_count = _count_learning_reports(context.root)
    report_history = summarize_report_history(context.root)
    tool_verification_count = _count_tool_verification_records(context.root)
    ingestion_quality = _read_quality_manifest_status(
        context.root,
        "ingestion_quality_manifest.json",
    )
    note_quality = _read_quality_manifest_status(context.root, "note_quality_manifest.json")
    exercise_quality = _read_quality_manifest_status(
        context.root,
        "exercise_quality_manifest.json",
    )
    exercise_validation = _read_exercise_validation_status(context.root)
    tutoring_quality = _read_quality_manifest_status(
        context.root,
        "tutoring_quality_manifest.json",
    )
    tool_verification_quality = _read_tool_verification_quality_status(context.root)
    benchmark_status = _read_benchmark_status(context.root)
    session_score_status = _read_session_score_status(context.root)
    session_closeout_status = read_session_closeout_status(context.root)
    multi_session_regression_status = read_multi_session_regression_status(context.root)
    next_session_plan_status = _read_next_session_plan_status(context.root)
    active_misconception_count, resolved_misconception_count = _count_misconceptions_by_status(
        context.learning_state
    )
    approved_exercise_count = _count_approved_exercises(context.root)
    exercise_bank_count = _count_exercise_bank_entries(context.root)
    attempted_exercise_count = len(list((context.root / "05_exercises" / "attempted").glob("*.md")))
    graded_exercise_count = len(list((context.root / "05_exercises" / "graded").glob("*.md")))
    phase = _current_project_phase(
        imported_sources=source_count,
        converted_references=converted_count,
        curated_references=curated_count,
        kb_objects=kb_object_count,
        latest_session=latest_session,
        pending_draft_notes=draft_count,
        reviewed_notes=reviewed_count,
        approved_exercises=approved_exercise_count,
        attempted_exercises=attempted_exercise_count,
        graded_exercises=graded_exercise_count,
        obsidian_exports=obsidian_export_count,
        obsidian_exports_to_run=obsidian_exports_to_run_count,
        scheduled_reviews=scheduled_review_count,
        learning_reports=report_count,
        learning_plans=_count_learning_plans(context.learning_plan_dir),
        benchmark_score=(
            benchmark_status["score"]
            if benchmark_status is not None and benchmark_status.get("status") != "invalid"
            else None
        ),
    )

    print(f"Project: {context.root}")
    print(f"Current phase: {phase}")
    print(f"Imported sources: {source_count}")
    print(f"Converted references: {converted_count}")
    print(f"Conversion pending references: {conversion_pending_count}")
    print(f"Correction patches: {correction_patch_count}")
    print(f"Pending correction patches: {pending_correction_patch_count}")
    print(f"LLM suggestion drafts: {llm_suggestion_draft_count}")
    print(f"Curated references: {curated_count}")
    print(f"KB objects: {kb_object_count}")
    print(f"Reference KB status: {kb_status.status}")
    print(f"Latest session: {latest_session}")
    print(f"Pending draft notes: {draft_count}")
    print(f"Misconception notes to draft: {misconception_note_draft_count}")
    print(f"Reviewed notes: {reviewed_count}")
    print(f"Generated exercises: {exercise_count}")
    print(f"Approved exercises: {approved_exercise_count}")
    print(f"Attempted exercises: {attempted_exercise_count}")
    print(f"Graded exercises: {graded_exercise_count}")
    print(f"Obsidian exports: {obsidian_export_count}")
    print(f"Obsidian exports to run: {obsidian_exports_to_run_count}")
    print(f"Obsidian backlinks: {obsidian_backlink_count}")
    print(f"Scheduled reviews: {scheduled_review_count}")
    if next_review is not None:
        print(
            "Next review: "
            f"{next_review['concept']} | {next_review['scheduled_for']} | "
            f"{next_review['priority']} | {next_review['reason']}"
        )
        repair = next_review.get("repair", "")
        if repair:
            print(f"Next repair: {repair}")
    print(f"Learning reports: {report_count}")
    print(f"Report history: {report_history.status}")
    print(f"Report history snapshots: {report_history.total_snapshots}")
    print(f"Latest report history: {_latest_report_history_text(report_history)}")
    print(f"Workflow actions: {workflow_action_count}")
    print(f"Quality checks to fix: {quality_checks_to_fix_count}")
    print(f"Ingestion quality check: {_quality_manifest_status_text(ingestion_quality)}")
    print(f"Note quality check: {_quality_manifest_status_text(note_quality)}")
    print(f"Exercise quality check: {_quality_manifest_status_text(exercise_quality)}")
    print(f"Exercise validation: {_quality_manifest_status_text(exercise_validation)}")
    print(f"Exercise bank entries: {exercise_bank_count}")
    print(f"Tutoring quality check: {_quality_manifest_status_text(tutoring_quality)}")
    print(f"Tool verification records: {tool_verification_count}")
    print(f"Tool verification check: {_tool_verification_quality_text(tool_verification_quality)}")
    print(f"Session score: {_session_score_status_text(session_score_status)}")
    print(f"Session score gates: {_session_score_gates_text(session_score_status)}")
    print(f"Session score failed gates: {_session_score_failed_gates_text(session_score_status)}")
    print(f"Session closeout: {_session_closeout_status_text(session_closeout_status)}")
    print(
        "Session closeout sessions: "
        f"{_session_closeout_sessions_text(session_closeout_status)}"
    )
    print(f"Session closeout score: {_session_closeout_score_text(session_closeout_status)}")
    print(
        "Multi-session regression: "
        f"{_multi_session_regression_status_text(multi_session_regression_status)}"
    )
    print(
        "Multi-session regression checks: "
        f"{_multi_session_regression_checks_text(multi_session_regression_status)}"
    )
    print(
        "Multi-session regression issues: "
        f"{_multi_session_regression_issues_text(multi_session_regression_status)}"
    )
    print(f"Next session plan: {_next_session_plan_text(next_session_plan_status)}")
    print(
        "Next session due reviews: "
        f"{_next_session_due_reviews_text(next_session_plan_status)}"
    )
    print(f"Next session handoff: {_next_session_handoff_text(next_session_plan_status)}")
    if benchmark_status is None:
        print("Benchmark score: none")
        print("Benchmark gates: none")
    elif benchmark_status.get("status") == "invalid":
        print("Benchmark score: invalid")
        print("Benchmark gates: invalid")
    else:
        print(f"Benchmark score: {benchmark_status['score']}/100")
        print(
            "Benchmark gates: "
            f"{benchmark_status['passed_gates']}/{benchmark_status['total_gates']}"
        )
        print(
            "Benchmark failed gates: "
            f"{_benchmark_failed_gates_text(benchmark_status)}"
        )
    print(f"Active misconceptions: {active_misconception_count}")
    print(f"Resolved misconceptions: {resolved_misconception_count}")
    return 0


def _handle_queue(args: argparse.Namespace) -> int:
    print(
        format_learning_queue(
            collect_learning_queue(args.project),
            section=args.section,
        ),
        end="",
    )
    return 0


def _handle_lifecycle_audit(args: argparse.Namespace) -> int:
    result = audit_project_lifecycle(args.project)
    print(
        f"Lifecycle audit passed {result.passed_checks}/{result.total_checks} checks: "
        f"{result.report_path}"
    )
    return 0 if result.passed_checks == result.total_checks else 1


def _handle_lifecycle_regression(args: argparse.Namespace) -> int:
    result = run_multi_session_regression(args.project)
    issues = ", ".join(result.issues) if result.issues else "none"
    print(f"Multi-session regression: {result.status}")
    print(f"Regression checks: {result.passed_checks}/{result.total_checks}")
    print(f"Regression issues: {issues}")
    print(f"Regression report: {result.report_path}")
    print(f"Regression manifest: {result.manifest_path}")
    return 0 if result.status == "pass" else 1


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
    kb_dir = result.index_path.parent.parent
    concept_nodes, concept_edges = _graph_counts(kb_dir / "concept_graph.json")
    dependency_nodes, dependency_edges = _graph_counts(kb_dir / "dependency_graph.json")
    noun = "object" if result.object_count == 1 else "objects"
    print(f"Indexed {result.object_count} reference {noun}")
    print(f"Concept graph: {concept_nodes} nodes, {concept_edges} edges")
    print(f"Dependency graph: {dependency_nodes} nodes, {dependency_edges} edges")
    print(f"Reference index: {result.index_path}")
    return 0


def _graph_counts(graph_path: Path) -> tuple[int, int]:
    if not graph_path.exists():
        return (0, 0)
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    nodes = graph.get("nodes", []) if isinstance(graph, dict) else []
    edges = graph.get("edges", []) if isinstance(graph, dict) else []
    node_count = len(nodes) if isinstance(nodes, list) else 0
    edge_count = len(edges) if isinstance(edges, list) else 0
    return (node_count, edge_count)


def _handle_kb_list(args: argparse.Namespace) -> int:
    _warn_if_reference_kb_stale(args.project)
    objects = list_reference_kb_objects(
        args.project,
        object_type=args.type,
        source_id=args.source_id,
    )
    print(_reference_kb_objects_text(objects), end="")
    return 0


def _reference_kb_objects_text(objects: list[dict[str, object]]) -> str:
    lines = ["# Reference KB Objects", ""]
    if not objects:
        lines.append("- none")
        return "\n".join(lines) + "\n"
    for item in objects:
        source = item.get("source", {})
        lines.append(
            f"- {_object_label(item)}{_source_label(source)} | {_source_location(source)}"
        )
        source_quality_status = str(item.get("source_quality_status", "")).strip()
        if source_quality_status:
            lines.append(f"  - source quality: {source_quality_status}")
    return "\n".join(lines) + "\n"


def _handle_kb_chapters(args: argparse.Namespace) -> int:
    _warn_if_reference_kb_stale(args.project)
    index = read_reference_chapter_index(args.project)
    print(_reference_kb_chapters_text(index), end="")
    return 0


def _reference_kb_chapters_text(index: dict[str, object]) -> str:
    lines = ["# Reference KB Chapters", ""]
    chapters = index.get("chapters", [])
    if not isinstance(chapters, list) or not chapters:
        lines.append("- none")
        return "\n".join(lines) + "\n"

    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        title = str(chapter.get("title") or "Unassigned")
        lines.append(f"## {title}")
        sections = chapter.get("sections", [])
        if not isinstance(sections, list) or not sections:
            lines.append("- none")
            continue
        for section in sections:
            if not isinstance(section, dict):
                continue
            section_title = str(section.get("title") or "Unassigned")
            source_path = str(section.get("source_path") or "unknown")
            lines.append(f"- {section_title} | {source_path}")
            objects = section.get("objects", [])
            if isinstance(objects, list):
                lines.extend(
                    f"  - {_chapter_object_label(item)} | {_chapter_object_location(item)}"
                    for item in objects
                    if isinstance(item, dict)
                )
    return "\n".join(lines) + "\n"


def _chapter_object_label(item: dict[str, object]) -> str:
    object_type = str(item.get("type") or "object")
    title = str(item.get("title") or "Untitled")
    number = str(item.get("number") or "").strip()
    if number:
        return f"{object_type} {number}: {title}"
    return f"{object_type}: {title}"


def _chapter_object_location(item: dict[str, object]) -> str:
    location = str(item.get("source_path") or "unknown")
    page = str(item.get("page") or "").strip()
    line = item.get("line")
    if page:
        location = f"{location}:p{page}"
    if line:
        location = f"{location}:{line}"
    return location


def _handle_kb_relationships(args: argparse.Namespace) -> int:
    _warn_if_reference_kb_stale(args.project)
    relationships = list_reference_kb_relationships(
        args.project,
        relationship_type=args.type,
    )
    print(_reference_kb_relationships_text(relationships), end="")
    return 0


def _reference_kb_relationships_text(relationships: list[dict[str, str]]) -> str:
    lines = ["# Reference KB Relationships", ""]
    if not relationships:
        lines.append("- none")
        return "\n".join(lines) + "\n"
    lines.extend(
        (
            f"- {relationship['source']} --{relationship['relationship']}--> "
            f"{relationship['target']}"
        )
        for relationship in relationships
    )
    return "\n".join(lines) + "\n"


def _handle_kb_search(args: argparse.Namespace) -> int:
    _warn_if_reference_kb_stale(args.project)
    matches = search_reference_kb(
        args.project,
        args.query,
        limit=args.limit,
        object_type=args.type,
        source_id=args.source_id,
        relationship_type=args.relationship_type,
    )
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
    _warn_if_reference_kb_stale(args.project)
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
    print(f"Ingestion quality manifest: {result.manifest_path}")
    return 0


def _warn_if_reference_kb_stale(project_path: Path | str) -> None:
    kb_status = reference_kb_status(project_path)
    if kb_status.status not in {"stale", "invalid", "missing"}:
        return
    print(
        f"warning: Reference KB status is {kb_status.status}; "
        f"run socrates kb build --project {project_path} to rebuild.",
        file=sys.stderr,
    )


def _handle_note_list(args: argparse.Namespace) -> int:
    notes = list_atomic_notes(args.project, status=args.status, note_type=args.type)
    print(_atomic_notes_text(notes), end="")
    return 0


def _atomic_notes_text(notes: list[AtomicNoteSummary]) -> str:
    lines = ["# Atomic Notes", ""]
    if not notes:
        lines.append("- none")
        return "\n".join(lines) + "\n"
    for note in notes:
        lines.append(
            f"- {note.note_id} | {note.status} | {note.note_type} | {note.concept} | {note.path}"
        )
        if note.quality_status:
            lines.append(f"  - quality: {note.quality_status}")
    return "\n".join(lines) + "\n"


def _handle_note_review(args: argparse.Namespace) -> int:
    reviewed = review_atomic_note(args.project, args.note)
    print(f"Reviewed note {args.note}: {reviewed}")
    return 0


def _handle_note_draft_misconceptions(args: argparse.Namespace) -> int:
    drafts = generate_misconception_note_drafts(args.project, status=args.status)
    noun = "note" if len(drafts) == 1 else "notes"
    print(f"Drafted {len(drafts)} misconception {noun}")
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
    print(f"Note quality manifest: {result.manifest_path}")
    return 0


def _handle_review_schedule(args: argparse.Namespace) -> int:
    try:
        as_of = _parse_iso_date(args.as_of) if args.as_of else date.today()
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    context = load_project(args.project)
    schedule_path = build_review_schedule(
        context,
        mastery_threshold=args.threshold,
        as_of=as_of,
    )
    count = _count_scheduled_reviews(context.learning_state)
    noun = "item" if count == 1 else "items"
    print(f"Scheduled {count} review {noun}: {schedule_path}")
    return 0


def _handle_review_exercises(args: argparse.Namespace) -> int:
    try:
        due_by = _parse_iso_date(args.due_by) if args.due_by else None
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    try:
        exercises = generate_targeted_review_exercise_drafts(
            args.project,
            due_by=due_by,
            priority=args.priority,
        )
    except json.JSONDecodeError:
        print(
            "error: invalid learning_state.json; repair the JSON before generating review exercises",
            file=sys.stderr,
        )
        return 1
    noun = "exercise" if len(exercises) == 1 else "exercises"
    print(f"Generated {len(exercises)} targeted review {noun}")
    return 0


def _handle_review_adjust_plan(args: argparse.Namespace) -> int:
    short_term_plan = adjust_short_term_plan_from_review_schedule(args.project)
    print(f"Adjusted short-term plan: {short_term_plan}")
    return 0


def _handle_review_due(args: argparse.Namespace) -> int:
    try:
        as_of = _parse_iso_date(args.as_of) if args.as_of else date.today()
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    context = load_project(args.project)
    print(_due_reviews_text(context.learning_state, as_of, priority=args.priority), end="")
    return 0


def _handle_review_repair_schedule(args: argparse.Namespace) -> int:
    try:
        as_of = _parse_iso_date(args.as_of) if args.as_of else date.today()
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    context = load_project(args.project)
    try:
        repaired_count, schedule_path = repair_review_schedule(context, as_of=as_of)
    except json.JSONDecodeError:
        print(
            "error: invalid learning_state.json; repair the JSON before repairing review schedule",
            file=sys.stderr,
        )
        return 1
    noun = "item" if repaired_count == 1 else "items"
    print(f"Repaired {repaired_count} review schedule {noun}: {schedule_path}")
    return 0


def _handle_review_resolve(args: argparse.Namespace) -> int:
    context = load_project(args.project)
    resolved_count = resolve_active_misconceptions_for_concept(context, args.concept)
    noun = "misconception" if resolved_count == 1 else "misconceptions"
    print(f"Resolved {resolved_count} active {noun} for {args.concept}")
    return 0


def _handle_review_misconceptions(args: argparse.Namespace) -> int:
    context = load_project(args.project)
    misconceptions = list_misconceptions(context, status=args.status)
    print(_misconceptions_text(misconceptions), end="")
    return 0


def _handle_review_mastery(args: argparse.Namespace) -> int:
    context = load_project(args.project)
    scores = list_learning_scores(
        context,
        score_type=args.kind,
        status=args.status,
        threshold=args.threshold,
    )
    print(_learning_scores_text(scores), end="")
    return 0


def _misconceptions_text(misconceptions: list[MisconceptionSummary]) -> str:
    lines = ["# Misconceptions", ""]
    if not misconceptions:
        lines.append("- none")
        return "\n".join(lines) + "\n"
    for item in misconceptions:
        lines.append(
            f"- {item.misconception_id} | {item.status} | "
            f"{item.concept} | x{item.count}"
        )
        if item.last_session_id:
            lines.append(f"  - Last session: {item.last_session_id}")
        if item.analysis:
            lines.append(f"  - Analysis: {item.analysis}")
        if item.repair_suggestion:
            lines.append(f"  - Repair suggestion: {item.repair_suggestion}")
        if item.follow_up_exercises:
            lines.append(
                f"  - Follow-up exercises: {', '.join(item.follow_up_exercises)}"
            )
    return "\n".join(lines) + "\n"


def _learning_scores_text(scores: list[LearningScoreSummary]) -> str:
    lines = ["# Learning Mastery", ""]
    if not scores:
        lines.append("- none")
        return "\n".join(lines) + "\n"
    lines.extend(
        f"- {item.score_type} | {item.item_id} | {item.status} | {item.score:g}"
        for item in scores
    )
    return "\n".join(lines) + "\n"


def _handle_exercise_list(args: argparse.Namespace) -> int:
    exercises = list_exercises(args.project, status=args.status, exercise_type=args.type)
    print(_exercises_text(exercises), end="")
    return 0


def _exercises_text(exercises: list[ExerciseSummary]) -> str:
    lines = ["# Exercises", ""]
    if not exercises:
        lines.append("- none")
        return "\n".join(lines) + "\n"
    for exercise in exercises:
        line = (
            f"- {exercise.exercise_id} | {exercise.status} | {exercise.exercise_type} | "
            f"{exercise.concept} | {exercise.path}"
        )
        if exercise.detail:
            line = f"{line} | {exercise.detail}"
        lines.append(line)
        if exercise.quality_status:
            lines.append(f"  - quality: {exercise.quality_status}")
    return "\n".join(lines) + "\n"


def _handle_exercise_check(args: argparse.Namespace) -> int:
    result = check_generated_exercise_quality(args.project)
    print(
        f"Checked {result.checked} exercise drafts: "
        f"{result.passed} passed, {result.failed} failed"
    )
    print(f"Exercise quality report: {result.report_path}")
    print(f"Exercise quality manifest: {result.manifest_path}")
    return 0


def _handle_exercise_validate(args: argparse.Namespace) -> int:
    if args.all:
        result = validate_project_exercises(args.project)
        print(
            f"Validated {result.checked} exercise drafts: "
            f"{result.passed} passed, {result.failed} failed"
        )
        print(f"Exercise validation checked: {result.checked}")
        print(f"Exercise validation passed: {result.passed}")
        print(f"Exercise validation failed: {result.failed}")
        print(f"Exercise validation report: {result.report_path}")
        print(f"Exercise validation manifest: {result.manifest_path}")
        return 1 if result.failed else 0

    result = validate_exercise(args.project, args.exercise)
    print(f"Exercise validation {result.exercise_id}: {result.status}")
    if result.issues:
        print("Issues:")
        for issue in result.issues:
            print(f"- {issue}")
    print(f"Exercise validation report: {result.report_path}")
    print(f"Exercise validation artifact: {result.artifact_path}")
    return 1 if result.status == "fail" else 0


def _handle_exercise_bank_build(args: argparse.Namespace) -> int:
    try:
        result = build_exercise_bank(args.project)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Exercise bank entries: {result.total_exercises}")
    print(f"Exercise bank manifest: {result.manifest_path}")
    return 0


def _handle_exercise_bank_status(args: argparse.Namespace) -> int:
    try:
        summaries = read_exercise_bank(args.project)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print("# Exercise Bank")
    print("")
    if not summaries:
        print("- none")
        return 0
    for item in summaries:
        print(
            f"- {item.exercise_id} | {item.concept} | "
            f"difficulty {item.difficulty} | {item.path}"
        )
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
    grade = grade_exercise_attempt(
        args.project,
        args.attempt,
        args.score,
        args.feedback,
        misconception_id=args.misconception,
        analysis=args.analysis,
        repair_suggestion=args.repair_suggestion,
    )
    print(f"Graded attempt {args.attempt}: {grade}")
    return 0


def _handle_exercise_suggest_feedback(args: argparse.Namespace) -> int:
    config = load_llm_config(Path.cwd())
    client = DeepSeekClient(config)
    try:
        artifact = suggest_exercise_feedback_with_llm(
            args.project,
            args.attempt,
            client=client,
        )
    except (OSError, ValueError, LlmProviderError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote LLM exercise-feedback draft: {artifact}")
    return 0


def _handle_session_list(args: argparse.Namespace) -> int:
    sessions = list_tutoring_sessions(args.project, status=args.status)
    print(_sessions_text(sessions), end="")
    return 0


def _sessions_text(sessions: list[TutoringSessionSummary]) -> str:
    lines = ["# Tutoring Sessions", ""]
    if not sessions:
        lines.append("- none")
        return "\n".join(lines) + "\n"
    for session in sessions:
        lines.append(f"- {session.session_id} | {session.status} | {session.path}")
        if session.missing_artifacts:
            lines.append(f"  - missing: {', '.join(session.missing_artifacts)}")
        else:
            lines.append("  - missing: none")
        if session.quality_status:
            quality_line = f"  - quality: {session.quality_status}"
            if session.quality_score is not None:
                quality_line += f", score {session.quality_score}/100"
            lines.append(quality_line)
    return "\n".join(lines) + "\n"


def _handle_session_check(args: argparse.Namespace) -> int:
    result = check_tutoring_session_quality(args.project, session_id=args.session_id)
    print(f"Checked session {result.session_id}: {result.status}")
    print(f"Tutoring quality report: {result.report_path}")
    print(f"Tutoring quality manifest: {result.manifest_path}")
    return 0


def _handle_session_score(args: argparse.Namespace) -> int:
    result = score_teaching_session(args.project, session_id=args.session_id)
    print(f"Scored session {result.session_id}: {result.score}/100")
    print(f"Session score gates: {result.passed_gates}/{result.total_gates}")
    print(f"Session score report: {result.report_path}")
    print(f"Session score manifest: {result.manifest_path}")
    return 0


def _handle_session_plan_next(args: argparse.Namespace) -> int:
    try:
        as_of = _parse_iso_date(args.as_of) if args.as_of else None
        result = create_next_session_plan(
            args.project,
            session_id=args.session_id,
            as_of=as_of,
        )
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Created next-session plan {result.session_id}: {result.plan_path}")
    print(f"Due reviews: {result.due_reviews}")
    if result.previous_session_id:
        print(f"Previous session: {result.previous_session_id}")
    else:
        print("Previous session: none")
    print(f"Next-session manifest: {result.manifest_path}")
    return 0


def _handle_session_closeout(args: argparse.Namespace) -> int:
    try:
        as_of = _parse_iso_date(args.as_of) if args.as_of else None
        result = close_tutoring_session(
            args.project,
            session_id=args.session_id,
            next_session_id=args.next_session_id,
            as_of=as_of,
        )
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Session closeout: {result.status}")
    print(f"Session score: {result.session_score}/100 ({result.session_score_status})")
    print(f"Next-session plan: {result.next_session_plan_path}")
    print(f"Project summary: {result.project_summary_path}")
    print(f"Closeout manifest: {result.manifest_path}")
    return 0


def _handle_session_suggest_next(args: argparse.Namespace) -> int:
    config = load_llm_config(Path.cwd())
    client = DeepSeekClient(config)
    try:
        artifact = suggest_next_question_with_llm(
            args.project,
            args.session_id,
            client=client,
        )
    except (OSError, ValueError, LlmProviderError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote LLM next-question draft: {artifact}")
    return 0


def _handle_session_judge_suggest(args: argparse.Namespace) -> int:
    config = load_llm_config(Path.cwd())
    client = DeepSeekClient(config)
    try:
        artifact = suggest_session_judge_with_llm(
            args.project,
            args.session_id,
            client=client,
        )
    except (OSError, ValueError, LlmProviderError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote LLM session-judge draft: {artifact}")
    return 0


def _handle_benchmark_run(args: argparse.Namespace) -> int:
    result = run_project_benchmark(args.project, session_id=args.session_id)
    print(f"Benchmark passed {result.passed_gates}/{result.total_gates} gates")
    print(f"Benchmark score: {result.score}/100")
    print(f"Benchmark report: {result.report_path}")
    print(f"Benchmark manifest: {result.manifest_path}")
    return 0


def _handle_benchmark_status(args: argparse.Namespace) -> int:
    context = load_project(args.project)
    print(_benchmark_status_text(context.root), end="")
    return 0


def _handle_report_list(args: argparse.Namespace) -> int:
    reports = list_learning_reports(args.project, status=args.status, report_type=args.type)
    print(_learning_reports_text(reports), end="")
    return 0


def _learning_reports_text(reports: list[ReportSummary]) -> str:
    lines = ["# Learning Reports", ""]
    if not reports:
        lines.append("- none")
        return "\n".join(lines) + "\n"
    lines.extend(
        f"- {report.report_id} | {report.status} | {report.title} | {report.path}"
        for report in reports
    )
    return "\n".join(lines) + "\n"


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


def _handle_tool_lean_skeleton(args: argparse.Namespace) -> int:
    result = generate_lean_statement_skeleton(
        args.project,
        object_id=args.object_id,
        namespace=args.namespace,
    )
    print(f"Wrote Lean skeleton: {result.skeleton_path}")
    print(f"Tool verification report: {result.report_path}")
    print(f"Tool verification manifest: {result.manifest_path}")
    print(f"Status: {result.status}")
    return 0


def _handle_tool_lean_check(args: argparse.Namespace) -> int:
    if args.timeout_seconds <= 0:
        print("error: timeout-seconds must be positive", file=sys.stderr)
        return 1
    try:
        result = check_lean_file(
            args.project,
            lean_file=args.file,
            object_id=args.object_id,
            title=args.title,
            timeout_seconds=args.timeout_seconds,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(_tool_lean_check_result_text(result), end="")
    return 0 if result.status == "lean_checked" else 1


def _tool_lean_check_result_text(result: LeanCheckResult) -> str:
    lines = [
        f"Lean check status: {result.status}",
        f"Checked: {str(result.checked).lower()}",
        f"Tool verification artifact: {result.artifact_path}",
        f"Tool verification report: {result.report_path}",
        f"Tool verification manifest: {result.manifest_path}",
    ]
    return "\n".join(lines) + "\n"


def _handle_tool_lean_deps(args: argparse.Namespace) -> int:
    try:
        result = map_lean_dependencies(args.project, object_id=args.object_id)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(_tool_lean_deps_result_text(result), end="")
    return 0


def _tool_lean_deps_result_text(result: LeanDependencyMapResult) -> str:
    lines = [
        f"Lean dependency map status: {result.status}",
        f"Dependencies: {result.dependency_count}",
        f"Resolved: {result.resolved_count}",
        f"Tool verification artifact: {result.artifact_path}",
        f"Tool verification report: {result.report_path}",
        f"Tool verification manifest: {result.manifest_path}",
    ]
    return "\n".join(lines) + "\n"


def _handle_tool_inventory(args: argparse.Namespace) -> int:
    result = write_tool_inventory(args.project)
    print(_tool_inventory_result_text(result), end="")
    return 0


def _tool_inventory_result_text(result: ToolInventoryResult) -> str:
    lines = [
        f"Tool inventory status: {result.status}",
        f"Tools available: {result.available}/{result.tools_checked}",
        f"Tool inventory report: {result.report_path}",
        f"Tool inventory manifest: {result.manifest_path}",
        f"Tool verification manifest: {result.registry_manifest_path}",
    ]
    return "\n".join(lines) + "\n"


def _handle_tool_sympy_identity(args: argparse.Namespace) -> int:
    result = verify_sympy_identity(
        args.project,
        object_id=args.object_id,
        lhs=args.lhs,
        rhs=args.rhs,
        title=args.title,
    )
    print(_tool_sympy_identity_result_text(result), end="")
    return 0 if result.status == "verified" else 1


def _tool_sympy_identity_result_text(result: SympyIdentityResult) -> str:
    lines = [
        f"SymPy identity status: {result.status}",
        f"Passed: {str(result.passed).lower()}",
        f"Tool verification artifact: {result.artifact_path}",
        f"Tool verification report: {result.report_path}",
        f"Tool verification manifest: {result.manifest_path}",
    ]
    return "\n".join(lines) + "\n"


def _handle_tool_sympy_counterexample(args: argparse.Namespace) -> int:
    try:
        samples = _parse_integer_samples(args.samples)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    result = search_sympy_counterexample(
        args.project,
        object_id=args.object_id,
        lhs=args.lhs,
        rhs=args.rhs,
        samples=samples,
        title=args.title,
    )
    print(_tool_sympy_counterexample_result_text(result), end="")
    return 0 if result.status in {"counterexample_found", "no_counterexample_found"} else 1


def _parse_integer_samples(value: str) -> tuple[int, ...]:
    try:
        samples = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    except ValueError as exc:
        raise ValueError("samples must be comma-separated integers") from exc
    if not samples:
        raise ValueError("samples must include at least one integer")
    return samples


def _tool_sympy_counterexample_result_text(result: SympyCounterexampleResult) -> str:
    lines = [
        f"SymPy counterexample status: {result.status}",
        f"Counterexample found: {str(result.counterexample_found).lower()}",
        f"Tool verification artifact: {result.artifact_path}",
        f"Tool verification report: {result.report_path}",
        f"Tool verification manifest: {result.manifest_path}",
    ]
    return "\n".join(lines) + "\n"


def _handle_tool_gap_order(args: argparse.Namespace) -> int:
    if args.expected_order <= 0:
        print("error: expected-order must be positive", file=sys.stderr)
        return 1
    if args.timeout_seconds <= 0:
        print("error: timeout-seconds must be positive", file=sys.stderr)
        return 1
    result = verify_gap_group_order(
        args.project,
        object_id=args.object_id,
        group_expression=args.group,
        expected_order=args.expected_order,
        title=args.title,
        timeout_seconds=args.timeout_seconds,
    )
    print(_tool_gap_order_result_text(result), end="")
    return 0 if result.status == "verified" else 1


def _tool_gap_order_result_text(result: GapGroupOrderResult) -> str:
    lines = [
        f"GAP group order status: {result.status}",
        f"Passed: {str(result.passed).lower()}",
        f"Tool verification artifact: {result.artifact_path}",
        f"Tool verification report: {result.report_path}",
        f"Tool verification manifest: {result.manifest_path}",
    ]
    return "\n".join(lines) + "\n"


def _handle_tool_sage_order(args: argparse.Namespace) -> int:
    if args.expected_order <= 0:
        print("error: expected-order must be positive", file=sys.stderr)
        return 1
    if args.timeout_seconds <= 0:
        print("error: timeout-seconds must be positive", file=sys.stderr)
        return 1
    result = verify_sage_group_order(
        args.project,
        object_id=args.object_id,
        group_expression=args.group,
        expected_order=args.expected_order,
        title=args.title,
        timeout_seconds=args.timeout_seconds,
    )
    print(_tool_sage_order_result_text(result), end="")
    return 0 if result.status == "verified" else 1


def _tool_sage_order_result_text(result: SageGroupOrderResult) -> str:
    lines = [
        f"Sage group order status: {result.status}",
        f"Passed: {str(result.passed).lower()}",
        f"Tool verification artifact: {result.artifact_path}",
        f"Tool verification report: {result.report_path}",
        f"Tool verification manifest: {result.manifest_path}",
    ]
    return "\n".join(lines) + "\n"


def _handle_tool_list(args: argparse.Namespace) -> int:
    records = list_tool_verification_records(args.project, status=args.status)
    print(_tool_verification_records_text(records), end="")
    return 0


def _handle_tool_check(args: argparse.Namespace) -> int:
    result = check_tool_verification_records(args.project)
    print(_tool_verification_check_text(result), end="")
    return 0 if result.status == "pass" else 1


def _tool_verification_check_text(result: ToolVerificationCheckResult) -> str:
    noun = "record" if result.checked == 1 else "records"
    lines = [
        (
            f"Checked {result.checked} tool-verification {noun}: "
            f"{result.passed} passed, {result.failed} failed"
        ),
        f"Tool verification eval report: {result.report_path}",
        f"Tool verification quality manifest: {result.manifest_path}",
    ]
    return "\n".join(lines) + "\n"


def _tool_verification_records_text(records: list[ToolVerificationSummary]) -> str:
    lines = ["# Tool Verification Records", ""]
    if not records:
        lines.append("- none")
        return "\n".join(lines) + "\n"
    for record in records:
        lines.append(
            (
                f"- {record.object_id} | {record.status} | {record.kind} | "
                f"{record.title} | {record.artifact_path}"
            )
        )
        if record.report_path:
            lines.append(f"  - report: {record.report_path}")
        if record.reference_kb_status:
            lines.append(f"  - reference_kb_status: {record.reference_kb_status}")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except ProjectExistsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
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


def _current_project_phase(
    *,
    imported_sources: int,
    converted_references: int,
    curated_references: int,
    kb_objects: int,
    latest_session: str,
    pending_draft_notes: int,
    reviewed_notes: int,
    approved_exercises: int,
    attempted_exercises: int,
    graded_exercises: int,
    obsidian_exports: int,
    obsidian_exports_to_run: int,
    scheduled_reviews: int,
    learning_reports: int,
    learning_plans: int,
    benchmark_score: int | None,
) -> str:
    if benchmark_score is not None:
        return "benchmark_ready"
    if obsidian_exports_to_run > 0:
        return "obsidian_export_pending"
    if learning_reports > 0:
        return "report_ready"
    if scheduled_reviews > 0:
        return "review_scheduled"
    if graded_exercises > 0:
        return "exercise_graded"
    if attempted_exercises > 0:
        return "exercise_attempted"
    if approved_exercises > 0:
        return "exercise_ready"
    if obsidian_exports > 0:
        return "obsidian_exported"
    if reviewed_notes > 0:
        return "notes_reviewed"
    if latest_session != "none":
        return "tutoring_complete"
    if pending_draft_notes > 0:
        return "notes_drafted"
    if kb_objects > 0:
        return "reference_kb_ready"
    if curated_references > 0:
        return "references_curated"
    if converted_references > 0:
        return "references_converted"
    if learning_plans > 0:
        return "planning_complete"
    if imported_sources > 0:
        return "references_imported"
    return "initialization"


def _count_learning_plans(learning_plan_dir: Path) -> int:
    if not learning_plan_dir.exists():
        return 0
    return len(list(learning_plan_dir.glob("*.md")))


def _count_learning_reports(project_root: Path) -> int:
    reports_dir = project_root / "07_exports" / "reports"
    if not reports_dir.exists():
        return 0
    return len(list(reports_dir.glob("*.md")))


def _latest_report_history_text(summary: ReportHistorySummary) -> str:
    if summary.latest_snapshot_id is None:
        return "none"
    return (
        f"#{summary.latest_snapshot_id} "
        f"{summary.latest_report_type} "
        f"{summary.latest_risk_level}"
    )


def _count_tool_verification_records(project_root: Path) -> int:
    manifest_path = project_root / "08_evals" / "tool_verification" / "manifest.json"
    if not manifest_path.exists():
        return 0
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return 0
    records = manifest.get("records", []) if isinstance(manifest, dict) else []
    return len(records) if isinstance(records, list) else 0


def _read_quality_manifest_status(
    project_root: Path,
    manifest_name: str,
) -> dict[str, object] | None:
    manifest_path = project_root / "08_evals" / manifest_name
    if not manifest_path.exists():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "invalid"}
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        return {"status": "invalid"}
    checked = manifest.get("checked")
    passed = manifest.get("passed")
    failed = manifest.get("failed")
    if not all(isinstance(value, int) for value in (checked, passed, failed)):
        return {"status": "invalid"}
    if checked < 0 or passed < 0 or failed < 0 or passed + failed != checked:
        return {"status": "invalid"}
    if failed > 0:
        status = "fail"
    elif checked == 0:
        status = "empty"
    elif passed == checked:
        status = "pass"
    else:
        status = "partial"
    return {
        "status": status,
        "checked": checked,
        "passed": passed,
        "failed": failed,
    }


def _quality_manifest_status_text(value: dict[str, object] | None) -> str:
    if value is None:
        return "not run"
    if value.get("status") == "invalid":
        return "invalid"
    return (
        f"{value['status']} "
        f"({value['passed']}/{value['checked']} passed, {value['failed']} failed)"
    )


def _read_exercise_validation_status(project_root: Path) -> dict[str, object] | None:
    return _read_quality_manifest_status(project_root, "exercise_validation_manifest.json")


def _read_tool_verification_quality_status(project_root: Path) -> dict[str, object] | None:
    manifest_path = project_root / "08_evals" / "tool_verification_quality_manifest.json"
    if not manifest_path.exists():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "invalid"}
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        return {"status": "invalid"}
    status = manifest.get("status")
    checked = manifest.get("checked")
    passed = manifest.get("passed")
    failed = manifest.get("failed")
    if not isinstance(status, str):
        return {"status": "invalid"}
    if not all(isinstance(value, int) for value in (checked, passed, failed)):
        return {"status": "invalid"}
    return {
        "status": status,
        "checked": checked,
        "passed": passed,
        "failed": failed,
    }


def _tool_verification_quality_text(value: dict[str, object] | None) -> str:
    if value is None:
        return "not run"
    if value.get("status") == "invalid":
        return "invalid"
    return (
        f"{value['status']} "
        f"({value['passed']}/{value['checked']} passed, {value['failed']} failed)"
    )


def _read_benchmark_status(project_root: Path) -> dict[str, object] | None:
    manifest_path = project_root / "08_evals" / "benchmark_manifest.json"
    if not manifest_path.exists():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "invalid"}
    if not isinstance(manifest, dict):
        return {"status": "invalid"}
    score = manifest.get("score")
    passed_gates = manifest.get("passed_gates")
    total_gates = manifest.get("total_gates")
    if not all(isinstance(value, int) for value in (score, passed_gates, total_gates)):
        return {"status": "invalid"}
    if score < 0 or passed_gates < 0 or total_gates <= 0:
        return {"status": "invalid"}
    return {
        "status": "current",
        "score": score,
        "passed_gates": passed_gates,
        "total_gates": total_gates,
        "failed_gates": _failed_benchmark_gates(manifest.get("gates")),
    }


def _read_session_score_status(project_root: Path) -> dict[str, object] | None:
    manifest_path = project_root / "08_evals" / "session_score_manifest.json"
    if not manifest_path.exists():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "invalid"}
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        return {"status": "invalid"}
    score = manifest.get("score")
    passed_gates = manifest.get("passed_gates")
    total_gates = manifest.get("total_gates")
    gates = manifest.get("gates")
    if not all(isinstance(value, int) for value in (score, passed_gates, total_gates)):
        return {"status": "invalid"}
    if score < 0 or passed_gates < 0 or total_gates <= 0:
        return {"status": "invalid"}
    if not isinstance(gates, list) or len(gates) != total_gates:
        return {"status": "invalid"}
    return {
        "status": str(manifest.get("status", "unknown")),
        "score": score,
        "passed_gates": passed_gates,
        "total_gates": total_gates,
        "failed_gates": _failed_benchmark_gates(gates),
    }


def _read_next_session_plan_status(project_root: Path) -> dict[str, object] | None:
    manifest_path = project_root / "02_learning_plan" / "next_session_plan_manifest.json"
    if not manifest_path.exists():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "invalid"}
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        return {"status": "invalid"}
    if manifest.get("quality_boundary") != "deterministic_handoff_plan":
        return {"status": "invalid"}
    session_id = manifest.get("session_id")
    status = manifest.get("status")
    due_reviews = manifest.get("due_reviews")
    if not isinstance(session_id, str) or not isinstance(status, str):
        return {"status": "invalid"}
    if not isinstance(due_reviews, int) or due_reviews < 0:
        return {"status": "invalid"}
    return {
        "status": status,
        "session_id": session_id,
        "due_reviews": due_reviews,
    }


def _session_score_status_text(value: dict[str, object] | None) -> str:
    if value is None:
        return "not run"
    if value.get("status") == "invalid":
        return "invalid"
    return f"{value['score']}/100"


def _session_score_gates_text(value: dict[str, object] | None) -> str:
    if value is None:
        return "none"
    if value.get("status") == "invalid":
        return "invalid"
    return f"{value['passed_gates']}/{value['total_gates']}"


def _session_score_failed_gates_text(value: dict[str, object] | None) -> str:
    if value is None:
        return "none"
    if value.get("status") == "invalid":
        return "invalid"
    failed_gates = value.get("failed_gates", [])
    if isinstance(failed_gates, list) and failed_gates:
        return ", ".join(str(name) for name in failed_gates)
    passed_gates = value.get("passed_gates")
    total_gates = value.get("total_gates")
    if (
        isinstance(passed_gates, int)
        and isinstance(total_gates, int)
        and passed_gates < total_gates
    ):
        return "unknown"
    return "none"


def _session_closeout_status_text(value: dict[str, object] | None) -> str:
    if value is None:
        return "not run"
    return str(value.get("status", "invalid"))


def _session_closeout_sessions_text(value: dict[str, object] | None) -> str:
    if value is None:
        return "none"
    if value.get("status") == "invalid":
        return "invalid"
    return f"{value['session_id']} -> {value['next_session_id']}"


def _session_closeout_score_text(value: dict[str, object] | None) -> str:
    if value is None:
        return "none"
    if value.get("status") == "invalid":
        return "invalid"
    return f"{value['session_score']}/100 ({value['session_score_status']})"


def _multi_session_regression_status_text(value: dict[str, object] | None) -> str:
    if value is None:
        return "not run"
    return str(value.get("status", "invalid"))


def _multi_session_regression_checks_text(value: dict[str, object] | None) -> str:
    if value is None:
        return "none"
    if value.get("status") == "invalid":
        return "invalid"
    return f"{value['passed_checks']}/{value['total_checks']}"


def _multi_session_regression_issues_text(value: dict[str, object] | None) -> str:
    if value is None:
        return "none"
    if value.get("status") == "invalid":
        return "invalid"
    issues = value.get("issues", [])
    if isinstance(issues, list) and issues:
        return ", ".join(str(issue) for issue in issues)
    return "none"


def _next_session_plan_text(value: dict[str, object] | None) -> str:
    if value is None:
        return "not created"
    if value.get("status") == "invalid":
        return "invalid"
    return str(value["session_id"])


def _next_session_due_reviews_text(value: dict[str, object] | None) -> str:
    if value is None:
        return "none"
    if value.get("status") == "invalid":
        return "invalid"
    return str(value["due_reviews"])


def _next_session_handoff_text(value: dict[str, object] | None) -> str:
    if value is None:
        return "not run"
    return str(value.get("status", "invalid"))


def _failed_benchmark_gates(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    failed: list[str] = []
    for gate in value:
        if not isinstance(gate, dict):
            continue
        if gate.get("passed") is not False:
            continue
        name = str(gate.get("name", "")).strip()
        if name:
            failed.append(name)
    return failed


def _count_llm_suggestion_drafts(project_path: Path) -> int:
    try:
        return sum(1 for item in list_llm_suggestions(project_path) if item.status == "draft")
    except (OSError, ValueError, json.JSONDecodeError):
        return 0


def _benchmark_failed_gates_text(benchmark_status: dict[str, object]) -> str:
    failed_gates = benchmark_status.get("failed_gates", [])
    if isinstance(failed_gates, list) and failed_gates:
        return ", ".join(str(name) for name in failed_gates)
    passed_gates = benchmark_status.get("passed_gates")
    total_gates = benchmark_status.get("total_gates")
    if (
        isinstance(passed_gates, int)
        and isinstance(total_gates, int)
        and passed_gates < total_gates
    ):
        return "unknown"
    return "none"


def _benchmark_status_text(project_root: Path) -> str:
    manifest_path = project_root / "08_evals" / "benchmark_manifest.json"
    lines = ["# Benchmark Status", ""]
    if not manifest_path.exists():
        lines.append("- not run")
        lines.append(f"- manifest: {manifest_path.relative_to(project_root).as_posix()}")
        return "\n".join(lines) + "\n"

    manifest = _read_json_object(manifest_path)
    benchmark_status = _read_benchmark_status(project_root)
    if (
        manifest is None
        or benchmark_status is None
        or benchmark_status.get("status") == "invalid"
    ):
        lines.append("- invalid manifest")
        lines.append(f"- manifest: {manifest_path.relative_to(project_root).as_posix()}")
        return "\n".join(lines) + "\n"

    lines.extend(
        [
            f"- Score: {benchmark_status['score']}/100",
            (
                "- Gates passed: "
                f"{benchmark_status['passed_gates']}/{benchmark_status['total_gates']}"
            ),
            f"- Failed gates: {_benchmark_failed_gates_text(benchmark_status)}",
            "- Report: 08_evals/benchmark_report.md",
            "- Manifest: 08_evals/benchmark_manifest.json",
            "",
            "## Gates",
            "",
        ]
    )
    gates = manifest.get("gates", [])
    if not isinstance(gates, list) or not gates:
        lines.append("- none")
        return "\n".join(lines) + "\n"
    for gate in gates:
        lines.extend(_benchmark_gate_status_lines(gate))
    return "\n".join(lines) + "\n"


def _read_json_object(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _benchmark_gate_status_lines(gate: object) -> list[str]:
    if not isinstance(gate, dict):
        return ["- invalid gate"]
    name = str(gate.get("name", "Unnamed gate"))
    status = "pass" if gate.get("passed") is True else "fail"
    checked = gate.get("checked", "unknown")
    failed = gate.get("failed", "unknown")
    lines = [f"- {name}: {status} | checked {checked} | failed {failed}"]
    report_path = gate.get("report_path")
    manifest_path = gate.get("manifest_path")
    if isinstance(report_path, str) and report_path:
        lines.append(f"  - report: {report_path}")
    if isinstance(manifest_path, str) and manifest_path:
        lines.append(f"  - manifest: {manifest_path}")
    return lines


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


def _count_exercise_bank_entries(project_root: Path) -> int:
    manifest_path = project_root / "05_exercises" / "exercise_bank_manifest.json"
    if not manifest_path.exists():
        return 0
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return 0
    records = manifest.get("records", []) if isinstance(manifest, dict) else []
    return len(records) if isinstance(records, list) else 0


def _count_scheduled_reviews(learning_state: Path) -> int:
    state = _read_learning_state_for_status(learning_state)
    schedule = state.get("review_schedule", [])
    return len(schedule) if isinstance(schedule, list) else 0


def _next_scheduled_review(learning_state: Path) -> dict[str, str] | None:
    state = _read_learning_state_for_status(learning_state)
    schedule = state.get("review_schedule", [])
    if not isinstance(schedule, list):
        return None

    rows: list[dict[str, str]] = []
    for item in schedule:
        if not isinstance(item, dict):
            continue
        scheduled_for = str(item.get("scheduled_for", "")).strip()
        if not scheduled_for:
            continue
        try:
            date.fromisoformat(scheduled_for)
        except ValueError:
            continue
        rows.append(
            {
                "concept": str(item.get("concept", "review")),
                "scheduled_for": scheduled_for,
                "priority": str(item.get("priority", "medium")),
                "reason": str(item.get("reason", "review scheduled")),
                "repair": "; ".join(
                    _due_review_repair_suggestions(item.get("repair_context", []))
                ),
            }
        )
    if not rows:
        return None
    return sorted(rows, key=lambda row: (row["scheduled_for"], row["concept"]))[0]


def _count_misconceptions_by_status(learning_state: Path) -> tuple[int, int]:
    state = _read_learning_state_for_status(learning_state)
    misconceptions = state.get("misconceptions", {})
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


def _read_learning_state_for_status(learning_state: Path) -> dict[str, object]:
    if not learning_state.exists():
        return {}
    try:
        state = json.loads(learning_state.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return state if isinstance(state, dict) else {}


def _parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"invalid ISO date {value!r}; expected YYYY-MM-DD") from exc


def _due_reviews_text(learning_state: Path, as_of: date, *, priority: str = "all") -> str:
    lines = ["# Due Reviews", ""]
    rows, invalid_rows = _due_review_rows(learning_state, as_of, priority=priority)
    if not rows:
        lines.append("- none")
    else:
        lines.extend(
            _due_review_row_text(row)
            for row in rows
        )
    if invalid_rows:
        lines.extend(["", "## Invalid Review Schedule Items", ""])
        lines.extend(
            f"- {row['concept']} | {row['scheduled_for']} | invalid scheduled_for"
            for row in invalid_rows
        )
    return "\n".join(lines) + "\n"


def _due_review_rows(
    learning_state: Path,
    as_of: date,
    *,
    priority: str = "all",
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    if not learning_state.exists():
        return ([], [])
    try:
        state = json.loads(learning_state.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            "invalid learning_state.json; repair the JSON before listing due reviews"
        ) from exc
    schedule = state.get("review_schedule", []) if isinstance(state, dict) else []
    if not isinstance(schedule, list):
        return ([], [])

    rows: list[dict[str, str]] = []
    invalid_rows: list[dict[str, str]] = []
    for item in schedule:
        if not isinstance(item, dict):
            continue
        scheduled_for = str(item.get("scheduled_for", "")).strip()
        if not scheduled_for:
            continue
        try:
            scheduled_date = date.fromisoformat(scheduled_for)
        except ValueError:
            invalid_rows.append(
                {
                    "concept": str(item.get("concept", "review")),
                    "scheduled_for": scheduled_for,
                }
            )
            continue
        if scheduled_date > as_of:
            continue
        item_priority = str(item.get("priority", "medium"))
        if priority != "all" and item_priority != priority:
            continue
        rows.append(
            {
                "concept": str(item.get("concept", "review")),
                "scheduled_for": scheduled_for,
                "priority": item_priority,
                "reason": str(item.get("reason", "review scheduled")),
                "repair": "; ".join(
                    _due_review_repair_suggestions(item.get("repair_context", []))
                ),
            }
        )
    return (
        sorted(rows, key=lambda row: (row["scheduled_for"], row["concept"])),
        sorted(invalid_rows, key=lambda row: (row["concept"], row["scheduled_for"])),
    )


def _due_review_row_text(row: dict[str, str]) -> str:
    line = (
        f"- {row['concept']} | {row['scheduled_for']} | "
        f"{row['priority']} | {row['reason']}"
    )
    repair = row.get("repair", "")
    if repair:
        line = f"{line} | repair: {repair}"
    return line


def _due_review_repair_suggestions(value: object) -> list[str]:
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
