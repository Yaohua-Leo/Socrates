"""Read-only resume summaries for project collections."""

from __future__ import annotations

from pathlib import Path

from .project_index import list_projects
from .resume import build_project_resume_payload


def format_project_resume_index(root_path: Path | str) -> str:
    """Render resume readiness across a root of Socrates projects."""

    root = Path(root_path).expanduser().resolve()
    projects = list_projects(root)
    lines = [
        "# Project Resume Index",
        "",
        "## Snapshot",
        "",
        f"- Root: {root}",
        f"- Projects: {len(projects)}",
        "",
        "## Projects",
        "",
    ]
    if not projects:
        lines.append("- none")
    else:
        for project in projects:
            payload = build_project_resume_payload(root / project["path"])
            lines.append(
                f"- {project['id']} | {payload['project']} | "
                f"{payload['resume_state']} | {payload['study_brief']} | "
                f"{payload['current_next_action']} | {payload['recommended_command']}"
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
