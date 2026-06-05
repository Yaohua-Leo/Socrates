"""Session-level teaching quality score composition."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from .context import load_project, write_json, write_text
from .exercise_validation import validate_project_exercises
from .quality import (
    check_atomic_note_quality,
    check_generated_exercise_quality,
    check_reference_ingestion_quality,
    check_tutoring_session_quality,
)


@dataclass(frozen=True)
class SessionScoreResult:
    """Summary of a persisted session score report."""

    session_id: str
    status: str
    score: int
    total_gates: int
    passed_gates: int
    report_path: Path
    manifest_path: Path


def score_teaching_session(
    project_path: Path | str,
    *,
    session_id: str,
) -> SessionScoreResult:
    """Run deterministic teaching-quality gates and write a session score report."""

    context = load_project(project_path)
    ingestion = check_reference_ingestion_quality(context.root)
    note = check_atomic_note_quality(context.root)
    exercise = check_generated_exercise_quality(context.root)
    validation = validate_project_exercises(context.root)
    tutoring = check_tutoring_session_quality(context.root, session_id=session_id)

    gate_entries = [
        _gate_entry(
            context.root,
            "Ingestion",
            passed=ingestion.failed == 0 and ingestion.checked > 0,
            checked=ingestion.checked,
            failed=ingestion.failed,
            report_path=ingestion.report_path,
            manifest_path=ingestion.manifest_path,
        ),
        _gate_entry(
            context.root,
            "Note quality",
            passed=note.failed == 0 and note.checked > 0,
            checked=note.checked,
            failed=note.failed,
            report_path=note.report_path,
            manifest_path=note.manifest_path,
        ),
        _gate_entry(
            context.root,
            "Exercise quality",
            passed=exercise.failed == 0 and exercise.checked > 0,
            checked=exercise.checked,
            failed=exercise.failed,
            report_path=exercise.report_path,
            manifest_path=exercise.manifest_path,
        ),
        _gate_entry(
            context.root,
            "Exercise validation",
            passed=validation.failed == 0 and validation.checked > 0,
            checked=validation.checked,
            failed=validation.failed,
            report_path=validation.report_path,
            manifest_path=validation.manifest_path,
        ),
        _gate_entry(
            context.root,
            "Tutoring quality",
            passed=tutoring.status == "pass",
            checked=1,
            failed=0 if tutoring.status == "pass" else 1,
            report_path=tutoring.report_path,
            manifest_path=tutoring.manifest_path,
            score=_tutoring_total_score(context.root, session_id),
            extra={
                "session_id": tutoring.session_id,
                "status": tutoring.status,
            },
        ),
    ]
    passed_gates = sum(1 for gate in gate_entries if gate["passed"] is True)
    score = _percent(passed_gates, len(gate_entries))
    status = "pass" if passed_gates == len(gate_entries) else "fail"
    report_path = context.evals_dir / "session_score_report.md"
    manifest_path = context.evals_dir / "session_score_manifest.json"
    write_text(
        report_path,
        _session_score_report(
            session_id,
            gate_entries,
            score=score,
            passed_gates=passed_gates,
            status=status,
        ),
    )
    write_json(
        manifest_path,
        {
            "schema_version": 1,
            "session_id": session_id,
            "status": status,
            "score": score,
            "passed_gates": passed_gates,
            "total_gates": len(gate_entries),
            "quality_boundary": "advisory_checklist",
            "gates": gate_entries,
        },
    )
    return SessionScoreResult(
        session_id=session_id,
        status=status,
        score=score,
        total_gates=len(gate_entries),
        passed_gates=passed_gates,
        report_path=report_path,
        manifest_path=manifest_path,
    )


def _gate_entry(
    project_root: Path,
    name: str,
    *,
    passed: bool,
    checked: int,
    failed: int,
    report_path: Path,
    manifest_path: Path,
    score: int | None = None,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    entry: dict[str, object] = {
        "name": name,
        "passed": passed,
        "score": _percent(checked - failed, checked) if score is None else score,
        "checked": checked,
        "failed": failed,
        "report_path": report_path.relative_to(project_root).as_posix(),
        "manifest_path": manifest_path.relative_to(project_root).as_posix(),
    }
    if extra:
        entry.update(extra)
    return entry


def _tutoring_total_score(project_root: Path, session_id: str) -> int:
    manifest_path = project_root / "08_evals" / "tutoring_quality_manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return 0
    sessions = manifest.get("sessions", []) if isinstance(manifest, dict) else []
    if not isinstance(sessions, list):
        return 0
    for item in sessions:
        if not isinstance(item, dict) or item.get("session_id") != session_id:
            continue
        total_score = item.get("total_score")
        return total_score if isinstance(total_score, int) else 0
    return 0


def _session_score_report(
    session_id: str,
    gates: list[dict[str, object]],
    *,
    score: int,
    passed_gates: int,
    status: str,
) -> str:
    lines = [
        "# Session Score Report",
        "",
        "## Summary",
        "",
        f"- Session: {session_id}",
        f"- Status: {status}",
        f"- Session score: {score}/100",
        f"- Gates passed: {passed_gates}/{len(gates)}",
        "- Quality boundary: advisory_checklist",
        "",
        "## Gates",
        "",
    ]
    for gate in gates:
        gate_status = "pass" if gate["passed"] is True else "fail"
        lines.append(f"- {gate['name']}: {gate_status}")
        lines.append(f"  - Score: {gate['score']}/100")
        lines.append(f"  - Checked: {gate['checked']}")
        lines.append(f"  - Failed: {gate['failed']}")
        lines.append(f"  - Report: {gate['report_path']}")
        lines.append(f"  - Manifest: {gate['manifest_path']}")
    return "\n".join(lines) + "\n"


def _percent(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        return 0
    return round((numerator / denominator) * 100)
