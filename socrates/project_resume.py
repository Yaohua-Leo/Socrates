"""Read-only resume summaries for project collections."""

from __future__ import annotations

from pathlib import Path

from .project_index import list_projects
from .resume import build_project_resume_payload


PROJECT_RESUME_INDEX_QUALITY_BOUNDARY = "deterministic_project_resume_index"


def build_project_resume_index_payload(root_path: Path | str) -> dict[str, object]:
    """Build the machine-readable read-only resume index payload."""

    root = Path(root_path).expanduser().resolve()
    projects = []
    for project in list_projects(root):
        resume_payload = build_project_resume_payload(root / project["path"])
        projects.append(
            {
                "id": project["id"],
                "title": resume_payload["project"],
                "path": project["path"],
                "resume_state": resume_payload["resume_state"],
                "study_brief": resume_payload["study_brief"],
                "study_brief_path": resume_payload["study_brief_path"],
                "current_next_action": resume_payload["current_next_action"],
                "recommended_command": resume_payload["recommended_command"],
            }
        )
    return {
        "schema_version": 1,
        "quality_boundary": PROJECT_RESUME_INDEX_QUALITY_BOUNDARY,
        "root": str(root),
        "project_count": len(projects),
        "projects": projects,
    }


def format_project_resume_index(root_path: Path | str) -> str:
    """Render resume readiness across a root of Socrates projects."""

    payload = build_project_resume_index_payload(root_path)
    projects = payload["projects"]
    lines = [
        "# Project Resume Index",
        "",
        "## Snapshot",
        "",
        f"- Root: {payload['root']}",
        f"- Projects: {payload['project_count']}",
        "",
        "## Projects",
        "",
    ]
    if not projects:
        lines.append("- none")
    else:
        for project in projects:
            lines.append(
                f"- {project['id']} | {project['title']} | "
                f"{project['resume_state']} | {project['study_brief']} | "
                f"{project['current_next_action']} | {project['recommended_command']}"
            )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            (
                "This project resume index summarizes existing deterministic "
                "evidence only. It does not generate briefs, refresh reports, "
                "run repairs, call an LLM, approve artifacts, score learning, "
                "tutor, predict, or mutate project state."
            ),
            "",
        ]
    )
    return "\n".join(lines)
