"""Read-only project resume summaries for returning learners."""

from __future__ import annotations

from pathlib import Path

from .context import load_project
from .dashboard import project_title
from .study_brief_status import StudyBriefStatus, summarize_study_brief


def format_project_resume(project_path: Path | str) -> str:
    """Render the compact read-only resume card for one project."""

    context = load_project(project_path)
    study_brief = summarize_study_brief(context.root)
    lines = [
        "# Resume Project",
        "",
        "## Snapshot",
        "",
        f"- Project: {project_title(context.project_file, fallback=context.root.name)}",
        f"- Root: {context.root}",
        f"- Resume state: {_resume_state(study_brief)}",
        f"- Study brief: {study_brief.status}",
        f"- Study brief path: {study_brief.path}",
        f"- Current next action: {study_brief.current_next_action}",
        f"- Recommended command: {_recommended_command(context.root, study_brief)}",
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
