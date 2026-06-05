"""Read-only operator dashboard for Socrates projects."""

from __future__ import annotations

from .context import load_project, project_title
from .learning_queue import (
    QueueItem,
    action_summary_record,
    collect_learning_queue,
    priority_queue_items,
)
from .multi_session import read_multi_session_regression_status
from .reports import ReportSummary, list_learning_reports, summarize_report_history
from .study_brief_status import summarize_study_brief
from .workflow_manifest import read_session_closeout_status


TOP_PRIORITY_LIMIT = 5
DASHBOARD_QUALITY_BOUNDARY = "deterministic_study_dashboard"


def build_study_dashboard_payload(project_path: Path | str) -> dict[str, object]:
    """Build the machine-readable read-only dashboard payload."""

    context = load_project(project_path)
    queue = collect_learning_queue(context.root)
    reports = list_learning_reports(context.root)
    report_history = summarize_report_history(context.root)
    closeout = read_session_closeout_status(context.root)
    regression = read_multi_session_regression_status(context.root)
    study_brief = summarize_study_brief(context.root)
    priority_actions = priority_queue_items(queue)[:TOP_PRIORITY_LIMIT]
    report_counts = _report_counts(reports)

    return {
        "schema_version": 1,
        "quality_boundary": DASHBOARD_QUALITY_BOUNDARY,
        "project": project_title(context.project_file, fallback=context.root.name),
        "root": str(context.root),
        "snapshot": {
            "workflow_actions": len(queue.workflow_actions),
            "session_closeout": _status_label(closeout),
            "multi_session_regression": _status_label(regression),
            "report_history": report_history.status,
            "report_history_snapshots": report_history.total_snapshots,
            "study_brief": study_brief.status,
            "study_brief_recorded_next_action": study_brief.recorded_next_action,
            "study_brief_current_next_action": study_brief.current_next_action,
            "reports_generated": report_counts["generated"],
            "reports_stale": report_counts["stale"],
            "reports_missing": report_counts["missing"],
        },
        "action_summary": action_summary_record(queue),
        "top_priority_actions": [_queue_item_record(item) for item in priority_actions],
        "report_health": [_report_record(report) for report in reports],
    }


def format_study_dashboard(project_path: Path | str) -> str:
    """Render a compact read-only project dashboard from existing evidence."""

    payload = build_study_dashboard_payload(project_path)
    snapshot = payload["snapshot"]
    action_summary = payload["action_summary"]
    top_priority_actions = payload["top_priority_actions"]
    report_health = payload["report_health"]

    lines = [
        "# Study Dashboard",
        "",
        "## Snapshot",
        "",
        f"- Project: {payload['project']}",
        f"- Root: {payload['root']}",
        f"- Workflow actions: {snapshot['workflow_actions']}",
        f"- Session closeout: {snapshot['session_closeout']}",
        f"- Multi-session regression: {snapshot['multi_session_regression']}",
        f"- Report history: {snapshot['report_history']}",
        f"- Report history snapshots: {snapshot['report_history_snapshots']}",
        f"- Study brief: {snapshot['study_brief']}",
        f"- Study brief recorded next action: {snapshot['study_brief_recorded_next_action']}",
        f"- Study brief current next action: {snapshot['study_brief_current_next_action']}",
        f"- Reports generated: {snapshot['reports_generated']}",
        f"- Reports stale: {snapshot['reports_stale']}",
        f"- Reports missing: {snapshot['reports_missing']}",
        "",
        "## Action Summary",
        "",
        *_action_summary_lines(action_summary),
        "",
        "## Top Priority Actions",
        "",
        *_queue_lines(top_priority_actions),
        "",
        "## Report Health",
        "",
        *_report_lines(report_health),
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


def _action_summary_lines(summary: object) -> list[str]:
    record = summary if isinstance(summary, dict) else {}
    return [
        f"- Completion: {record.get('completion', 'clear')}",
        f"- Open actions: {record.get('open_actions', 0)}",
        f"- Blockers: {record.get('blockers', 0)}",
        f"- Can continue learning: {record.get('can_continue_learning', 0)}",
        f"- Needs human review: {record.get('needs_human_review', 0)}",
        f"- Next action: {record.get('next_action', 'none')}",
    ]


def _queue_lines(items: object) -> list[str]:
    rows = items if isinstance(items, list) else []
    if not rows:
        return ["- none"]
    return [f"- {_queue_item_summary(row)}" for row in rows]


def _queue_item_summary(row: object) -> str:
    record = row if isinstance(row, dict) else {}
    line = f"{record.get('item_id', '')} | {record.get('path', '')}"
    detail = str(record.get("detail", ""))
    if detail:
        line = f"{line} | {detail}"
    return line


def _queue_item_record(item: QueueItem) -> dict[str, str]:
    return {
        "item_id": item.item_id,
        "path": item.path,
        "detail": item.detail,
    }


def _report_lines(reports: object) -> list[str]:
    rows = reports if isinstance(reports, list) else []
    if not rows:
        return ["- none"]
    return [
        f"- {report['report_id']} | {report['status']} | {report['title']} | {report['path']}"
        for report in rows
        if isinstance(report, dict)
    ]


def _report_record(report: ReportSummary) -> dict[str, str]:
    return {
        "report_id": report.report_id,
        "status": report.status,
        "title": report.title,
        "path": report.path,
    }


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
