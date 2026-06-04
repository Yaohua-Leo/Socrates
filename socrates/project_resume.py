"""Read-only resume summaries for project collections."""

from __future__ import annotations

from pathlib import Path

from .project_index import list_projects
from .resume import build_project_resume_payload


PROJECT_RESUME_INDEX_QUALITY_BOUNDARY = "deterministic_project_resume_index"
RESUME_STATE_FILTERS = ("all", "ready", "refresh_brief")


def build_project_resume_index_payload(
    root_path: Path | str,
    *,
    state_filter: str = "all",
) -> dict[str, object]:
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
    projects = _filtered_projects(projects, state_filter)
    ready_count = sum(1 for project in projects if project["resume_state"] == "ready")
    refresh_brief_count = sum(
        1 for project in projects if project["resume_state"] == "refresh_brief"
    )
    recommended_commands = _recommended_commands(projects)
    return {
        "schema_version": 1,
        "quality_boundary": PROJECT_RESUME_INDEX_QUALITY_BOUNDARY,
        "root": str(root),
        "state_filter": state_filter,
        "project_count": len(projects),
        "ready_count": ready_count,
        "refresh_brief_count": refresh_brief_count,
        "recommended_command_count": len(recommended_commands),
        "recommended_commands": recommended_commands,
        "projects": projects,
    }


def format_project_resume_index(
    root_path: Path | str,
    *,
    state_filter: str = "all",
) -> str:
    """Render resume readiness across a root of Socrates projects."""

    payload = build_project_resume_index_payload(root_path, state_filter=state_filter)
    projects = payload["projects"]
    lines = [
        "# Project Resume Index",
        "",
        "## Snapshot",
        "",
        f"- Root: {payload['root']}",
        f"- State filter: {payload['state_filter']}",
        f"- Projects: {payload['project_count']}",
        f"- Ready: {payload['ready_count']}",
        f"- Refresh brief: {payload['refresh_brief_count']}",
        f"- Recommended commands: {payload['recommended_command_count']}",
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
    recommended_commands = payload["recommended_commands"]
    lines.extend(["", "## Recommended Commands", ""])
    if not recommended_commands:
        lines.append("- none")
    else:
        for command in recommended_commands:
            lines.append(
                f"- {command['project_id']} | {command['project_title']} | "
                f"{command['resume_state']} | {command['command']}"
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


def _filtered_projects(
    projects: list[dict[str, object]],
    state_filter: str,
) -> list[dict[str, object]]:
    if state_filter not in RESUME_STATE_FILTERS:
        raise ValueError(f"unknown resume state filter: {state_filter}")
    if state_filter == "all":
        return projects
    return [project for project in projects if project["resume_state"] == state_filter]


def _recommended_commands(projects: list[dict[str, object]]) -> list[dict[str, str]]:
    commands: list[dict[str, str]] = []
    for project in projects:
        command = str(project.get("recommended_command", "")).strip()
        if not command or command == "none":
            continue
        commands.append(
            {
                "project_id": str(project["id"]),
                "project_title": str(project["title"]),
                "resume_state": str(project["resume_state"]),
                "command": command,
            }
        )
    return commands
