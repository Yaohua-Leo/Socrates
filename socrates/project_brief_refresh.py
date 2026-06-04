"""Batch study-brief refresh for project collections."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from .project_index import list_projects
from .resume import build_project_resume_payload
from .study_brief import generate_study_brief


PROJECT_BRIEF_REFRESH_QUALITY_BOUNDARY = "deterministic_project_brief_refresh"
STUDY_BRIEF_RELATIVE_PATH = "07_exports/briefs/study_brief.md"


def refresh_project_briefs_payload(
    root_path: Path | str,
    *,
    dry_run: bool = False,
    limit: int | None = None,
    project_ids: Sequence[str] | None = None,
) -> dict[str, object]:
    """Build the batch study-brief refresh payload, optionally without writes."""

    if limit is not None and limit <= 0:
        raise ValueError("limit must be positive")
    root = Path(root_path).expanduser().resolve()
    project_id_filter = _normalize_project_ids(project_ids)
    projects = list_projects(root)
    if project_id_filter:
        available_project_ids = {str(project["id"]) for project in projects}
        missing_project_ids = [
            project_id
            for project_id in project_id_filter
            if project_id not in available_project_ids
        ]
        if missing_project_ids:
            raise ValueError(f"unknown project id: {', '.join(missing_project_ids)}")
    selected: list[dict[str, str]] = []
    refreshed: list[dict[str, str]] = []
    deferred: list[dict[str, str]] = []
    excluded: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    for project in projects:
        project_path = root / str(project["path"])
        resume_payload = build_project_resume_payload(project_path)
        row = {
            "id": str(project["id"]),
            "title": str(resume_payload["project"]),
            "path": str(project["path"]),
            "resume_state": str(resume_payload["resume_state"]),
        }
        if project_id_filter and row["id"] not in project_id_filter:
            excluded.append({**row, "reason": "project_id_filter"})
            continue
        if row["resume_state"] != "refresh_brief":
            skipped.append({**row, "reason": "resume_state_ready"})
            continue
        if limit is not None and len(selected) >= limit:
            deferred.append(
                {
                    **row,
                    "brief_path": STUDY_BRIEF_RELATIVE_PATH,
                    "reason": "limit_reached",
                }
            )
            continue
        if dry_run:
            selected.append({**row, "brief_path": STUDY_BRIEF_RELATIVE_PATH})
            continue
        brief_path = generate_study_brief(project_path)
        refreshed_row = {
            **row,
            "brief_path": brief_path.relative_to(project_path).as_posix(),
        }
        selected.append(refreshed_row)
        refreshed.append(refreshed_row)
    mode = "dry_run" if dry_run else "write"
    return {
        "schema_version": 1,
        "quality_boundary": PROJECT_BRIEF_REFRESH_QUALITY_BOUNDARY,
        "root": str(root),
        "mode": mode,
        "dry_run": dry_run,
        "limit": limit,
        "project_ids": list(project_id_filter),
        "selected_count": len(selected),
        "refreshed_count": len(refreshed),
        "deferred_count": len(deferred),
        "excluded_count": len(excluded),
        "skipped_count": len(skipped),
        "selected": selected,
        "refreshed": refreshed,
        "deferred": deferred,
        "excluded": excluded,
        "skipped": skipped,
    }


def format_project_brief_refresh(
    root_path: Path | str,
    *,
    dry_run: bool = False,
    limit: int | None = None,
    project_ids: Sequence[str] | None = None,
) -> str:
    """Render a deterministic batch study-brief refresh summary."""

    payload = refresh_project_briefs_payload(
        root_path,
        dry_run=dry_run,
        limit=limit,
        project_ids=project_ids,
    )
    project_id_text = ", ".join(payload["project_ids"]) or "all"
    lines = [
        "# Project Brief Refresh",
        "",
        "## Summary",
        "",
        f"- Root: {payload['root']}",
        f"- Mode: {payload['mode']}",
        f"- Limit: {payload['limit'] if payload['limit'] is not None else 'none'}",
        f"- Project ids: {project_id_text}",
        f"- Selected: {payload['selected_count']}",
        f"- Refreshed: {payload['refreshed_count']}",
        f"- Deferred: {payload['deferred_count']}",
        f"- Excluded: {payload['excluded_count']}",
        f"- Skipped: {payload['skipped_count']}",
        "",
        "## Selected Projects",
        "",
    ]
    selected = payload["selected"]
    if not selected:
        lines.append("- none")
    else:
        for project in selected:
            lines.append(
                f"- {project['id']} | {project['title']} | "
                f"{project['resume_state']} | {project['brief_path']}"
            )
    lines.extend(
        [
            "",
            "## Refreshed Projects",
            "",
        ]
    )
    refreshed = payload["refreshed"]
    if not refreshed:
        lines.append("- none")
    else:
        for project in refreshed:
            lines.append(
                f"- {project['id']} | {project['title']} | {project['brief_path']}"
            )
    lines.extend(
        [
            "",
            "## Deferred Projects",
            "",
        ]
    )
    deferred = payload["deferred"]
    if not deferred:
        lines.append("- none")
    else:
        for project in deferred:
            lines.append(
                f"- {project['id']} | {project['title']} | "
                f"{project['resume_state']} | {project['brief_path']} | "
                f"{project['reason']}"
            )
    lines.extend(
        [
            "",
            "## Excluded Projects",
            "",
        ]
    )
    excluded = payload["excluded"]
    if not excluded:
        lines.append("- none")
    else:
        for project in excluded:
            lines.append(
                f"- {project['id']} | {project['title']} | "
                f"{project['resume_state']} | {project['reason']}"
            )
    lines.extend(
        [
            "",
            "## Skipped Projects",
            "",
        ]
    )
    skipped = payload["skipped"]
    if not skipped:
        lines.append("- none")
    else:
        for project in skipped:
            lines.append(
                f"- {project['id']} | {project['title']} | "
                f"{project['resume_state']} | {project['reason']}"
            )
    lines.extend(["", "## Boundary", ""])
    if dry_run:
        lines.extend(
            [
                (
                    "This dry run previews child projects whose current resume state "
                    "is refresh_brief. It does not write study briefs, manifests, "
                    "project logs, root indexes, reports, repairs, LLM drafts, "
                    "scores, tutoring actions, predictions, or learning-state truth."
                ),
                "",
            ]
        )
    else:
        lines.extend(
            [
                (
                    "This command writes study briefs only for child projects whose "
                    "current resume state is refresh_brief. It does not refresh ready "
                    "projects, generate reports, run repairs, call an LLM, approve "
                    "artifacts, score learning, tutor, predict, or mutate "
                    "learning-state truth. Use --dry-run to preview the same "
                    "selection without writes."
                ),
                "",
            ]
        )
    if limit is not None:
        lines.insert(
            -1,
            (
                "When --limit is set, over-limit refresh_brief projects are "
                "reported as deferred and left unwritten."
            ),
        )
    if payload["project_ids"]:
        lines.insert(
            -1,
            (
                "When --project-id is set, nonmatching child projects are "
                "reported as excluded and left untouched."
            ),
        )
    return "\n".join(lines)


def _normalize_project_ids(project_ids: Sequence[str] | None) -> tuple[str, ...]:
    if not project_ids:
        return ()
    normalized: list[str] = []
    seen: set[str] = set()
    for project_id in project_ids:
        value = str(project_id).strip()
        if not value or value in seen:
            continue
        normalized.append(value)
        seen.add(value)
    return tuple(normalized)
