"""Batch study-brief refresh for project collections."""

from __future__ import annotations

from pathlib import Path

from .project_index import list_projects
from .resume import build_project_resume_payload
from .study_brief import generate_study_brief


PROJECT_BRIEF_REFRESH_QUALITY_BOUNDARY = "deterministic_project_brief_refresh"


def refresh_project_briefs_payload(root_path: Path | str) -> dict[str, object]:
    """Generate study briefs for child projects that need a brief refresh."""

    root = Path(root_path).expanduser().resolve()
    refreshed: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    for project in list_projects(root):
        project_path = root / str(project["path"])
        resume_payload = build_project_resume_payload(project_path)
        row = {
            "id": str(project["id"]),
            "title": str(resume_payload["project"]),
            "path": str(project["path"]),
            "resume_state": str(resume_payload["resume_state"]),
        }
        if row["resume_state"] != "refresh_brief":
            skipped.append({**row, "reason": "resume_state_ready"})
            continue
        brief_path = generate_study_brief(project_path)
        refreshed.append(
            {
                **row,
                "brief_path": brief_path.relative_to(project_path).as_posix(),
            }
        )
    return {
        "schema_version": 1,
        "quality_boundary": PROJECT_BRIEF_REFRESH_QUALITY_BOUNDARY,
        "root": str(root),
        "refreshed_count": len(refreshed),
        "skipped_count": len(skipped),
        "refreshed": refreshed,
        "skipped": skipped,
    }


def format_project_brief_refresh(root_path: Path | str) -> str:
    """Render a deterministic batch study-brief refresh summary."""

    payload = refresh_project_briefs_payload(root_path)
    lines = [
        "# Project Brief Refresh",
        "",
        "## Summary",
        "",
        f"- Root: {payload['root']}",
        f"- Refreshed: {payload['refreshed_count']}",
        f"- Skipped: {payload['skipped_count']}",
        "",
        "## Refreshed Projects",
        "",
    ]
    refreshed = payload["refreshed"]
    if not refreshed:
        lines.append("- none")
    else:
        for project in refreshed:
            lines.append(
                f"- {project['id']} | {project['title']} | {project['brief_path']}"
            )
    lines.extend(["", "## Skipped Projects", ""])
    skipped = payload["skipped"]
    if not skipped:
        lines.append("- none")
    else:
        for project in skipped:
            lines.append(
                f"- {project['id']} | {project['title']} | "
                f"{project['resume_state']} | {project['reason']}"
            )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            (
                "This command writes study briefs only for child projects whose "
                "current resume state is refresh_brief. It does not refresh ready "
                "projects, generate reports, run repairs, call an LLM, approve "
                "artifacts, score learning, tutor, predict, or mutate learning-state truth."
            ),
            "",
        ]
    )
    return "\n".join(lines)
