"""Read-only operator dashboard for Socrates projects."""

from __future__ import annotations

import json
from pathlib import Path

from .context import load_project
from .learning_queue import (
    QueueItem,
    action_summary_lines,
    collect_learning_queue,
    priority_queue_items,
)
from .multi_session import read_multi_session_regression_status
from .reports import ReportSummary, list_learning_reports, summarize_report_history
from .workflow_manifest import read_session_closeout_status


TOP_PRIORITY_LIMIT = 5


def format_study_dashboard(project_path: Path | str) -> str:
    """Render a compact read-only project dashboard from existing evidence."""

    context = load_project(project_path)
    queue = collect_learning_queue(context.root)
    reports = list_learning_reports(context.root)
    report_history = summarize_report_history(context.root)
    closeout = read_session_closeout_status(context.root)
    regression = read_multi_session_regression_status(context.root)
    priority_actions = priority_queue_items(queue)[:TOP_PRIORITY_LIMIT]
    report_counts = _report_counts(reports)

    lines = [
        "# Study Dashboard",
        "",
        "## Snapshot",
        "",
        f"- Project: {project_title(context.project_file, fallback=context.root.name)}",
        f"- Root: {context.root}",
        f"- Workflow actions: {len(queue.workflow_actions)}",
        f"- Session closeout: {_status_label(closeout)}",
        f"- Multi-session regression: {_status_label(regression)}",
        f"- Report history: {report_history.status}",
        f"- Report history snapshots: {report_history.total_snapshots}",
        f"- Reports generated: {report_counts['generated']}",
        f"- Reports stale: {report_counts['stale']}",
        f"- Reports missing: {report_counts['missing']}",
        "",
        "## Action Summary",
        "",
        *action_summary_lines(queue),
        "",
        "## Top Priority Actions",
        "",
        *_queue_lines(priority_actions),
        "",
        "## Report Health",
        "",
        *_report_lines(reports),
        "",
        "## Boundary",
        "",
        (
            "This dashboard summarizes existing deterministic evidence only. It does "
            "not run repairs, generate reports, score learning, tutor, predict, "
            "approve artifacts, call an LLM, or mutate project state."
        ),
        "",
    ]
    return "\n".join(lines)


def _queue_lines(items: list[QueueItem]) -> list[str]:
    if not items:
        return ["- none"]
    lines = []
    for item in items:
        line = f"- {item.item_id} | {item.path}"
        if item.detail:
            line += f" | {item.detail}"
        lines.append(line)
    return lines


def _report_lines(reports: list[ReportSummary]) -> list[str]:
    if not reports:
        return ["- none"]
    return [
        f"- {report.report_id} | {report.status} | {report.title} | {report.path}"
        for report in reports
    ]


def _report_counts(reports: list[ReportSummary]) -> dict[str, int]:
    counts = {"generated": 0, "stale": 0, "missing": 0}
    for report in reports:
        if report.status in counts:
            counts[report.status] += 1
    return counts


def _status_label(value: dict[str, object] | None) -> str:
    if value is None:
        return "not_run"
    status = value.get("status")
    return status if isinstance(status, str) else "invalid"


def project_title(project_file: Path, *, fallback: str) -> str:
    try:
        lines = project_file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return fallback
    in_project = False
    for line in lines:
        stripped = line.strip()
        if stripped == "project:":
            in_project = True
            continue
        if in_project and stripped.startswith("title:"):
            title = _yaml_like_string(stripped.removeprefix("title:").strip())
            return title or fallback
        if in_project and line and not line.startswith(" "):
            break
    return fallback


def _yaml_like_string(value: str) -> str:
    if value in {"", "null"}:
        return ""
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return value.strip("'\"")
    return parsed if isinstance(parsed, str) else str(parsed)
