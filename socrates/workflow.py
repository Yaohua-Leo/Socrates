"""Deterministic product workflow compositions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .context import append_project_log, load_project, write_json
from .planning import create_next_session_plan
from .reports import generate_project_summary
from .session_score import score_teaching_session
from .workflow_manifest import SESSION_CLOSEOUT_BOUNDARY, SESSION_CLOSEOUT_MANIFEST_PATH


@dataclass(frozen=True)
class SessionCloseoutResult:
    """Summary of one deterministic post-session closeout."""

    session_id: str
    next_session_id: str
    status: str
    session_score: int
    session_score_status: str
    session_score_report_path: Path
    session_score_manifest_path: Path
    next_session_plan_path: Path
    next_session_plan_manifest_path: Path
    project_summary_path: Path
    manifest_path: Path


def close_tutoring_session(
    project_path: Path | str,
    *,
    session_id: str,
    next_session_id: str,
    as_of: date | None = None,
) -> SessionCloseoutResult:
    """Run deterministic post-session score, handoff, and summary generation."""

    context = load_project(project_path)
    score = score_teaching_session(context.root, session_id=session_id)
    handoff = create_next_session_plan(
        context.root,
        session_id=next_session_id,
        as_of=as_of,
    )
    project_summary_path = generate_project_summary(context.root)
    status = "ready" if score.status == "pass" else "needs_attention"
    manifest_path = context.root / SESSION_CLOSEOUT_MANIFEST_PATH
    write_json(
        manifest_path,
        {
            "schema_version": 1,
            "session_id": session_id,
            "next_session_id": next_session_id,
            "status": status,
            "quality_boundary": SESSION_CLOSEOUT_BOUNDARY,
            "session_score_status": score.status,
            "session_score": score.score,
            "session_score_report_path": score.report_path.relative_to(context.root).as_posix(),
            "session_score_manifest_path": score.manifest_path.relative_to(context.root).as_posix(),
            "next_session_plan_path": handoff.plan_path.relative_to(context.root).as_posix(),
            "next_session_plan_manifest_path": handoff.manifest_path.relative_to(
                context.root
            ).as_posix(),
            "project_summary_path": project_summary_path.relative_to(context.root).as_posix(),
        },
    )
    append_project_log(context, f"Closed out session {session_id} for {next_session_id}.")
    return SessionCloseoutResult(
        session_id=session_id,
        next_session_id=next_session_id,
        status=status,
        session_score=score.score,
        session_score_status=score.status,
        session_score_report_path=score.report_path,
        session_score_manifest_path=score.manifest_path,
        next_session_plan_path=handoff.plan_path,
        next_session_plan_manifest_path=handoff.manifest_path,
        project_summary_path=project_summary_path,
        manifest_path=manifest_path,
    )
