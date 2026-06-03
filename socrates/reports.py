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
            sessions_completed=_count_dirs(context.sessions_dir),
            reviewed_notes=_count_reviewed_notes(context.root),
            obsidian_exports=_count_markdown(context.root / "07_exports" / "obsidian"),
            generated_exercises=_count_markdown(context.generated_exercises_dir),
            approved_exercises=_count_approved_exercises(context.root),
            attempted_exercises=_count_markdown(context.root / "05_exercises" / "attempted"),
            graded_exercises=_count_markdown(context.root / "05_exercises" / "graded"),
            state=state,
        ),
    )
    append_project_log(context, "Generated project summary report.")
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


def _project_summary_text(
    *,
    title: str,
    project_root: Path,
    imported_sources: int,
    curated_references: int,
    kb_objects: int,
    sessions_completed: int,
    reviewed_notes: int,
    obsidian_exports: int,
    generated_exercises: int,
    approved_exercises: int,
    attempted_exercises: int,
    graded_exercises: int,
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
        reason = str(item.get("reason", "review scheduled"))
        lines.append(f"- {concept}: {priority}, {due} - {reason}")
    return lines or ["- none scheduled"]


def _yaml_like_string(value: str) -> str:
    if value == "null":
        return ""
    if value.startswith('"') and value.endswith('"'):
        return str(json.loads(value))
    return value
