"""Shared manifest readers for deterministic workflow artifacts."""

from __future__ import annotations

import json
from pathlib import Path


SESSION_CLOSEOUT_BOUNDARY = "deterministic_session_closeout"
SESSION_CLOSEOUT_MANIFEST_PATH = Path("08_evals") / "session_closeout_manifest.json"

_PATH_KEYS = (
    "session_score_report_path",
    "session_score_manifest_path",
    "next_session_plan_path",
    "next_session_plan_manifest_path",
    "project_summary_path",
)


def read_session_closeout_status(project_path: Path | str) -> dict[str, object] | None:
    """Read a normalized session closeout status for status/lifecycle surfaces."""

    project_root = Path(project_path).resolve()
    manifest_path = project_root / SESSION_CLOSEOUT_MANIFEST_PATH
    if not manifest_path.exists():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "invalid"}
    if not isinstance(manifest, dict):
        return {"status": "invalid"}
    normalized = _normalized_closeout_status(project_root, manifest)
    return normalized if normalized is not None else {"status": "invalid"}


def has_ready_session_closeout(project_path: Path | str) -> bool:
    """Return whether the project has a valid ready closeout manifest."""

    status = read_session_closeout_status(project_path)
    return status is not None and status.get("status") == "ready"


def _normalized_closeout_status(
    project_root: Path,
    manifest: dict[str, object],
) -> dict[str, object] | None:
    if manifest.get("schema_version") != 1:
        return None
    if manifest.get("quality_boundary") != SESSION_CLOSEOUT_BOUNDARY:
        return None
    status = manifest.get("status")
    if status not in {"ready", "needs_attention"}:
        return None
    session_id = manifest.get("session_id")
    next_session_id = manifest.get("next_session_id")
    if not isinstance(session_id, str) or not session_id:
        return None
    if not isinstance(next_session_id, str) or not next_session_id:
        return None
    session_score_status = manifest.get("session_score_status")
    if session_score_status not in {"pass", "fail"}:
        return None
    session_score = manifest.get("session_score")
    if type(session_score) is not int or session_score < 0 or session_score > 100:
        return None
    if status == "ready" and (session_score_status != "pass" or session_score != 100):
        return None
    if status == "needs_attention" and session_score_status != "fail":
        return None
    if not all(_manifest_artifact_exists(project_root, manifest.get(key)) for key in _PATH_KEYS):
        return None
    return {
        "status": status,
        "session_id": session_id,
        "next_session_id": next_session_id,
        "session_score_status": session_score_status,
        "session_score": session_score,
    }


def _manifest_artifact_exists(project_root: Path, value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        return False
    return (project_root / path).exists()
