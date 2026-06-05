"""Read-only project resume summaries for returning learners."""

from __future__ import annotations

from pathlib import Path

from .context import load_project, project_title
from .study_brief_status import StudyBriefStatus, summarize_study_brief


RESUME_QUALITY_BOUNDARY = "deterministic_project_resume"


def build_project_resume_payload(project_path: Path | str) -> dict[str, object]:
    """Build the machine-readable read-only resume payload."""

    context = load_project(project_path)
    study_brief = summarize_study_brief(context.root)
    return {
        "schema_version": 1,
        "quality_boundary": RESUME_QUALITY_BOUNDARY,
        "project": project_title(context.project_file, fallback=context.root.name),
        "root": str(context.root),
        "resume_state": _resume_state(study_brief),
        "study_brief": study_brief.status,
        "study_brief_path": study_brief.path,
        "current_next_action": study_brief.current_next_action,
        "recommended_command": _recommended_command(context.root, study_brief),
    }


def format_project_resume(project_path: Path | str) -> str:
    """Render the compact read-only resume card for one project."""

    payload = build_project_resume_payload(project_path)
    lines = [
        "# Resume Project",
        "",
        "## Snapshot",
        "",
        f"- Project: {payload['project']}",
        f"- Root: {payload['root']}",
        f"- Resume state: {payload['resume_state']}",
        f"- Study brief: {payload['study_brief']}",
        f"- Study brief path: {payload['study_brief_path']}",
        f"- Current next action: {payload['current_next_action']}",
        f"- Recommended command: {payload['recommended_command']}",
        "",
        "## Boundary",
        "",
        (
            "This resume card summarizes existing deterministic evidence only. "
            "It does not generate briefs, refresh reports, run repairs, call an "
            "LLM, approve artifacts, score learning, tutor, predict, or mutate "
            "project state."
        ),
        "",
    ]
    return "\n".join(lines)


def _resume_state(study_brief: StudyBriefStatus) -> str:
    if study_brief.status == "current":
        return "ready"
    return "refresh_brief"


def _recommended_command(project_root: Path, study_brief: StudyBriefStatus) -> str:
    if study_brief.status == "current":
        return "none"
    return f'python -m socrates brief generate --project "{project_root}"'
