"""Learning report generation for Socrates projects."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from .context import append_project_log, load_project, write_text


@dataclass(frozen=True)
class ReportSummary:
    """A lifecycle summary for one expected learning report."""

    report_id: str
    status: str
    title: str
    path: str


REPORT_SPECS = (
    ("weekly", "Weekly Learning Report", "weekly_report.md"),
    ("monthly", "Monthly Learning Report", "monthly_report.md"),
    ("project-summary", "Project Summary", "project_summary.md"),
)


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


def generate_project_summary(project_path: Path | str) -> Path:
    """Write a project-level lifecycle snapshot from persisted artifacts."""

    context = load_project(project_path)
    report_path = context.root / "07_exports" / "reports" / "project_summary.md"
    state = _read_learning_state(context.learning_state)
    write_text(
        report_path,
        _project_summary_text(
            title=_read_project_title(context.project_file),
            project_root=context.root,
            imported_sources=_count_sources(context.source_registry),
            curated_references=_count_markdown(context.references_dir / "curated"),
            kb_objects=_count_kb_objects(context.root),
            kb_snapshot=_read_kb_snapshot(context.root),
            sessions_completed=_count_dirs(context.sessions_dir),
            reviewed_notes=_count_reviewed_notes(context.root),
            obsidian_exports=_count_obsidian_exports(context.root),
            generated_exercises=_count_markdown(context.generated_exercises_dir),
            approved_exercises=_count_approved_exercises(context.root),
            attempted_exercises=_count_markdown(context.root / "05_exercises" / "attempted"),
            graded_exercises=_count_markdown(context.root / "05_exercises" / "graded"),
            benchmark_snapshot=_read_benchmark_snapshot(context.root),
            state=state,
        ),
    )
    append_project_log(context, "Generated project summary report.")
    return report_path


def generate_monthly_report(project_path: Path | str) -> Path:
    """Write a monthly learning review from persisted project artifacts."""

    context = load_project(project_path)
    report_path = context.root / "07_exports" / "reports" / "monthly_report.md"
    state = _read_learning_state(context.learning_state)
    write_text(
        report_path,
        _monthly_report_text(
            reviewed_notes=_count_reviewed_notes(context.root),
            draft_notes=_count_markdown(context.atomic_note_drafts_dir),
            obsidian_exports=_count_obsidian_exports(context.root),
            generated_exercises=_count_markdown(context.generated_exercises_dir),
            approved_exercises=_count_approved_exercises(context.root),
            attempted_exercises=_count_markdown(context.root / "05_exercises" / "attempted"),
            graded_exercises=_count_markdown(context.root / "05_exercises" / "graded"),
            state=state,
        ),
    )
    append_project_log(context, "Generated monthly learning report.")
    return report_path


def list_learning_reports(project_path: Path | str, *, status: str = "all") -> list[ReportSummary]:
    """List expected learning reports and whether they have been generated."""

    allowed_statuses = {"all", "generated", "missing"}
    if status not in allowed_statuses:
        allowed = ", ".join(sorted(allowed_statuses))
        raise ValueError(f"Unknown report status {status!r}; expected one of: {allowed}")

    context = load_project(project_path)
    reports_dir = context.root / "07_exports" / "reports"
    summaries: list[ReportSummary] = []
    for report_id, title, file_name in REPORT_SPECS:
        report_path = reports_dir / file_name
        report_status = "generated" if report_path.exists() else "missing"
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
    return summaries


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


def _monthly_report_text(
    *,
    reviewed_notes: int,
    draft_notes: int,
    obsidian_exports: int,
    generated_exercises: int,
    approved_exercises: int,
    attempted_exercises: int,
    graded_exercises: int,
    state: dict[str, object],
) -> str:
    concept_mastery = state.get("concept_mastery", {})
    lines = [
        "# Monthly Learning Report",
        "",
        "## Concepts Studied",
        "",
        *_score_lines(concept_mastery),
        "",
        "## Notes And Exercises",
        "",
        f"- Draft notes: {draft_notes}",
        f"- Reviewed notes: {reviewed_notes}",
        f"- Obsidian exports: {obsidian_exports}",
        f"- Generated exercises: {generated_exercises}",
        f"- Approved exercises: {approved_exercises}",
        f"- Attempted exercises: {attempted_exercises}",
        f"- Graded exercises: {graded_exercises}",
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
    kb_snapshot: list[dict[str, str]],
    sessions_completed: int,
    reviewed_notes: int,
    obsidian_exports: int,
    generated_exercises: int,
    approved_exercises: int,
    attempted_exercises: int,
    graded_exercises: int,
    benchmark_snapshot: dict[str, object],
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
        "## Artifact Inventory",
        "",
        f"- Imported sources: {imported_sources}",
        f"- Curated references: {curated_references}",
        f"- KB objects: {kb_objects}",
        f"- Sessions completed: {sessions_completed}",
        f"- Reviewed notes: {reviewed_notes}",
        f"- Obsidian exports: {obsidian_exports}",
        f"- Generated exercises: {generated_exercises}",
        f"- Approved exercises: {approved_exercises}",
        f"- Attempted exercises: {attempted_exercises}",
        f"- Graded exercises: {graded_exercises}",
        "",
        "## Benchmark Snapshot",
        "",
        *_benchmark_snapshot_lines(benchmark_snapshot),
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
    loaded = json.loads(path.read_text(encoding="utf-8"))
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


def _count_sources(registry_path: Path) -> int:
    if not registry_path.exists():
        return 0
    return sum(
        1
        for line in registry_path.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("- id:")
    )


def _count_kb_objects(project_root: Path) -> int:
    index_path = project_root / "06_kb" / "chunks" / "reference_index.json"
    if not index_path.exists():
        return 0
    index = json.loads(index_path.read_text(encoding="utf-8"))
    objects = index.get("objects", []) if isinstance(index, dict) else []
    return len(objects) if isinstance(objects, list) else 0


def _read_kb_snapshot(project_root: Path, *, limit: int = 10) -> list[dict[str, str]]:
    index_path = project_root / "06_kb" / "chunks" / "reference_index.json"
    if not index_path.exists():
        return []
    index = json.loads(index_path.read_text(encoding="utf-8"))
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
        scheduled_for = str(item.get("scheduled_for", "")).strip()
        reason = str(item.get("reason", "review scheduled"))
        date_label = f", {scheduled_for}" if scheduled_for else ""
        lines.append(f"- {concept}: {priority}, {due}{date_label} - {reason}")
    return lines or ["- none scheduled"]


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
        count = int(item.get("count", 1))
        lines.append(f"- {misconception_id}: {concept}, {status} x{count}")
    return lines or ["- none recorded"]


def _weak_concept_lines(value: object, *, threshold: float = 0.7) -> list[str]:
    if not isinstance(value, dict) or not value:
        return ["- none below threshold"]
    lines: list[str] = []
    for concept, score_value in sorted(value.items()):
        score = float(score_value)
        if score < threshold:
            lines.append(f"- {concept}: {score:g}")
    return lines or ["- none below threshold"]


def _yaml_like_string(value: str) -> str:
    if value == "null":
        return ""
    if value.startswith('"') and value.endswith('"'):
        return str(json.loads(value))
    return value
