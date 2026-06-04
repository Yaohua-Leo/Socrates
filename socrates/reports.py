"""Learning report generation for Socrates projects."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from .context import append_project_log, load_project, write_text
from .kb import reference_kb_status
from .learning_queue import (
    LearningQueue,
    QueueItem,
    action_summary_lines,
    collect_learning_queue,
    priority_queue_items,
    repair_path_items,
)
from .obsidian import (
    obsidian_backlink_count,
    obsidian_export_count,
    obsidian_exported_note_ids,
)
from .state import coerce_learning_score, coerce_occurrence_count
from .tool_verification import ToolVerificationSummary, list_tool_verification_records


@dataclass(frozen=True)
class ReportSummary:
    """A lifecycle summary for one expected learning report."""

    report_id: str
    status: str
    title: str
    path: str


@dataclass(frozen=True)
class RiskMetrics:
    """Current report risk pressure derived from queue and learning state."""

    risk_level: str
    blocker_pressure: int
    review_pressure: int
    human_review_backlog: int
    weak_concepts: int
    active_misconceptions: int


REPORT_SPECS = (
    ("weekly", "Weekly Learning Report", "weekly_report.md"),
    ("monthly", "Monthly Learning Report", "monthly_report.md"),
    ("project-summary", "Project Summary", "project_summary.md"),
)
REPORT_TYPES = frozenset(report_id for report_id, _title, _file_name in REPORT_SPECS)
_STATE_WARNING_KEY = "_state_warnings"
_RISK_HISTORY_FILE = "risk_history.json"
_RISK_HISTORY_SCHEMA_VERSION = "v0.19"


def generate_weekly_report(project_path: Path | str) -> Path:
    """Write a compact weekly report from persisted project artifacts."""

    context = load_project(project_path)
    report_path = context.root / "07_exports" / "reports" / "weekly_report.md"
    state = _read_learning_state(context.learning_state)
    queue = collect_learning_queue(context.root)
    priority_actions = priority_queue_items(queue)
    action_summary = action_summary_lines(queue)
    repair_paths = repair_path_items(queue)
    risk_metrics = _risk_metrics(queue=queue, state=state)
    risk_summary = _risk_summary_lines(risk_metrics)
    trend_summary = _trend_summary_lines(
        previous=_latest_risk_snapshot(context.root, report_type="weekly"),
        current=risk_metrics,
    )
    write_text(
        report_path,
        _weekly_report_text(
            sessions_completed=_count_dirs(context.sessions_dir),
            pending_draft_notes=len(queue.notes_to_review),
            reviewed_notes=_count_reviewed_notes(context.root),
            obsidian_exports=obsidian_export_count(context.root),
            obsidian_exports_to_run=len(queue.obsidian_exports_to_run),
            generated_exercises=_count_markdown(context.generated_exercises_dir),
            attempted_exercises=_count_markdown(context.root / "05_exercises" / "attempted"),
            graded_exercises=_count_markdown(context.root / "05_exercises" / "graded"),
            priority_actions=priority_actions,
            action_summary=action_summary,
            repair_paths=repair_paths,
            risk_summary=risk_summary,
            trend_summary=trend_summary,
            state=state,
        ),
    )
    _append_risk_history_snapshot(context.root, report_type="weekly", metrics=risk_metrics)
    append_project_log(context, "Generated weekly learning report.")
    return report_path


def generate_project_summary(project_path: Path | str) -> Path:
    """Write a project-level lifecycle snapshot from persisted artifacts."""

    context = load_project(project_path)
    report_path = context.root / "07_exports" / "reports" / "project_summary.md"
    state = _read_learning_state(context.learning_state)
    kb_status = reference_kb_status(context.root)
    queue = collect_learning_queue(context.root)
    priority_actions = priority_queue_items(queue)
    action_summary = action_summary_lines(queue)
    repair_paths = repair_path_items(queue)
    risk_metrics = _risk_metrics(queue=queue, state=state)
    risk_summary = _risk_summary_lines(risk_metrics)
    trend_summary = _trend_summary_lines(
        previous=_latest_risk_snapshot(context.root, report_type="project-summary"),
        current=risk_metrics,
    )
    write_text(
        report_path,
        _project_summary_text(
            title=_read_project_title(context.project_file),
            project_root=context.root,
            imported_sources=_count_sources(context.source_registry),
            curated_references=_count_markdown(context.references_dir / "curated"),
            kb_objects=kb_status.object_count,
            kb_status=kb_status.status,
            kb_snapshot=_read_kb_snapshot(context.root),
            sessions_completed=_count_dirs(context.sessions_dir),
            pending_draft_notes=len(queue.notes_to_review),
            reviewed_notes=_count_reviewed_notes(context.root),
            obsidian_exports=obsidian_export_count(context.root),
            obsidian_exports_to_run=len(queue.obsidian_exports_to_run),
            obsidian_backlinks=obsidian_backlink_count(context.root),
            generated_exercises=_count_markdown(context.generated_exercises_dir),
            approved_exercises=_count_approved_exercises(context.root),
            attempted_exercises=_count_markdown(context.root / "05_exercises" / "attempted"),
            graded_exercises=_count_markdown(context.root / "05_exercises" / "graded"),
            priority_actions=priority_actions,
            action_summary=action_summary,
            repair_paths=repair_paths,
            risk_summary=risk_summary,
            trend_summary=trend_summary,
            tool_verification_records=list_tool_verification_records(context.root),
            artifact_quality=_read_artifact_quality_snapshots(context.root),
            tool_verification_quality=_read_tool_verification_quality_snapshot(context.root),
            benchmark_snapshot=_read_benchmark_snapshot(context.root),
            session_score_snapshot=_read_session_score_snapshot(context.root),
            next_session_handoff_snapshot=_read_next_session_handoff_snapshot(context.root),
            state=state,
        ),
    )
    _append_risk_history_snapshot(
        context.root,
        report_type="project-summary",
        metrics=risk_metrics,
    )
    append_project_log(context, "Generated project summary report.")
    return report_path


def generate_monthly_report(project_path: Path | str) -> Path:
    """Write a monthly learning review from persisted project artifacts."""

    context = load_project(project_path)
    report_path = context.root / "07_exports" / "reports" / "monthly_report.md"
    state = _read_learning_state(context.learning_state)
    queue = collect_learning_queue(context.root)
    priority_actions = priority_queue_items(queue)
    action_summary = action_summary_lines(queue)
    repair_paths = repair_path_items(queue)
    risk_metrics = _risk_metrics(queue=queue, state=state)
    risk_summary = _risk_summary_lines(risk_metrics)
    trend_summary = _trend_summary_lines(
        previous=_latest_risk_snapshot(context.root, report_type="monthly"),
        current=risk_metrics,
    )
    write_text(
        report_path,
        _monthly_report_text(
            reviewed_notes=_count_reviewed_notes(context.root),
            draft_notes=len(queue.notes_to_review),
            obsidian_exports=obsidian_export_count(context.root),
            obsidian_exports_to_run=len(queue.obsidian_exports_to_run),
            generated_exercises=_count_markdown(context.generated_exercises_dir),
            approved_exercises=_count_approved_exercises(context.root),
            attempted_exercises=_count_markdown(context.root / "05_exercises" / "attempted"),
            graded_exercises=_count_markdown(context.root / "05_exercises" / "graded"),
            priority_actions=priority_actions,
            action_summary=action_summary,
            repair_paths=repair_paths,
            risk_summary=risk_summary,
            trend_summary=trend_summary,
            state=state,
        ),
    )
    _append_risk_history_snapshot(context.root, report_type="monthly", metrics=risk_metrics)
    append_project_log(context, "Generated monthly learning report.")
    return report_path


def list_learning_reports(
    project_path: Path | str, *, status: str = "all", report_type: str = "all"
) -> list[ReportSummary]:
    """List expected learning reports and whether they have been generated."""

    allowed_statuses = {"all", "generated", "missing", "stale"}
    if status not in allowed_statuses:
        allowed = ", ".join(sorted(allowed_statuses))
        raise ValueError(f"Unknown report status {status!r}; expected one of: {allowed}")
    allowed_types = {"all", *REPORT_TYPES}
    if report_type not in allowed_types:
        allowed = ", ".join(sorted(allowed_types))
        raise ValueError(f"Unknown report type {report_type!r}; expected one of: {allowed}")

    context = load_project(project_path)
    reports_dir = context.root / "07_exports" / "reports"
    summaries: list[ReportSummary] = []
    for report_id, title, file_name in REPORT_SPECS:
        report_path = reports_dir / file_name
        report_status = _report_status(context.root, report_id, report_path)
        summaries.append(
            ReportSummary(
                report_id=report_id,
                status=report_status,
                title=title,
                path=report_path.relative_to(context.root).as_posix(),
            )
        )
    if status != "all":
        summaries = [summary for summary in summaries if summary.status == status]
    if report_type != "all":
        summaries = [summary for summary in summaries if summary.report_id == report_type]
    return summaries


def _report_status(project_root: Path, report_id: str, report_path: Path) -> str:
    if not report_path.exists():
        return "missing"
    if _is_report_stale(project_root, report_id, report_path):
        return "stale"
    return "generated"


def _is_report_stale(project_root: Path, report_id: str, report_path: Path) -> bool:
    latest_input_mtime = _latest_report_input_mtime(project_root, report_id)
    return latest_input_mtime is not None and latest_input_mtime > report_path.stat().st_mtime_ns


def _latest_report_input_mtime(project_root: Path, report_id: str) -> int | None:
    latest: int | None = None
    for path in _report_input_paths(project_root, report_id):
        for mtime in _artifact_mtimes(path):
            latest = mtime if latest is None else max(latest, mtime)
    return latest


def _report_input_paths(project_root: Path, report_id: str) -> tuple[Path, ...]:
    if report_id == "weekly":
        return (
            project_root / "03_sessions",
            project_root / "04_atomic_notes" / "drafts",
            *_reviewed_note_input_paths(project_root),
            *_priority_action_input_paths(project_root),
            project_root / "05_exercises" / "generated",
            project_root / "05_exercises" / "attempted",
            project_root / "05_exercises" / "graded",
            project_root / "07_exports" / "obsidian",
            project_root / "00_meta" / "learning_state.json",
        )
    if report_id == "monthly":
        return (
            project_root / "04_atomic_notes",
            *_priority_action_input_paths(project_root),
            project_root / "05_exercises" / "generated",
            project_root / "05_exercises" / "attempted",
            project_root / "05_exercises" / "graded",
            project_root / "07_exports" / "obsidian",
            project_root / "00_meta" / "learning_state.json",
        )
    if report_id == "project-summary":
        return (
            project_root / "project.yaml",
            project_root / "01_references" / "source_registry.yaml",
            project_root / "01_references" / "curated",
            project_root / "03_sessions",
            project_root / "04_atomic_notes" / "drafts",
            *_reviewed_note_input_paths(project_root),
            *_priority_action_input_paths(project_root),
            project_root / "05_exercises" / "generated",
            project_root / "05_exercises" / "attempted",
            project_root / "05_exercises" / "graded",
            project_root / "06_kb" / "chunks" / "reference_index.json",
            project_root / "02_learning_plan" / "next_session_plan_manifest.json",
            project_root / "07_exports" / "obsidian",
            project_root / "08_evals" / "benchmark_manifest.json",
            project_root / "08_evals" / "session_score_manifest.json",
            project_root / "08_evals" / "ingestion_quality_manifest.json",
            project_root / "08_evals" / "note_quality_manifest.json",
            project_root / "08_evals" / "exercise_quality_manifest.json",
            project_root / "08_evals" / "tutoring_quality_manifest.json",
            project_root / "08_evals" / "tool_verification" / "manifest.json",
            project_root / "08_evals" / "tool_verification_eval.md",
            project_root / "08_evals" / "tool_verification_quality_manifest.json",
            project_root / "00_meta" / "learning_state.json",
        )
    return ()


def _reviewed_note_input_paths(project_root: Path) -> tuple[Path, ...]:
    return tuple(
        project_root / "04_atomic_notes" / folder
        for folder in (
            "definitions",
            "theorems",
            "examples",
            "counterexamples",
            "techniques",
            "exercises",
        )
    )


def _priority_action_input_paths(project_root: Path) -> tuple[Path, ...]:
    return (
        project_root / "08_evals" / "session_closeout_manifest.json",
        project_root / "08_evals" / "multi_session_regression_manifest.json",
        project_root / "08_evals" / "ingestion_quality_manifest.json",
        project_root / "08_evals" / "note_quality_manifest.json",
        project_root / "08_evals" / "exercise_quality_manifest.json",
        project_root / "08_evals" / "tutoring_quality_manifest.json",
        project_root / "08_evals" / "tool_verification_quality_manifest.json",
    )


def _artifact_mtimes(path: Path) -> list[int]:
    if not path.exists():
        return []
    mtimes = [path.stat().st_mtime_ns]
    if path.is_dir():
        mtimes.extend(item.stat().st_mtime_ns for item in path.rglob("*") if item.exists())
    return mtimes


def _weekly_report_text(
    *,
    sessions_completed: int,
    pending_draft_notes: int,
    reviewed_notes: int,
    obsidian_exports: int,
    obsidian_exports_to_run: int,
    generated_exercises: int,
    attempted_exercises: int,
    graded_exercises: int,
    priority_actions: list[QueueItem],
    action_summary: list[str],
    repair_paths: list[QueueItem],
    risk_summary: list[str],
    trend_summary: list[str],
    state: dict[str, object],
) -> str:
    lines = [
        "# Weekly Learning Report",
        "",
        "## Activity",
        "",
        f"- Sessions completed: {sessions_completed}",
        f"- Pending draft notes: {pending_draft_notes}",
        f"- Reviewed notes: {reviewed_notes}",
        f"- Obsidian exports: {obsidian_exports}",
        f"- Obsidian exports to run: {obsidian_exports_to_run}",
        f"- Generated exercises: {generated_exercises}",
        f"- Attempted exercises: {attempted_exercises}",
        f"- Graded exercises: {graded_exercises}",
        "",
        "## Priority Actions",
        "",
        *_priority_action_lines(priority_actions),
        "",
        "## Recommended Focus",
        "",
        *_recommended_focus_lines(priority_actions=priority_actions, state=state),
        "",
        "## Action Summary",
        "",
        *action_summary,
        "",
        "## Repair Paths",
        "",
        *_priority_action_lines(repair_paths),
        "",
        "## Risk Summary",
        "",
        *risk_summary,
        "",
        "## Trend Summary",
        "",
        *trend_summary,
        "",
        *_state_warning_section(state),
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


def _monthly_report_text(
    *,
    reviewed_notes: int,
    draft_notes: int,
    obsidian_exports: int,
    obsidian_exports_to_run: int,
    generated_exercises: int,
    approved_exercises: int,
    attempted_exercises: int,
    graded_exercises: int,
    priority_actions: list[QueueItem],
    action_summary: list[str],
    repair_paths: list[QueueItem],
    risk_summary: list[str],
    trend_summary: list[str],
    state: dict[str, object],
) -> str:
    concept_mastery = state.get("concept_mastery", {})
    lines = [
        "# Monthly Learning Report",
        "",
        *_state_warning_section(state),
        "## Concepts Studied",
        "",
        *_score_lines(concept_mastery),
        "",
        "## Notes And Exercises",
        "",
        f"- Draft notes: {draft_notes}",
        f"- Reviewed notes: {reviewed_notes}",
        f"- Obsidian exports: {obsidian_exports}",
        f"- Obsidian exports to run: {obsidian_exports_to_run}",
        f"- Generated exercises: {generated_exercises}",
        f"- Approved exercises: {approved_exercises}",
        f"- Attempted exercises: {attempted_exercises}",
        f"- Graded exercises: {graded_exercises}",
        "",
        "## Priority Actions",
        "",
        *_priority_action_lines(priority_actions),
        "",
        "## Recommended Focus",
        "",
        *_recommended_focus_lines(priority_actions=priority_actions, state=state),
        "",
        "## Action Summary",
        "",
        *action_summary,
        "",
        "## Repair Paths",
        "",
        *_priority_action_lines(repair_paths),
        "",
        "## Risk Summary",
        "",
        *risk_summary,
        "",
        "## Trend Summary",
        "",
        *trend_summary,
        "",
        "## Misconceptions",
        "",
        *_misconception_lines(state.get("misconceptions", {})),
        "",
        "## Weak Concepts",
        "",
        *_weak_concept_lines(concept_mastery),
        "",
        "## Recommended Next Steps",
        "",
        *_review_lines(state.get("review_schedule", [])),
    ]
    return "\n".join(lines).rstrip() + "\n"


def _project_summary_text(
    *,
    title: str,
    project_root: Path,
    imported_sources: int,
    curated_references: int,
    kb_objects: int,
    kb_status: str,
    kb_snapshot: list[dict[str, str]],
    sessions_completed: int,
    pending_draft_notes: int,
    reviewed_notes: int,
    obsidian_exports: int,
    obsidian_exports_to_run: int,
    obsidian_backlinks: int,
    generated_exercises: int,
    approved_exercises: int,
    attempted_exercises: int,
    graded_exercises: int,
    priority_actions: list[QueueItem],
    action_summary: list[str],
    repair_paths: list[QueueItem],
    risk_summary: list[str],
    trend_summary: list[str],
    tool_verification_records: list[ToolVerificationSummary],
    artifact_quality: list[dict[str, object]],
    tool_verification_quality: dict[str, object],
    benchmark_snapshot: dict[str, object],
    session_score_snapshot: dict[str, object],
    next_session_handoff_snapshot: dict[str, object],
    state: dict[str, object],
) -> str:
    lines = [
        "# Project Summary",
        "",
        "## Project",
        "",
        f"- Title: {title}",
        f"- Root: {project_root}",
        "",
        *_state_warning_section(state),
        "## Artifact Inventory",
        "",
        f"- Imported sources: {imported_sources}",
        f"- Curated references: {curated_references}",
        f"- KB objects: {kb_objects}",
        f"- Reference KB status: {kb_status}",
        f"- Sessions completed: {sessions_completed}",
        f"- Pending draft notes: {pending_draft_notes}",
        f"- Reviewed notes: {reviewed_notes}",
        f"- Obsidian exports: {obsidian_exports}",
        f"- Obsidian exports to run: {obsidian_exports_to_run}",
        f"- Obsidian backlinks: {obsidian_backlinks}",
        f"- Generated exercises: {generated_exercises}",
        f"- Approved exercises: {approved_exercises}",
        f"- Attempted exercises: {attempted_exercises}",
        f"- Graded exercises: {graded_exercises}",
        f"- Tool verification records: {len(tool_verification_records)}",
        "",
        "## Priority Actions",
        "",
        *_priority_action_lines(priority_actions),
        "",
        "## Recommended Focus",
        "",
        *_recommended_focus_lines(priority_actions=priority_actions, state=state),
        "",
        "## Action Summary",
        "",
        *action_summary,
        "",
        "## Repair Paths",
        "",
        *_priority_action_lines(repair_paths),
        "",
        "## Risk Summary",
        "",
        *risk_summary,
        "",
        "## Trend Summary",
        "",
        *trend_summary,
        "",
        "## Benchmark Snapshot",
        "",
        *_benchmark_snapshot_lines(benchmark_snapshot),
        "",
        "## Session Score Snapshot",
        "",
        *_session_score_snapshot_lines(session_score_snapshot),
        "",
        "## Next Session Handoff Snapshot",
        "",
        *_next_session_handoff_snapshot_lines(next_session_handoff_snapshot),
        "",
        "## Artifact Quality Snapshot",
        "",
        *_artifact_quality_snapshot_lines(artifact_quality),
        "",
        "## Tool Verification Snapshot",
        "",
        *_tool_verification_snapshot_lines(
            tool_verification_records,
            quality=tool_verification_quality,
        ),
        "",
        "## Reference KB Snapshot",
        "",
        *_kb_snapshot_lines(kb_snapshot),
        "",
        "## Current Learning State",
        "",
        *_score_lines(state.get("concept_mastery", {})),
        "",
        "## Proof Skills",
        "",
        *_score_lines(state.get("proof_skills", {})),
        "",
        "## Next Review Items",
        "",
        *_review_lines(state.get("review_schedule", [])),
    ]
    return "\n".join(lines).rstrip() + "\n"


def _read_learning_state(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            _STATE_WARNING_KEY: [
                "invalid learning_state.json; repair the JSON to restore learning-state sections."
            ]
        }
    return loaded if isinstance(loaded, dict) else {}


def _read_project_title(project_file: Path) -> str:
    in_project = False
    for line in project_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not line.startswith(" ") and stripped.endswith(":"):
            in_project = stripped == "project:"
            continue
        if in_project and stripped.startswith("title:"):
            title = _yaml_like_string(stripped.removeprefix("title:").strip())
            if title:
                return title
    return "Untitled Project"


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


def _count_obsidian_exports_to_run(project_root: Path) -> int:
    notes_root = project_root / "04_atomic_notes"
    if not notes_root.exists():
        return 0
    exported_ids = obsidian_exported_note_ids(project_root)
    pending = 0
    for folder in notes_root.iterdir():
        if not folder.is_dir() or folder.name == "drafts":
            continue
        for note_path in folder.glob("*.md"):
            if note_path.stem in exported_ids:
                continue
            if "reviewed_by_user: true" in note_path.read_text(encoding="utf-8"):
                pending += 1
    return pending


def _count_sources(registry_path: Path) -> int:
    if not registry_path.exists():
        return 0
    return sum(
        1
        for line in registry_path.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("- id:")
    )


def _read_kb_snapshot(project_root: Path, *, limit: int = 10) -> list[dict[str, str]]:
    index_path = project_root / "06_kb" / "chunks" / "reference_index.json"
    if not index_path.exists():
        return []
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    objects = index.get("objects", []) if isinstance(index, dict) else []
    if not isinstance(objects, list):
        return []
    snapshot: list[dict[str, str]] = []
    for item in objects:
        if not isinstance(item, dict):
            continue
        source = item.get("source", {})
        if not isinstance(source, dict):
            source = {}
        snapshot.append(
            {
                "label": _kb_object_label(item),
                "source_label": _kb_source_label(source),
                "location": _kb_source_location(source),
            }
        )
        if len(snapshot) >= limit:
            break
    return snapshot


def _read_benchmark_snapshot(project_root: Path) -> dict[str, object]:
    manifest_path = project_root / "08_evals" / "benchmark_manifest.json"
    if not manifest_path.exists():
        return {"status": "not_run"}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "invalid"}
    if not isinstance(manifest, dict):
        return {"status": "invalid"}
    score = manifest.get("score")
    passed_gates = manifest.get("passed_gates")
    total_gates = manifest.get("total_gates")
    gates = manifest.get("gates", [])
    if not all(isinstance(value, int) for value in (score, passed_gates, total_gates)):
        return {"status": "invalid"}
    return {
        "status": "ready",
        "score": score,
        "passed_gates": passed_gates,
        "total_gates": total_gates,
        "failed_gates": _failed_benchmark_gates(gates),
    }


def _read_session_score_snapshot(project_root: Path) -> dict[str, object]:
    manifest_path = project_root / "08_evals" / "session_score_manifest.json"
    if not manifest_path.exists():
        return {"status": "not_run"}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "invalid"}
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        return {"status": "invalid"}
    session_id = manifest.get("session_id")
    score = manifest.get("score")
    passed_gates = manifest.get("passed_gates")
    total_gates = manifest.get("total_gates")
    gates = manifest.get("gates", [])
    if not isinstance(session_id, str):
        return {"status": "invalid"}
    if not all(isinstance(value, int) for value in (score, passed_gates, total_gates)):
        return {"status": "invalid"}
    if not isinstance(gates, list) or len(gates) != total_gates:
        return {"status": "invalid"}
    return {
        "status": "ready",
        "session_id": session_id,
        "score": score,
        "passed_gates": passed_gates,
        "total_gates": total_gates,
        "failed_gates": _failed_benchmark_gates(gates),
    }


def _read_next_session_handoff_snapshot(project_root: Path) -> dict[str, object]:
    manifest_path = project_root / "02_learning_plan" / "next_session_plan_manifest.json"
    if not manifest_path.exists():
        return {"status": "not_run"}
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
    previous_session_id = manifest.get("previous_session_id")
    invalid_review_items = manifest.get("invalid_review_items")
    if not isinstance(session_id, str) or not isinstance(status, str):
        return {"status": "invalid"}
    if not isinstance(due_reviews, int) or due_reviews < 0:
        return {"status": "invalid"}
    if previous_session_id is not None and not isinstance(previous_session_id, str):
        return {"status": "invalid"}
    if not isinstance(invalid_review_items, int) or invalid_review_items < 0:
        return {"status": "invalid"}
    return {
        "status": status,
        "session_id": session_id,
        "due_reviews": due_reviews,
        "previous_session_id": previous_session_id,
        "invalid_review_items": invalid_review_items,
    }


def _read_artifact_quality_snapshots(project_root: Path) -> list[dict[str, object]]:
    specs = (
        ("Ingestion", "ingestion_quality_manifest.json"),
        ("Note quality", "note_quality_manifest.json"),
        ("Exercise quality", "exercise_quality_manifest.json"),
        ("Tutoring quality", "tutoring_quality_manifest.json"),
    )
    return [
        _read_artifact_quality_snapshot(project_root, label=label, manifest_name=manifest_name)
        for label, manifest_name in specs
    ]


def _read_artifact_quality_snapshot(
    project_root: Path,
    *,
    label: str,
    manifest_name: str,
) -> dict[str, object]:
    relative_path = f"08_evals/{manifest_name}"
    manifest_path = project_root / relative_path
    if not manifest_path.exists():
        return {"label": label, "status": "not_run", "path": relative_path}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"label": label, "status": "invalid", "path": relative_path}
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        return {"label": label, "status": "invalid", "path": relative_path}
    checked = manifest.get("checked")
    passed = manifest.get("passed")
    failed = manifest.get("failed")
    if not all(isinstance(value, int) for value in (checked, passed, failed)):
        return {"label": label, "status": "invalid", "path": relative_path}
    if checked < 0 or passed < 0 or failed < 0 or passed + failed != checked:
        return {"label": label, "status": "invalid", "path": relative_path}
    if failed > 0:
        status = "fail"
    elif checked == 0:
        status = "empty"
    elif passed == checked:
        status = "pass"
    else:
        status = "partial"
    return {
        "label": label,
        "status": status,
        "checked": checked,
        "passed": passed,
        "failed": failed,
        "path": relative_path,
    }


def _read_tool_verification_quality_snapshot(project_root: Path) -> dict[str, object]:
    manifest_path = project_root / "08_evals" / "tool_verification_quality_manifest.json"
    if not manifest_path.exists():
        return {"status": "not_run"}
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


def _count_approved_exercises(project_root: Path) -> int:
    generated_root = project_root / "05_exercises" / "generated"
    if not generated_root.exists():
        return 0
    approved = 0
    for exercise_path in generated_root.glob("*.md"):
        text = exercise_path.read_text(encoding="utf-8")
        if 'status: "approved"' in text and "reviewed_by_user: true" in text:
            approved += 1
    return approved


def _state_warning_section(state: dict[str, object]) -> list[str]:
    warnings = state.get(_STATE_WARNING_KEY, [])
    if not isinstance(warnings, list):
        return []
    warning_lines = [f"- {warning}" for warning in warnings if str(warning).strip()]
    if not warning_lines:
        return []
    return ["## State Warnings", "", *warning_lines, ""]


def _priority_action_lines(items: list[QueueItem], *, limit: int = 5) -> list[str]:
    if not items:
        return ["- none"]
    lines = [_priority_action_line(item) for item in items[:limit]]
    remaining = len(items) - limit
    if remaining > 0:
        lines.append(f"- ... {remaining} more")
    return lines


def _priority_action_line(item: QueueItem) -> str:
    line = f"- {item.item_id} | {item.path}"
    if item.detail:
        line = f"{line} | {item.detail}"
    return line


def _recommended_focus_lines(
    *,
    priority_actions: list[QueueItem],
    state: dict[str, object],
) -> list[str]:
    return [
        f"- Next action: {_next_action_focus(priority_actions)}",
        f"- Weak concept: {_weakest_concept_focus(state.get('concept_mastery', {}))}",
        f"- Next review: {_next_review_focus(state.get('review_schedule', []))}",
        (
            "- Active misconception: "
            f"{_active_misconception_focus(state.get('misconceptions', {}))}"
        ),
    ]


def _risk_metrics(*, queue: LearningQueue, state: dict[str, object]) -> RiskMetrics:
    blocker_pressure = (
        len(queue.workflow_actions)
        + len(queue.quality_checks_to_fix)
        + len(queue.tool_verifications_to_fix)
    )
    review_pressure = len(queue.scheduled_reviews)
    human_review_backlog = (
        len(queue.obsidian_exports_to_run)
        + len(queue.notes_to_review)
        + len(queue.misconception_notes_to_draft)
        + len(queue.exercise_drafts_to_approve)
        + len(queue.attempts_to_grade)
    )
    weak_concepts = _weak_concept_count(state.get("concept_mastery", {}))
    active_misconceptions = _active_misconception_count(state.get("misconceptions", {}))
    risk_level = _risk_level(
        blocker_pressure=blocker_pressure,
        review_pressure=review_pressure,
        human_review_backlog=human_review_backlog,
        weak_concepts=weak_concepts,
        active_misconceptions=active_misconceptions,
    )
    return RiskMetrics(
        risk_level=risk_level,
        blocker_pressure=blocker_pressure,
        review_pressure=review_pressure,
        human_review_backlog=human_review_backlog,
        weak_concepts=weak_concepts,
        active_misconceptions=active_misconceptions,
    )


def _risk_summary_lines(metrics: RiskMetrics) -> list[str]:
    return [
        f"- Risk level: {metrics.risk_level}",
        f"- Blocker pressure: {metrics.blocker_pressure}",
        f"- Review pressure: {metrics.review_pressure}",
        f"- Human review backlog: {metrics.human_review_backlog}",
        f"- Weak concepts: {metrics.weak_concepts}",
        f"- Active misconceptions: {metrics.active_misconceptions}",
    ]


def _trend_summary_lines(
    *,
    previous: dict[str, object] | None,
    current: RiskMetrics,
) -> list[str]:
    if previous is None:
        return [
            "- Previous snapshot: none",
            "- Risk level change: baseline",
            "- Blocker pressure change: baseline",
            "- Review pressure change: baseline",
            "- Human review backlog change: baseline",
            "- Weak concepts change: baseline",
            "- Active misconceptions change: baseline",
        ]
    return [
        f"- Previous snapshot: {_snapshot_id_label(previous.get('snapshot_id'))}",
        f"- Risk level change: {previous.get('risk_level', 'unknown')} -> {current.risk_level}",
        (
            "- Blocker pressure change: "
            f"{_risk_delta(current.blocker_pressure, previous.get('blocker_pressure'))}"
        ),
        (
            "- Review pressure change: "
            f"{_risk_delta(current.review_pressure, previous.get('review_pressure'))}"
        ),
        (
            "- Human review backlog change: "
            f"{_risk_delta(current.human_review_backlog, previous.get('human_review_backlog'))}"
        ),
        f"- Weak concepts change: {_risk_delta(current.weak_concepts, previous.get('weak_concepts'))}",
        (
            "- Active misconceptions change: "
            f"{_risk_delta(current.active_misconceptions, previous.get('active_misconceptions'))}"
        ),
    ]


def _risk_delta(current: int, previous: object) -> str:
    delta = current - _snapshot_int(previous)
    return "0" if delta == 0 else f"{delta:+d}"


def _snapshot_id_label(value: object) -> str:
    snapshot_id = _snapshot_int(value)
    return str(snapshot_id) if snapshot_id else "unknown"


def _risk_history_path(project_root: Path) -> Path:
    return project_root / "07_exports" / "reports" / _RISK_HISTORY_FILE


def _read_risk_history(project_root: Path) -> list[dict[str, object]]:
    history_path = _risk_history_path(project_root)
    if not history_path.exists():
        return []
    try:
        loaded = json.loads(history_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(loaded, dict):
        return []
    if loaded.get("schema_version") != _RISK_HISTORY_SCHEMA_VERSION:
        return []
    snapshots = loaded.get("snapshots", [])
    if not isinstance(snapshots, list):
        return []
    return [snapshot for snapshot in snapshots if isinstance(snapshot, dict)]


def _latest_risk_snapshot(
    project_root: Path,
    *,
    report_type: str,
) -> dict[str, object] | None:
    for snapshot in reversed(_read_risk_history(project_root)):
        if snapshot.get("report_type") == report_type:
            return snapshot
    return None


def _append_risk_history_snapshot(
    project_root: Path,
    *,
    report_type: str,
    metrics: RiskMetrics,
) -> None:
    snapshots = _read_risk_history(project_root)
    snapshot_id = max((_snapshot_int(item.get("snapshot_id")) for item in snapshots), default=0) + 1
    snapshots.append(
        {
            "snapshot_id": snapshot_id,
            "report_type": report_type,
            "risk_level": metrics.risk_level,
            "blocker_pressure": metrics.blocker_pressure,
            "review_pressure": metrics.review_pressure,
            "human_review_backlog": metrics.human_review_backlog,
            "weak_concepts": metrics.weak_concepts,
            "active_misconceptions": metrics.active_misconceptions,
        }
    )
    payload = {
        "schema_version": _RISK_HISTORY_SCHEMA_VERSION,
        "snapshots": snapshots[-50:],
    }
    write_text(_risk_history_path(project_root), json.dumps(payload, indent=2) + "\n")


def _snapshot_int(value: object) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0


def _risk_level(
    *,
    blocker_pressure: int,
    review_pressure: int,
    human_review_backlog: int,
    weak_concepts: int,
    active_misconceptions: int,
) -> str:
    if blocker_pressure:
        return "blocked"
    if review_pressure or human_review_backlog or weak_concepts or active_misconceptions:
        return "attention"
    return "clear"


def _weak_concept_count(value: object, *, threshold: float = 0.7) -> int:
    if not isinstance(value, dict):
        return 0
    return sum(
        1
        for concept, score in value.items()
        if str(concept).strip() and coerce_learning_score(score) < threshold
    )


def _active_misconception_count(value: object) -> int:
    if not isinstance(value, dict):
        return 0
    active_count = 0
    for item in value.values():
        if not isinstance(item, dict):
            continue
        status = str(item.get("status", "active")).strip() or "active"
        if status == "active":
            active_count += coerce_occurrence_count(item.get("count", 1))
    return active_count


def _next_action_focus(priority_actions: list[QueueItem]) -> str:
    if not priority_actions:
        return "none"
    return _priority_action_line(priority_actions[0]).removeprefix("- ")


def _weakest_concept_focus(value: object) -> str:
    if not isinstance(value, dict) or not value:
        return "none recorded"
    rows = [
        (coerce_learning_score(score), str(concept))
        for concept, score in value.items()
        if str(concept).strip()
    ]
    if not rows:
        return "none recorded"
    score, concept = sorted(rows, key=lambda row: (row[0], row[1]))[0]
    return f"{concept}: {score:g}"


def _next_review_focus(value: object) -> str:
    if not isinstance(value, list) or not value:
        return "none scheduled"
    rows: list[tuple[str, str, str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        concept = str(item.get("concept", "review")).strip() or "review"
        priority = str(item.get("priority", "medium")).strip() or "medium"
        scheduled_for = str(item.get("scheduled_for", "")).strip()
        due = str(item.get("due", "")).strip()
        when = scheduled_for or due or "unscheduled"
        sort_when = scheduled_for or "9999-99-99"
        rows.append((sort_when, concept, priority, when))
    if not rows:
        return "none scheduled"
    _sort_when, concept, priority, when = sorted(rows)[0]
    return f"{concept} | {priority} | {when}"


def _active_misconception_focus(value: object) -> str:
    if not isinstance(value, dict) or not value:
        return "none recorded"
    for misconception_id, item in sorted(value.items(), key=lambda pair: str(pair[0])):
        if not isinstance(item, dict):
            continue
        status = str(item.get("status", "active")).strip() or "active"
        if status != "active":
            continue
        concept = str(item.get("concept", "general")).strip() or "general"
        count = coerce_occurrence_count(item.get("count", 1))
        return f"{misconception_id} | {concept} | {status} x{count}"
    return "none recorded"


def _score_lines(value: object) -> list[str]:
    if not isinstance(value, dict) or not value:
        return ["- none recorded"]
    return [f"- {key}: {coerce_learning_score(score):g}" for key, score in sorted(value.items())]


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
        scheduled_for = str(item.get("scheduled_for", "")).strip()
        reason = str(item.get("reason", "review scheduled"))
        date_label = f", {scheduled_for}" if scheduled_for else ""
        lines.append(f"- {concept}: {priority}, {due}{date_label} - {reason}")
        for suggestion in _review_repair_suggestions(item.get("repair_context", [])):
            lines.append(f"  - Repair suggestion: {suggestion}")
    return lines or ["- none scheduled"]


def _review_repair_suggestions(value: object) -> list[str]:
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


def _kb_snapshot_lines(snapshot: list[dict[str, str]]) -> list[str]:
    if not snapshot:
        return ["- none indexed"]
    lines: list[str] = []
    for item in snapshot:
        source_label = item["source_label"]
        label = item["label"]
        lines.append(f"- {label}{source_label}")
        location = item["location"]
        if location:
            lines.append(f"  Source: {location}")
    return lines


def _benchmark_snapshot_lines(snapshot: dict[str, object]) -> list[str]:
    status = snapshot.get("status")
    if status == "not_run":
        return ["- not run"]
    if status != "ready":
        return ["- invalid benchmark manifest"]
    failed_gates = snapshot.get("failed_gates", [])
    failed_text = (
        ", ".join(str(name) for name in failed_gates)
        if isinstance(failed_gates, list) and failed_gates
        else "none"
    )
    return [
        f"- Score: {snapshot['score']}/100",
        f"- Gates passed: {snapshot['passed_gates']}/{snapshot['total_gates']}",
        f"- Failed gates: {failed_text}",
        "- Manifest: 08_evals/benchmark_manifest.json",
    ]


def _session_score_snapshot_lines(snapshot: dict[str, object]) -> list[str]:
    status = snapshot.get("status")
    if status == "not_run":
        return ["- not run"]
    if status != "ready":
        return ["- invalid session score manifest"]
    failed_gates = snapshot.get("failed_gates", [])
    failed_text = (
        ", ".join(str(name) for name in failed_gates)
        if isinstance(failed_gates, list) and failed_gates
        else "none"
    )
    return [
        f"- Session: {snapshot['session_id']}",
        f"- Score: {snapshot['score']}/100",
        f"- Gates passed: {snapshot['passed_gates']}/{snapshot['total_gates']}",
        f"- Failed gates: {failed_text}",
        "- Manifest: 08_evals/session_score_manifest.json",
    ]


def _next_session_handoff_snapshot_lines(snapshot: dict[str, object]) -> list[str]:
    status = snapshot.get("status")
    if status == "not_run":
        return ["- not run"]
    if status == "invalid":
        return ["- invalid next-session handoff manifest"]
    previous_session_id = snapshot.get("previous_session_id") or "none"
    return [
        f"- Session: {snapshot['session_id']}",
        f"- Status: {snapshot['status']}",
        f"- Due reviews: {snapshot['due_reviews']}",
        f"- Previous session: {previous_session_id}",
        f"- Invalid review items: {snapshot['invalid_review_items']}",
        "- Manifest: 02_learning_plan/next_session_plan_manifest.json",
    ]


def _artifact_quality_snapshot_lines(snapshots: list[dict[str, object]]) -> list[str]:
    if not snapshots:
        return ["- none configured"]
    return [_artifact_quality_snapshot_line(snapshot) for snapshot in snapshots]


def _artifact_quality_snapshot_line(snapshot: dict[str, object]) -> str:
    label = str(snapshot.get("label", "Artifact quality"))
    path = str(snapshot.get("path", "")).strip()
    suffix = f" - {path}" if path else ""
    status = snapshot.get("status")
    if status == "not_run":
        return f"- {label}: not run{suffix}"
    if status == "invalid":
        return f"- {label}: invalid manifest{suffix}"
    return (
        f"- {label}: {status} "
        f"({snapshot['passed']}/{snapshot['checked']} passed, "
        f"{snapshot['failed']} failed){suffix}"
    )


def _tool_verification_snapshot_lines(
    records: list[ToolVerificationSummary],
    *,
    quality: dict[str, object],
) -> list[str]:
    lines = _tool_verification_quality_lines(quality)
    if not records:
        return [*lines, "- Records: none"]
    lines.extend(
        (
            f"- {record.object_id}: {record.status}, {record.kind}"
            f" -> {record.artifact_path}"
        )
        for record in records
    )
    return lines


def _tool_verification_quality_lines(snapshot: dict[str, object]) -> list[str]:
    status = snapshot.get("status")
    if status == "not_run":
        return ["- Check: not run"]
    if status == "invalid":
        return ["- Check: invalid quality manifest"]
    return [
        (
            f"- Check: {status} "
            f"({snapshot['passed']}/{snapshot['checked']} passed, {snapshot['failed']} failed)"
        ),
        "- Quality manifest: 08_evals/tool_verification_quality_manifest.json",
    ]


def _failed_benchmark_gates(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    failed: list[str] = []
    for gate in value:
        if not isinstance(gate, dict) or gate.get("passed") is not False:
            continue
        name = str(gate.get("name", "")).strip()
        if name:
            failed.append(name)
    return failed


def _kb_object_label(item: dict[str, object]) -> str:
    object_type = str(item.get("type", "object")).title()
    number = str(item.get("number", "")).strip()
    title = str(item.get("title", "Untitled"))
    if number:
        return f"{object_type} {number}: {title}"
    return f"{object_type}: {title}"


def _kb_source_label(source: dict[object, object]) -> str:
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
    if source_id:
        return f" [{source_id}]"
    return ""


def _kb_source_location(source: dict[object, object]) -> str:
    path = str(source.get("path", "")).strip()
    if not path:
        return ""
    page = str(source.get("page", "")).strip()
    line = source.get("line")
    if page and line:
        return f"{path}:p{page}:{line}"
    if page:
        return f"{path}:p{page}"
    if line:
        return f"{path}:{line}"
    return path


def _misconception_lines(value: object) -> list[str]:
    if not isinstance(value, dict) or not value:
        return ["- none recorded"]
    lines: list[str] = []
    for misconception_id, item in sorted(value.items()):
        if not isinstance(item, dict):
            continue
        concept = str(item.get("concept", "general"))
        status = str(item.get("status", "active"))
        count = coerce_occurrence_count(item.get("count", 1))
        lines.append(f"- {misconception_id}: {concept}, {status} x{count}")
    return lines or ["- none recorded"]


def _weak_concept_lines(value: object, *, threshold: float = 0.7) -> list[str]:
    if not isinstance(value, dict) or not value:
        return ["- none below threshold"]
    lines: list[str] = []
    for concept, score_value in sorted(value.items()):
        score = coerce_learning_score(score_value)
        if score < threshold:
            lines.append(f"- {concept}: {score:g}")
    return lines or ["- none below threshold"]


def _yaml_like_string(value: str) -> str:
    if value == "null":
        return ""
    if value.startswith('"') and value.endswith('"'):
        return str(json.loads(value))
    return value
