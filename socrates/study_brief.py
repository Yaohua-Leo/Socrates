"""Generated study-start briefs for Socrates projects."""

from __future__ import annotations

from pathlib import Path

from .context import append_project_log, load_project, write_json, write_text
from .dashboard import format_study_dashboard, project_title
from .learning_queue import QueueItem, collect_learning_queue, priority_queue_items
from .study_brief_status import (
    STUDY_BRIEF_MANIFEST_RELATIVE_PATH,
    STUDY_BRIEF_QUALITY_BOUNDARY,
    STUDY_BRIEF_RELATIVE_PATH,
)


def format_study_brief(project_path: Path | str) -> str:
    """Render a deterministic startup brief from existing project evidence."""

    context = load_project(project_path)
    first_action = _first_priority_action(context.root)
    lines = [
        "# Study Brief",
        "",
        "## Start Here",
        "",
        f"- Project: {project_title(context.project_file, fallback=context.root.name)}",
        f"- Root: {context.root}",
        f"- Next action: {_action_line(first_action)}",
        f"- Action type: {_action_type(first_action)}",
        "",
        "## Dashboard Evidence",
        "",
        *_demote_markdown_headings(format_study_dashboard(context.root).rstrip().splitlines()),
        "",
        "## Boundary",
        "",
        (
            "This brief is generated from existing deterministic evidence only. "
            "Aside from writing this brief artifact and a project-log entry, it "
            "does not run repairs, generate reports, call an LLM, approve "
            "artifacts, score learning, tutor, predict, or mutate learning-state "
            "truth."
        ),
        "",
    ]
    return "\n".join(lines)


def generate_study_brief(project_path: Path | str) -> Path:
    """Write the study brief export artifact and return its path."""

    context = load_project(project_path)
    brief_path = context.root / STUDY_BRIEF_RELATIVE_PATH
    first_action = _first_priority_action(context.root)
    write_text(brief_path, format_study_brief(context.root))
    write_json(
        context.root / STUDY_BRIEF_MANIFEST_RELATIVE_PATH,
        {
            "schema_version": 1,
            "quality_boundary": STUDY_BRIEF_QUALITY_BOUNDARY,
            "status": "generated",
            "brief_path": STUDY_BRIEF_RELATIVE_PATH.as_posix(),
            "recorded_next_action": _action_line(first_action),
            "action_type": _action_type(first_action),
        },
    )
    append_project_log(context, "Generated study brief.")
    return brief_path


def _first_priority_action(project_path: Path) -> QueueItem | None:
    actions = priority_queue_items(collect_learning_queue(project_path))
    return actions[0] if actions else None


def _action_line(item: QueueItem | None) -> str:
    if item is None:
        return "none"
    line = f"{item.item_id} | {item.path}"
    if item.detail:
        line += f" | {item.detail}"
    return line


def _action_type(item: QueueItem | None) -> str:
    if item is None:
        return "none"
    section = item.item_id.split(":", maxsplit=1)[0]
    if section in {"workflow", "quality-checks", "tool-verifications"}:
        return "blocker"
    if section in {"reviews", "exercises"}:
        return "continue_learning"
    if section in {
        "attempts",
        "exercise-drafts",
        "misconceptions",
        "notes",
        "obsidian-exports",
    }:
        return "human_review"
    return "action"


def _demote_markdown_headings(lines: list[str]) -> list[str]:
    demoted: list[str] = []
    for line in lines:
        if line.startswith("# "):
            demoted.append("## " + line[2:])
            continue
        if line.startswith("## "):
            demoted.append("### " + line[3:])
            continue
        demoted.append(line)
    return demoted
