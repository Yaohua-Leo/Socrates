"""Deterministic multi-session regression checks."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from .context import append_project_log, load_project, write_json, write_text
from .workflow_manifest import read_session_closeout_status


MULTI_SESSION_REGRESSION_BOUNDARY = "deterministic_multi_session_regression"
MULTI_SESSION_REGRESSION_REPORT_PATH = Path("08_evals") / "multi_session_regression.md"
MULTI_SESSION_REGRESSION_MANIFEST_PATH = (
    Path("08_evals") / "multi_session_regression_manifest.json"
)

SESSION_ARTIFACTS = (
    "transcript.md",
    "tutor_notes.md",
    "detected_misconceptions.md",
    "summary.md",
    "next_actions.md",
)


@dataclass(frozen=True)
class MultiSessionRegressionResult:
    """Summary of one persisted multi-session regression run."""

    status: str
    closeout_session_id: str
    next_session_id: str
    passed_checks: int
    total_checks: int
    issues: list[str]
    report_path: Path
    manifest_path: Path


def run_multi_session_regression(project_path: Path | str) -> MultiSessionRegressionResult:
    """Verify that a completed session has carried into a visible next session."""

    context = load_project(project_path)
    closeout = read_session_closeout_status(context.root)
    closeout_session_id = _string_value(closeout, "session_id")
    next_session_id = _string_value(closeout, "next_session_id")
    checks = _regression_checks(
        context.root,
        closeout=closeout,
        closeout_session_id=closeout_session_id,
        next_session_id=next_session_id,
    )
    passed_checks = sum(1 for check in checks if check["passed"] is True)
    total_checks = len(checks)
    issues = [
        str(issue)
        for check in checks
        for issue in check.get("issues", [])
        if isinstance(issue, str)
    ]
    status = "pass" if passed_checks == total_checks else "fail"
    report_path = context.root / MULTI_SESSION_REGRESSION_REPORT_PATH
    manifest_path = context.root / MULTI_SESSION_REGRESSION_MANIFEST_PATH
    write_text(
        report_path,
        _regression_report(
            status=status,
            closeout_session_id=closeout_session_id,
            next_session_id=next_session_id,
            passed_checks=passed_checks,
            total_checks=total_checks,
            checks=checks,
            issues=issues,
        ),
    )
    write_json(
        manifest_path,
        {
            "schema_version": 1,
            "quality_boundary": MULTI_SESSION_REGRESSION_BOUNDARY,
            "status": status,
            "closeout_session_id": closeout_session_id,
            "next_session_id": next_session_id,
            "passed_checks": passed_checks,
            "total_checks": total_checks,
            "checks": checks,
            "issues": issues,
            "report_path": MULTI_SESSION_REGRESSION_REPORT_PATH.as_posix(),
        },
    )
    append_project_log(context, "Ran deterministic multi-session regression.")
    return MultiSessionRegressionResult(
        status=status,
        closeout_session_id=closeout_session_id,
        next_session_id=next_session_id,
        passed_checks=passed_checks,
        total_checks=total_checks,
        issues=issues,
        report_path=report_path,
        manifest_path=manifest_path,
    )


def read_multi_session_regression_status(project_path: Path | str) -> dict[str, object] | None:
    """Read a normalized persisted multi-session regression status."""

    project_root = Path(project_path).resolve()
    manifest_path = project_root / MULTI_SESSION_REGRESSION_MANIFEST_PATH
    if not manifest_path.exists():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "invalid"}
    if not isinstance(manifest, dict):
        return {"status": "invalid"}
    normalized = _normalized_regression_status(project_root, manifest)
    return normalized if normalized is not None else {"status": "invalid"}


def has_passing_multi_session_regression(project_path: Path | str) -> bool:
    """Return whether the latest persisted multi-session regression passed."""

    status = read_multi_session_regression_status(project_path)
    return status is not None and status.get("status") == "pass"


def _regression_checks(
    project_root: Path,
    *,
    closeout: dict[str, object] | None,
    closeout_session_id: str,
    next_session_id: str,
) -> list[dict[str, object]]:
    return [
        _check_closeout_manifest(closeout),
        _check_session_artifacts(
            project_root,
            closeout_session_id,
            name="Completed session artifacts",
            missing_label="missing completed session artifacts",
        ),
        _check_session_artifacts(
            project_root,
            next_session_id,
            name="Next session artifacts",
            missing_label="missing next session artifacts",
        ),
        _check_next_session_handoff(project_root, next_session_id),
        _check_project_summary(project_root),
    ]


def _check_closeout_manifest(closeout: dict[str, object] | None) -> dict[str, object]:
    passed = closeout is not None and closeout.get("status") == "ready"
    issues: list[str] = []
    if not passed:
        issues.append("missing ready session closeout")
    return {"name": "Session closeout manifest", "passed": passed, "issues": issues}


def _check_session_artifacts(
    project_root: Path,
    session_id: str,
    *,
    name: str,
    missing_label: str,
) -> dict[str, object]:
    issues: list[str] = []
    if not session_id:
        issues.append(f"{missing_label}: unknown")
    else:
        session_dir = project_root / "03_sessions" / session_id
        missing = [
            artifact
            for artifact in SESSION_ARTIFACTS
            if not (session_dir / artifact).exists()
        ]
        if missing:
            issues.append(f"{missing_label}: {session_id}")
    return {"name": name, "passed": not issues, "issues": issues}


def _check_next_session_handoff(project_root: Path, next_session_id: str) -> dict[str, object]:
    manifest_path = project_root / "02_learning_plan" / "next_session_plan_manifest.json"
    issues: list[str] = []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        manifest = None
    if not isinstance(manifest, dict):
        issues.append("missing next-session handoff manifest")
    elif manifest.get("schema_version") != 1:
        issues.append("invalid next-session handoff schema")
    elif manifest.get("quality_boundary") != "deterministic_handoff_plan":
        issues.append("invalid next-session handoff boundary")
    elif manifest.get("session_id") != next_session_id:
        issues.append("next-session handoff target mismatch")
    else:
        plan_path = manifest.get("plan_path")
        if not _relative_artifact_exists(project_root, plan_path):
            issues.append("missing next-session handoff plan")
    return {"name": "Next session handoff", "passed": not issues, "issues": issues}


def _check_project_summary(project_root: Path) -> dict[str, object]:
    path = project_root / "07_exports" / "reports" / "project_summary.md"
    issues = [] if path.exists() else ["missing project summary refresh"]
    return {"name": "Project summary refresh", "passed": not issues, "issues": issues}


def _normalized_regression_status(
    project_root: Path,
    manifest: dict[str, object],
) -> dict[str, object] | None:
    if manifest.get("schema_version") != 1:
        return None
    if manifest.get("quality_boundary") != MULTI_SESSION_REGRESSION_BOUNDARY:
        return None
    status = manifest.get("status")
    if status not in {"pass", "fail"}:
        return None
    closeout_session_id = manifest.get("closeout_session_id")
    next_session_id = manifest.get("next_session_id")
    if not isinstance(closeout_session_id, str):
        return None
    if not isinstance(next_session_id, str):
        return None
    passed_checks = manifest.get("passed_checks")
    total_checks = manifest.get("total_checks")
    if type(passed_checks) is not int or type(total_checks) is not int:
        return None
    if passed_checks < 0 or total_checks <= 0 or passed_checks > total_checks:
        return None
    issues = manifest.get("issues")
    if not isinstance(issues, list) or not all(isinstance(issue, str) for issue in issues):
        return None
    checks = manifest.get("checks")
    if not isinstance(checks, list) or len(checks) != total_checks:
        return None
    if status == "pass" and (passed_checks != total_checks or issues):
        return None
    if status == "fail" and passed_checks == total_checks:
        return None
    if not _relative_artifact_exists(project_root, manifest.get("report_path")):
        return None
    return {
        "status": status,
        "closeout_session_id": closeout_session_id,
        "next_session_id": next_session_id,
        "passed_checks": passed_checks,
        "total_checks": total_checks,
        "issues": issues,
    }


def _regression_report(
    *,
    status: str,
    closeout_session_id: str,
    next_session_id: str,
    passed_checks: int,
    total_checks: int,
    checks: list[dict[str, object]],
    issues: list[str],
) -> str:
    lines = [
        "# Multi-Session Regression",
        "",
        "## Summary",
        "",
        f"- Status: {status}",
        f"- Closeout session: {closeout_session_id or 'unknown'}",
        f"- Next session: {next_session_id or 'unknown'}",
        f"- Checks: {passed_checks}/{total_checks}",
        "",
        "## Checks",
        "",
    ]
    for check in checks:
        check_status = "pass" if check["passed"] is True else "fail"
        lines.append(f"- {check['name']}: {check_status}")
    lines.extend(["", "## Issues", ""])
    if issues:
        lines.extend(f"- {issue}" for issue in issues)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            (
                "This regression is deterministic artifact evidence. It is not an LLM "
                "judge, mathematical proof, grade, or learning-state truth source."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def _string_value(value: dict[str, object] | None, key: str) -> str:
    if value is None or value.get("status") == "invalid":
        return ""
    item = value.get(key)
    return item if isinstance(item, str) else ""


def _relative_artifact_exists(project_root: Path, value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        return False
    return (project_root / path).exists()
