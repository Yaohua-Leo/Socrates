"""Checklist-based quality checks for generated artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import json
from pathlib import Path
import re

from .context import load_project, write_json, write_text
from .contracts import (
    EXERCISE_ALLOWED_REVIEW_STATUSES,
    EXERCISE_ALLOWED_STATUSES,
    EXERCISE_ALLOWED_TYPES,
    REVIEW_ALLOWED_PRIORITIES,
)
from .kb import find_counterexamples, parse_object_heading, reference_kb_status
from .obsidian import obsidian_export_count
from .project import slugify_topic
from .state import ensure_learning_state_readable


@dataclass(frozen=True)
class ExerciseQualityResult:
    """Summary of a generated-exercise quality check."""

    checked: int
    passed: int
    failed: int
    report_path: Path
    manifest_path: Path


@dataclass(frozen=True)
class NoteQualityResult:
    """Summary of an atomic-note quality check."""

    checked: int
    passed: int
    failed: int
    report_path: Path
    manifest_path: Path


@dataclass(frozen=True)
class TutoringQualityResult:
    """Summary of a tutoring-session quality check."""

    session_id: str
    status: str
    report_path: Path
    manifest_path: Path


@dataclass(frozen=True)
class IngestionQualityResult:
    """Summary of curated-reference ingestion quality checks."""

    checked: int
    passed: int
    failed: int
    object_count: int
    report_path: Path
    manifest_path: Path


@dataclass(frozen=True)
class BenchmarkResult:
    """Summary of a project-level quality benchmark run."""

    total_gates: int
    passed_gates: int
    score: int
    report_path: Path
    manifest_path: Path


@dataclass(frozen=True)
class LifecycleAuditResult:
    """Summary of a persisted lifecycle completion audit."""

    total_checks: int
    passed_checks: int
    report_path: Path


REQUIRED_FRONTMATTER = ("status:", "review_status:", "type:", "concept:", "difficulty:")
REQUIRED_SECTIONS = (
    "## Target Training Point",
    "## Concepts",
    "## Prerequisites",
    "## Hints",
    "## Solution Outline",
    "## Rubric",
    "## Common Mistakes",
)
NOTE_REQUIRED_FRONTMATTER = (
    "status:",
    "review_status:",
    "reviewed_by_user:",
    "type:",
    "topic:",
    "concept:",
    "created_by:",
    "source_id:",
    "tags:",
    "related:",
)
NOTE_ALLOWED_STATUSES = {"draft", "reviewed"}
NOTE_ALLOWED_REVIEW_STATUSES = {"needs_review", "approved"}
NOTE_ALLOWED_TYPES = {
    "definition",
    "theorem",
    "example",
    "counterexample",
    "technique",
    "proof_pattern",
    "exercise",
    "misconception",
}
NOTE_REQUIRED_SECTIONS = (
    "## Key Examples",
    "## Non-Examples",
    "## Common Mistakes",
    "## Review Questions",
)
SESSION_REQUIRED_FILES = (
    "transcript.md",
    "tutor_notes.md",
    "detected_misconceptions.md",
    "summary.md",
    "next_actions.md",
)
RUBRIC_POINT_PATTERN = re.compile(r":\s*(\d+)\s+pts\b")

def check_generated_exercise_quality(project_path: Path | str) -> ExerciseQualityResult:
    """Check generated exercise drafts and write a quality report."""

    context = load_project(project_path)
    exercise_paths = sorted(context.generated_exercises_dir.glob("*.md"))
    rows = [_check_exercise(path) for path in exercise_paths]
    counterexample_rows = [
        _exercise_counterexample_search(context.root, path)
        for path in exercise_paths
    ]
    tool_verification_rows = [
        _exercise_tool_verification_evidence(context.root, path)
        for path in exercise_paths
    ]
    passed = sum(1 for row in rows if row["status"] == "pass")
    failed = len(rows) - passed
    report_path = context.evals_dir / "exercise_quality_eval.md"
    manifest_path = context.evals_dir / "exercise_quality_manifest.json"
    write_text(
        report_path,
        _exercise_quality_report(
            rows,
            passed,
            failed,
            counterexample_rows,
            tool_verification_rows,
        ),
    )
    write_json(
        manifest_path,
        _exercise_quality_manifest(
            context.root,
            exercise_paths,
            rows,
            counterexample_rows,
            tool_verification_rows,
            passed=passed,
            failed=failed,
        ),
    )
    return ExerciseQualityResult(
        checked=len(rows),
        passed=passed,
        failed=failed,
        report_path=report_path,
        manifest_path=manifest_path,
    )


def check_atomic_note_quality(project_path: Path | str) -> NoteQualityResult:
    """Check atomic notes and write a note-quality report."""

    context = load_project(project_path)
    note_paths = _atomic_note_paths(context.root)
    rows = [_check_note(path, context.root) for path in note_paths]
    passed = sum(1 for row in rows if row["status"] == "pass")
    failed = len(rows) - passed
    report_path = context.evals_dir / "note_quality_eval.md"
    manifest_path = context.evals_dir / "note_quality_manifest.json"
    write_text(report_path, _note_quality_report(rows, passed, failed))
    write_json(
        manifest_path,
        _note_quality_manifest(
            context.root,
            note_paths,
            rows,
            passed=passed,
            failed=failed,
        ),
    )
    return NoteQualityResult(
        checked=len(rows),
        passed=passed,
        failed=failed,
        report_path=report_path,
        manifest_path=manifest_path,
    )


def check_tutoring_session_quality(
    project_path: Path | str,
    *,
    session_id: str,
) -> TutoringQualityResult:
    """Check one tutoring session and append a tutoring quality report."""

    context = load_project(project_path)
    session_dir = context.sessions_dir / session_id
    missing = [name for name in SESSION_REQUIRED_FILES if not (session_dir / name).exists()]
    transcript_path = session_dir / "transcript.md"
    transcript = transcript_path.read_text(encoding="utf-8") if transcript_path.exists() else ""
    issues: list[str] = []
    if missing:
        issues.append("missing required session artifacts")
    has_tutor_question = "Tutor:" in transcript
    if not has_tutor_question:
        issues.append("missing tutor question")
    hint_count = _line_prefix_count(transcript, "Hint ")
    if hint_count == 0:
        issues.append("missing first hint")
    elif hint_count < 2:
        issues.append("incomplete hint ladder")
    student_attempt_count = _line_prefix_count(transcript, "Student attempt:")
    if student_attempt_count == 0:
        issues.append("missing student attempt")
    premature_solution = _has_premature_solution(transcript)
    if premature_solution:
        issues.append("premature full solution")
    rubric = _tutoring_rubric(
        missing=missing,
        has_tutor_question=has_tutor_question,
        has_hint_ladder=hint_count >= 2,
        has_student_attempt=student_attempt_count > 0,
        premature_solution=premature_solution,
    )

    status = "fail" if issues else "pass"
    report_path = context.evals_dir / "tutoring_eval.md"
    manifest_path = context.evals_dir / "tutoring_quality_manifest.json"
    _append_report(
        report_path,
        _tutoring_quality_report(
            session_id,
            status,
            missing,
            has_tutor_question,
            hint_count,
            student_attempt_count,
            premature_solution,
            issues,
            rubric,
        ),
    )
    write_json(
        manifest_path,
        _updated_tutoring_quality_manifest(
            context.root,
            manifest_path,
            session_id=session_id,
            session_dir=session_dir,
            status=status,
            missing=missing,
            transcript=transcript,
            premature_solution=premature_solution,
            issues=issues,
            rubric=rubric,
        ),
    )
    return TutoringQualityResult(
        session_id=session_id,
        status=status,
        report_path=report_path,
        manifest_path=manifest_path,
    )


def _updated_tutoring_quality_manifest(
    project_root: Path,
    manifest_path: Path,
    *,
    session_id: str,
    session_dir: Path,
    status: str,
    missing: list[str],
    transcript: str,
    premature_solution: bool,
    issues: list[str],
    rubric: dict[str, int],
) -> dict[str, object]:
    sessions = _existing_tutoring_manifest_sessions(manifest_path)
    session_entry = _tutoring_manifest_entry(
        project_root,
        session_id=session_id,
        session_dir=session_dir,
        status=status,
        missing=missing,
        transcript=transcript,
        premature_solution=premature_solution,
        issues=issues,
        rubric=rubric,
    )
    by_session_id = {
        str(item.get("session_id", "")): item
        for item in sessions
        if isinstance(item, dict) and item.get("session_id")
    }
    by_session_id[session_id] = session_entry
    checked_sessions = sorted(
        by_session_id.values(),
        key=lambda item: str(item.get("session_id", "")),
    )
    return {
        "schema_version": 1,
        "checked": len(checked_sessions),
        "passed": sum(1 for item in checked_sessions if item.get("status") == "pass"),
        "failed": sum(1 for item in checked_sessions if item.get("status") == "fail"),
        "sessions": checked_sessions,
    }


def _existing_tutoring_manifest_sessions(manifest_path: Path) -> list[dict[str, object]]:
    if not manifest_path.exists():
        return []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    sessions = manifest.get("sessions", []) if isinstance(manifest, dict) else []
    return [item for item in sessions if isinstance(item, dict)]


def _tutoring_manifest_entry(
    project_root: Path,
    *,
    session_id: str,
    session_dir: Path,
    status: str,
    missing: list[str],
    transcript: str,
    premature_solution: bool,
    issues: list[str],
    rubric: dict[str, int],
) -> dict[str, object]:
    return {
        "session_id": session_id,
        "path": session_dir.relative_to(project_root).as_posix(),
        "status": status,
        "missing_artifacts": missing,
        "artifacts": _session_artifact_manifest(project_root, session_dir),
        "transcript_checks": {
            "has_tutor_question": "Tutor:" in transcript,
            "hint_count": _line_prefix_count(transcript, "Hint "),
            "student_attempt_count": _line_prefix_count(transcript, "Student attempt:"),
            "premature_solution": premature_solution,
        },
        "rubric": rubric,
        "total_score": sum(rubric.values()),
        "issues": issues,
    }


def _session_artifact_manifest(project_root: Path, session_dir: Path) -> dict[str, object]:
    return {
        file_name: {
            "exists": (session_dir / file_name).exists(),
            "path": (session_dir / file_name).relative_to(project_root).as_posix(),
        }
        for file_name in SESSION_REQUIRED_FILES
    }


def check_reference_ingestion_quality(project_path: Path | str) -> IngestionQualityResult:
    """Check curated reference files for extractable KB objects."""

    context = load_project(project_path)
    curated_paths = sorted((context.references_dir / "curated").glob("*.md"))
    rows = [_check_curated_reference(path) for path in curated_paths]
    passed = sum(1 for row in rows if row["status"] == "pass")
    failed = len(rows) - passed
    object_count = sum(int(row["object_count"]) for row in rows)
    report_path = context.evals_dir / "ingestion_eval.md"
    manifest_path = context.evals_dir / "ingestion_quality_manifest.json"
    write_text(report_path, _ingestion_quality_report(rows, passed, failed, object_count))
    write_json(
        manifest_path,
        _ingestion_quality_manifest(
            context.root,
            curated_paths,
            rows,
            passed=passed,
            failed=failed,
            object_count=object_count,
        ),
    )
    return IngestionQualityResult(
        checked=len(rows),
        passed=passed,
        failed=failed,
        object_count=object_count,
        report_path=report_path,
        manifest_path=manifest_path,
    )


def run_project_benchmark(
    project_path: Path | str,
    *,
    session_id: str,
) -> BenchmarkResult:
    """Run the deterministic project-quality benchmark suite."""

    context = load_project(project_path)
    ingestion = check_reference_ingestion_quality(context.root)
    note = check_atomic_note_quality(context.root)
    exercise = check_generated_exercise_quality(context.root)
    tutoring = check_tutoring_session_quality(context.root, session_id=session_id)
    gates = {
        "Ingestion": ingestion.failed == 0 and ingestion.checked > 0,
        "Note quality": note.failed == 0 and note.checked > 0,
        "Exercise quality": exercise.failed == 0 and exercise.checked > 0,
        "Tutoring quality": tutoring.status == "pass",
    }
    passed_gates = sum(1 for passed in gates.values() if passed)
    score = _benchmark_score(passed_gates, len(gates))
    report_path = context.evals_dir / "benchmark_report.md"
    manifest_path = context.evals_dir / "benchmark_manifest.json"
    write_text(report_path, _benchmark_report(gates, score=score))
    write_json(
        manifest_path,
        _benchmark_manifest(
            context.root,
            gates,
            score=score,
            ingestion=ingestion,
            note=note,
            exercise=exercise,
            tutoring=tutoring,
        ),
    )
    return BenchmarkResult(
        total_gates=len(gates),
        passed_gates=passed_gates,
        score=score,
        report_path=report_path,
        manifest_path=manifest_path,
    )


def audit_project_lifecycle(project_path: Path | str) -> LifecycleAuditResult:
    """Check whether the project has persisted artifacts for the full learning loop."""

    context = load_project(project_path)
    ensure_learning_state_readable(
        context.learning_state,
        action="auditing project lifecycle",
    )
    state = _read_learning_state(context.learning_state)
    kb_status = reference_kb_status(context.root)
    checks = {
        "Project metadata": context.project_file.exists() and context.learning_state.exists(),
        "Reference KB": kb_status.object_count > 0 and kb_status.status == "current",
        "Learning plans": _has_learning_plans(context.root),
        "Tutoring session artifacts": _has_complete_session(context.sessions_dir),
        "Reviewed atomic notes": _reviewed_note_count(context.root) > 0,
    }
    if _has_misconception_records(state):
        checks["Misconception notes"] = _has_reviewed_misconception_notes(
            context.root,
            state,
        )
    checks.update(
        {
            "Obsidian export": obsidian_export_count(context.root) > 0,
            "Generated exercises": _markdown_count(context.generated_exercises_dir) >= 5,
            "Exercise attempts": _markdown_count(context.root / "05_exercises" / "attempted") > 0,
            "Graded exercises": _markdown_count(context.root / "05_exercises" / "graded") > 0,
            "Learning state": bool(state.get("concept_mastery")),
            "Review schedule": _has_review_schedule(context.root, state),
            "Learning reports": _has_learning_reports(context.root),
            "Benchmark report": _has_benchmark_report(context.root),
            "Benchmark manifest": _has_benchmark_manifest(context.root),
            "Tool verification records": _has_tool_verification_records(context.root),
        }
    )
    report_path = context.evals_dir / "lifecycle_eval.md"
    write_text(report_path, _lifecycle_report(checks))
    return LifecycleAuditResult(
        total_checks=len(checks),
        passed_checks=sum(1 for passed in checks.values() if passed),
        report_path=report_path,
    )


def _check_exercise(path: Path) -> dict[str, object]:
    issues = exercise_quality_issues(path)
    return {
        "file": path.name,
        "status": "fail" if issues else "pass",
        "issues": issues,
    }


def exercise_quality_issues(path: Path) -> list[str]:
    """Return checklist issues for one generated exercise file."""

    text = path.read_text(encoding="utf-8")
    issues: list[str] = []
    if not text.startswith("---\n"):
        issues.append("missing YAML frontmatter")
    for field in REQUIRED_FRONTMATTER:
        if field not in text:
            issues.append(f"missing frontmatter field {field.rstrip(':')}")
    if _invalid_exercise_status(text):
        issues.append("invalid exercise status")
    if _invalid_exercise_review_status(text):
        issues.append("invalid exercise review_status")
    if _invalid_exercise_type(text):
        issues.append("invalid exercise type")
    if _approved_exercise_missing_user_review(text):
        issues.append("missing exercise user review")
    if _is_generated_exercise(text) and _missing_source_id(text):
        issues.append("missing source id")
    if _is_targeted_review_exercise(text):
        if _missing_frontmatter_value(text, "priority"):
            issues.append("missing targeted review priority")
        elif _invalid_frontmatter_choice(text, "priority", REVIEW_ALLOWED_PRIORITIES):
            issues.append("invalid targeted review priority")
        if _missing_frontmatter_value(text, "due"):
            issues.append("missing targeted review due")
        if _missing_frontmatter_value(text, "scheduled_for"):
            issues.append("missing targeted review scheduled_for")
        elif _invalid_frontmatter_iso_date(text, "scheduled_for"):
            issues.append("invalid targeted review scheduled_for")
    if "difficulty:" in text and not _has_valid_exercise_difficulty(text):
        issues.append("invalid difficulty")
    if not _has_statement_or_review_prompt(text):
        issues.append("missing statement or review prompt")
    for section in REQUIRED_SECTIONS:
        if section not in text:
            issues.append(f"missing section {section.removeprefix('## ')}")
    if "## Concepts" in text and not _has_concept_tags(text):
        issues.append("missing concept tags")
    if "## Prerequisites" in text and not _has_prerequisites(text):
        issues.append("missing prerequisites")
    if "## Target Training Point" in text and not _has_target_training_point(text):
        issues.append("missing target training point")
    if "## Common Mistakes" in text and not _has_common_mistakes(text):
        issues.append("missing common mistakes")
    if not _has_hint_ladder(text):
        issues.append("missing hint ladder")
    elif not _has_progressive_hint_ladder(text):
        issues.append("non-progressive hint ladder")
    if not _has_solution_steps(text):
        issues.append("missing structured solution steps")
    if not _has_rubric_points(text):
        issues.append("missing rubric point values")
    elif not _rubric_points_sum_to_total(text):
        issues.append("rubric point values do not sum to total")
    return issues


def _exercise_counterexample_search(project_root: Path, exercise_path: Path) -> dict[str, object]:
    text = exercise_path.read_text(encoding="utf-8")
    concept = _frontmatter_value(text, "concept") or ""
    if not concept:
        return {
            "file": exercise_path.name,
            "concept": "",
            "status": "skipped",
            "reason": "missing concept frontmatter",
            "matches": [],
        }

    index_path = project_root / "06_kb" / "chunks" / "reference_index.json"
    if not index_path.exists():
        return {
            "file": exercise_path.name,
            "concept": concept,
            "status": "not_run",
            "reason": "reference KB index missing",
            "matches": [],
        }

    try:
        matches = find_counterexamples(project_root, concept, limit=3)
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        if isinstance(exc, ValueError) and "Reference KB index" not in str(exc):
            raise
        return {
            "file": exercise_path.name,
            "concept": concept,
            "status": "not_run",
            "reason": "reference KB index unreadable",
            "matches": [],
        }

    return {
        "file": exercise_path.name,
        "concept": concept,
        "status": "searched",
        "reason": "",
        "matches": matches,
    }


def _exercise_tool_verification_evidence(
    project_root: Path,
    exercise_path: Path,
) -> dict[str, object]:
    manifest_path = project_root / "08_evals" / "tool_verification" / "manifest.json"
    if not manifest_path.exists():
        return {
            "file": exercise_path.name,
            "exercise_id": exercise_path.stem,
            "status": "not_run",
            "reason": "tool-verification manifest missing",
            "records": [],
        }
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "file": exercise_path.name,
            "exercise_id": exercise_path.stem,
            "status": "not_run",
            "reason": "tool-verification manifest unreadable",
            "records": [],
        }
    records = manifest.get("records", []) if isinstance(manifest, dict) else []
    if not isinstance(records, list):
        return {
            "file": exercise_path.name,
            "exercise_id": exercise_path.stem,
            "status": "not_run",
            "reason": "tool-verification manifest has invalid records",
            "records": [],
        }
    linked_records = [
        record
        for record in records
        if isinstance(record, dict)
        and str(record.get("object_id", "")).strip() == exercise_path.stem
    ]
    return {
        "file": exercise_path.name,
        "exercise_id": exercise_path.stem,
        "status": "linked" if linked_records else "not_linked",
        "reason": "" if linked_records else "no matching tool-verification record",
        "records": linked_records,
        "quality": (
            _exercise_tool_verification_quality(project_root, exercise_path.stem)
            if linked_records
            else {"status": "not_applicable", "reason": "", "records": []}
        ),
    }


def _exercise_tool_verification_quality(
    project_root: Path,
    exercise_id: str,
) -> dict[str, object]:
    manifest_path = project_root / "08_evals" / "tool_verification_quality_manifest.json"
    source_manifest_path = project_root / "08_evals" / "tool_verification" / "manifest.json"
    if not manifest_path.exists():
        return {
            "status": "not_run",
            "reason": "tool-verification check not run",
            "records": [],
        }
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "status": "invalid",
            "reason": "tool-verification quality manifest unreadable",
            "records": [],
        }
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        return {
            "status": "invalid",
            "reason": "tool-verification quality manifest has invalid schema",
            "records": [],
        }
    records = manifest.get("records", [])
    if not isinstance(records, list):
        return {
            "status": "invalid",
            "reason": "tool-verification quality manifest has invalid records",
            "records": [],
        }

    linked_quality_records = [
        record
        for record in records
        if isinstance(record, dict)
        and str(record.get("object_id", "")).strip() == exercise_id
    ]
    staleness_reasons = _tool_verification_quality_staleness_reasons(
        manifest,
        manifest_path,
        source_manifest_path,
    )
    staleness_reasons.extend(
        _tool_verification_record_staleness_reasons(
            project_root,
            linked_quality_records,
        )
    )
    if staleness_reasons:
        return {
            "status": "stale",
            "reason": staleness_reasons[0],
            "reasons": staleness_reasons,
            "records": linked_quality_records,
        }
    if not linked_quality_records:
        return {
            "status": "not_found",
            "reason": "no matching tool-verification quality record",
            "records": [],
        }

    statuses = [
        str(record.get("quality_status", "")).strip()
        for record in linked_quality_records
        if isinstance(record, dict)
    ]
    if any(status == "fail" for status in statuses):
        status = "fail"
    elif statuses and all(status == "pass" for status in statuses):
        status = "pass"
    else:
        status = "unknown"
    return {"status": status, "reason": "", "records": linked_quality_records}


def _tool_verification_record_staleness_reasons(
    project_root: Path,
    records: list[object],
) -> list[str]:
    reasons: list[str] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        if _record_fingerprint_changed(
            project_root,
            record.get("artifact_path"),
            record.get("artifact_fingerprint"),
        ):
            reasons.append("tool-verification artifact fingerprint changed")
        if _record_fingerprint_changed(
            project_root,
            record.get("report_path"),
            record.get("report_fingerprint"),
        ):
            reasons.append("tool-verification report fingerprint changed")
    return _dedupe_preserving_order(reasons)


def _record_fingerprint_changed(
    project_root: Path,
    relative_path: object,
    fingerprint: object,
) -> bool:
    if not isinstance(relative_path, str) or not relative_path.strip():
        return False
    if not isinstance(fingerprint, dict):
        return False
    algorithm = str(fingerprint.get("algorithm", "")).strip()
    value = str(fingerprint.get("value", "")).strip()
    if algorithm != "sha256" or not value:
        return False
    path = Path(relative_path)
    if path.is_absolute() or ".." in path.parts:
        return False
    resolved = project_root / path
    if not resolved.exists():
        return True
    return hashlib.sha256(resolved.read_bytes()).hexdigest() != value


def _tool_verification_quality_staleness_reasons(
    manifest: dict[str, object],
    manifest_path: Path,
    source_manifest_path: Path,
) -> list[str]:
    fingerprint = manifest.get("source_manifest_fingerprint")
    if isinstance(fingerprint, dict):
        algorithm = str(fingerprint.get("algorithm", "")).strip()
        value = str(fingerprint.get("value", "")).strip()
        if algorithm == "sha256" and value:
            if not source_manifest_path.exists():
                return []
            current_value = hashlib.sha256(source_manifest_path.read_bytes()).hexdigest()
            if current_value != value:
                return ["tool-verification source manifest fingerprint changed"]
            return []
    if not source_manifest_path.exists():
        return []
    if source_manifest_path.stat().st_mtime > manifest_path.stat().st_mtime:
        return ["tool-verification check is older than source manifest"]
    return []


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _exercise_quality_manifest(
    project_root: Path,
    exercise_paths: list[Path],
    rows: list[dict[str, object]],
    counterexample_rows: list[dict[str, object]],
    tool_verification_rows: list[dict[str, object]],
    *,
    passed: int,
    failed: int,
) -> dict[str, object]:
    row_by_file = {str(row["file"]): row for row in rows}
    counterexample_by_file = {
        str(row["file"]): row for row in counterexample_rows
    }
    tool_verification_by_file = {
        str(row["file"]): row for row in tool_verification_rows
    }
    return {
        "schema_version": 1,
        "checked": len(exercise_paths),
        "passed": passed,
        "failed": failed,
        "exercises": [
            _exercise_manifest_entry(
                project_root,
                exercise_path,
                row_by_file.get(exercise_path.name, {}),
                counterexample_by_file.get(exercise_path.name, {}),
                tool_verification_by_file.get(exercise_path.name, {}),
            )
            for exercise_path in exercise_paths
        ],
    }


def _exercise_manifest_entry(
    project_root: Path,
    exercise_path: Path,
    quality_row: dict[str, object],
    counterexample_row: dict[str, object],
    tool_verification_row: dict[str, object],
) -> dict[str, object]:
    text = exercise_path.read_text(encoding="utf-8")
    issues = quality_row.get("issues", [])
    if not isinstance(issues, list):
        issues = []
    return {
        "id": exercise_path.stem,
        "path": exercise_path.relative_to(project_root).as_posix(),
        "quality_status": quality_row.get("status", "unknown"),
        "issues": issues,
        "frontmatter": _exercise_frontmatter(text),
        "sections": _exercise_section_manifest(text),
        "counterexample_search": _counterexample_search_manifest(counterexample_row),
        "tool_verification": _tool_verification_evidence_manifest(tool_verification_row),
    }


def _exercise_frontmatter(text: str) -> dict[str, object]:
    keys = (
        "status",
        "review_status",
        "reviewed_by_user",
        "type",
        "concept",
        "source_id",
        "difficulty",
        "priority",
        "due",
        "scheduled_for",
    )
    values: dict[str, object] = {}
    for key in keys:
        value = _frontmatter_value(text, key)
        if value is None:
            continue
        if key == "difficulty":
            values[key] = _int_if_possible(value)
        elif key == "reviewed_by_user":
            values[key] = _bool_if_possible(value)
        else:
            values[key] = value
    return values


def _exercise_section_manifest(text: str) -> dict[str, object]:
    return {
        "has_statement": "## Statement" in text,
        "has_review_prompt": "## Review Prompt" in text,
        "has_target_training_point": "## Target Training Point" in text,
        "hint_count": _numbered_line_count(_section_text(text, "## Hints"), "Hint "),
        "solution_step_count": _numbered_line_count(
            _section_text(text, "## Solution Outline"),
            "Step ",
        ),
        "rubric_total_points": _rubric_total_points(text),
        "has_common_mistakes": "## Common Mistakes" in text,
    }


def _counterexample_search_manifest(row: dict[str, object]) -> dict[str, object]:
    matches = row.get("matches", [])
    if not isinstance(matches, list):
        matches = []
    result: dict[str, object] = {
        "status": row.get("status", "unknown"),
        "match_count": len(matches),
        "matches": [_counterexample_manifest_match(match) for match in matches],
    }
    if row.get("reason"):
        result["reason"] = row["reason"]
    return result


def _counterexample_manifest_match(match: dict[str, object]) -> dict[str, object]:
    source = match.get("source", {})
    if not isinstance(source, dict):
        source = {}
    result: dict[str, object] = {
        "id": str(match.get("id", "")),
        "type": str(match.get("type", "")),
        "title": str(match.get("title", "")),
        "source_path": str(source.get("path") or "unknown"),
    }
    if source.get("line"):
        result["line"] = source["line"]
    if source.get("page"):
        result["page"] = source["page"]
    return result


def _tool_verification_evidence_manifest(row: dict[str, object]) -> dict[str, object]:
    records = row.get("records", [])
    if not isinstance(records, list):
        records = []
    quality = row.get("quality", {})
    if not isinstance(quality, dict):
        quality = {}
    quality_records = quality.get("records", [])
    if not isinstance(quality_records, list):
        quality_records = []
    result: dict[str, object] = {
        "status": row.get("status", "unknown"),
        "record_count": len(records),
        "records": [_tool_verification_manifest_record(record) for record in records],
        "quality_status": quality.get("status", "unknown"),
        "quality_records": [
            _tool_verification_quality_manifest_record(record)
            for record in quality_records
        ],
    }
    if row.get("reason"):
        result["reason"] = row["reason"]
    if quality.get("reason"):
        result["quality_reason"] = quality["reason"]
    reasons = quality.get("reasons", [])
    if isinstance(reasons, list) and reasons:
        result["quality_reasons"] = [str(reason) for reason in reasons]
    return result


def _tool_verification_manifest_record(record: object) -> dict[str, object]:
    if not isinstance(record, dict):
        return {"kind": "", "status": "", "artifact_path": "", "report_path": ""}
    return {
        "kind": str(record.get("kind", "")),
        "status": str(record.get("status", "")),
        "artifact_path": str(
            record.get("skeleton_path")
            or record.get("artifact_path")
            or record.get("output_path")
            or ""
        ),
        "report_path": str(record.get("report_path", "")),
    }


def _tool_verification_quality_manifest_record(record: object) -> dict[str, object]:
    if not isinstance(record, dict):
        return {
            "kind": "",
            "record_status": "",
            "quality_status": "",
            "artifact_path": "",
            "report_path": "",
            "issues": [],
        }
    issues = record.get("issues", [])
    if not isinstance(issues, list):
        issues = []
    return {
        "kind": str(record.get("kind", "")),
        "record_status": str(record.get("record_status", "")),
        "quality_status": str(record.get("quality_status", "")),
        "artifact_path": str(record.get("artifact_path", "")),
        "report_path": str(record.get("report_path", "")),
        "artifact_fingerprint": _quality_record_fingerprint(record.get("artifact_fingerprint")),
        "report_fingerprint": _quality_record_fingerprint(record.get("report_fingerprint")),
        "issues": [str(issue) for issue in issues],
    }


def _quality_record_fingerprint(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {"algorithm": "sha256", "value": ""}
    return {
        "algorithm": str(value.get("algorithm", "")),
        "value": str(value.get("value", "")),
    }


def _int_if_possible(value: str) -> object:
    try:
        return int(value)
    except ValueError:
        return value


def _bool_if_possible(value: str) -> object:
    normalized = value.casefold()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    return value


def _frontmatter_value(text: str, key: str) -> str | None:
    if not text.startswith("---\n"):
        return None
    parts = text.split("---\n", 2)
    if len(parts) != 3:
        return None
    prefix = f"{key}:"
    for line in parts[1].splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip().strip('"')
    return None


def _frontmatter_list(text: str, key: str) -> list[str]:
    frontmatter = _frontmatter_lines(text)
    prefix = f"{key}:"
    values: list[str] = []
    in_list = False
    for line in frontmatter:
        if line.startswith(prefix):
            in_list = True
            inline_value = line.removeprefix(prefix).strip()
            if inline_value == "[]":
                return []
            if inline_value:
                return [_frontmatter_string(inline_value)]
            continue
        if not in_list:
            continue
        stripped = line.strip()
        if stripped == "[]":
            return []
        if line.startswith("  - "):
            values.append(_frontmatter_string(line.removeprefix("  - ").strip()))
            continue
        if stripped and not line.startswith(" "):
            break
    return values


def _frontmatter_lines(text: str) -> list[str]:
    if not text.startswith("---\n"):
        return []
    parts = text.split("---\n", 2)
    if len(parts) != 3:
        return []
    return parts[1].splitlines()


def _frontmatter_string(value: str) -> str:
    if (
        (value.startswith('"') and value.endswith('"'))
        or (value.startswith("'") and value.endswith("'"))
    ):
        return value[1:-1]
    return value


def _has_hint_ladder(text: str) -> bool:
    hint_section = _section_text(text, "## Hints")
    return all(f"Hint {index}" in hint_section for index in range(1, 4))


def _has_progressive_hint_ladder(text: str) -> bool:
    hints = _hint_ladder_lines(text)
    if len(hints) < 3:
        return False
    normalized = {_normalize_hint_text(hint) for hint in hints[:3]}
    return len(normalized) == 3


def _has_valid_exercise_difficulty(text: str) -> bool:
    value = _frontmatter_value(text, "difficulty")
    if value is None:
        return False
    try:
        difficulty = int(value)
    except ValueError:
        return False
    return 1 <= difficulty <= 5


def _has_concept_tags(text: str) -> bool:
    return _has_real_bullet(_section_text(text, "## Concepts"))


def _has_prerequisites(text: str) -> bool:
    return _has_real_bullet(_section_text(text, "## Prerequisites"))


def _has_common_mistakes(text: str) -> bool:
    return _has_real_bullet(_section_text(text, "## Common Mistakes"))


def _has_target_training_point(text: str) -> bool:
    return _has_section_content(_section_text(text, "## Target Training Point"))


def _has_statement_or_review_prompt(text: str) -> bool:
    return _has_section_content(_section_text(text, "## Statement")) or _has_section_content(
        _section_text(text, "## Review Prompt")
    )


def _has_real_bullet(section: str) -> bool:
    for line in section.splitlines():
        value = line.strip()
        if not value.startswith("- "):
            continue
        tag = value.removeprefix("- ").strip()
        if tag and tag.casefold() != "none recorded.":
            return True
    return False


def _has_section_content(section: str) -> bool:
    for line in section.splitlines():
        value = line.strip()
        if value and value.casefold() != "none recorded.":
            return True
    return False


def _is_generated_exercise(text: str) -> bool:
    return _frontmatter_value(text, "type") == "generated_exercise"


def _is_targeted_review_exercise(text: str) -> bool:
    return _frontmatter_value(text, "type") == "targeted_review_exercise"


def _missing_source_id(text: str) -> bool:
    return _missing_frontmatter_value(text, "source_id")


def _missing_frontmatter_value(text: str, key: str) -> bool:
    value = _frontmatter_value(text, key)
    return value is None or value in {"", "null"}


def _invalid_exercise_status(text: str) -> bool:
    return _invalid_frontmatter_choice(text, "status", EXERCISE_ALLOWED_STATUSES)


def _invalid_exercise_review_status(text: str) -> bool:
    return _invalid_frontmatter_choice(
        text,
        "review_status",
        EXERCISE_ALLOWED_REVIEW_STATUSES,
    )


def _invalid_exercise_type(text: str) -> bool:
    return _invalid_frontmatter_choice(text, "type", EXERCISE_ALLOWED_TYPES)


def _approved_exercise_missing_user_review(text: str) -> bool:
    approved = (
        _frontmatter_value(text, "status") == "approved"
        or _frontmatter_value(text, "review_status") == "approved"
    )
    if not approved:
        return False
    value = _frontmatter_value(text, "reviewed_by_user")
    return value is None or value.casefold() != "true"


def _hint_ladder_lines(text: str) -> list[str]:
    hint_section = _section_text(text, "## Hints")
    return [
        line.strip().lstrip("- ").strip()
        for line in hint_section.splitlines()
        if line.strip().lstrip("- ").startswith("Hint ")
    ]


def _normalize_hint_text(hint: str) -> str:
    if ":" in hint:
        hint = hint.split(":", 1)[1]
    return " ".join(hint.casefold().split())


def _has_solution_steps(text: str) -> bool:
    solution_section = _section_text(text, "## Solution Outline")
    return all(f"Step {index}:" in solution_section for index in range(1, 4))


def _has_rubric_points(text: str) -> bool:
    rubric_section = _section_text(text, "## Rubric")
    return "Total: 10 pts" in rubric_section and sum(
        1 for line in rubric_section.splitlines() if " pts" in line
    ) >= 4


def _rubric_points_sum_to_total(text: str) -> bool:
    total = _rubric_total_points(text)
    if total is None:
        return False
    component_points = _rubric_component_points(text)
    if not component_points:
        return False
    return sum(component_points) == total


def _rubric_component_points(text: str) -> list[int]:
    rubric_section = _section_text(text, "## Rubric")
    points: list[int] = []
    for line in rubric_section.splitlines():
        if "Total:" in line:
            continue
        match = RUBRIC_POINT_PATTERN.search(line)
        if match:
            points.append(int(match.group(1)))
    return points


def _numbered_line_count(section: str, marker: str) -> int:
    return sum(1 for line in section.splitlines() if marker in line)


def _bullet_count(section: str) -> int:
    return sum(1 for line in section.splitlines() if line.strip().startswith("- "))


def _line_prefix_count(text: str, prefix: str) -> int:
    return sum(1 for line in text.splitlines() if line.startswith(prefix))


def _rubric_total_points(text: str) -> int | None:
    rubric_section = _section_text(text, "## Rubric")
    for line in rubric_section.splitlines():
        if "Total:" not in line or "pts" not in line:
            continue
        value = line.split("Total:", 1)[1].split("pts", 1)[0].strip()
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _section_text(text: str, heading: str) -> str:
    _, separator, after_heading = text.partition(heading)
    if not separator:
        return ""
    next_section_index = after_heading.find("\n## ")
    return after_heading if next_section_index < 0 else after_heading[:next_section_index]


def _atomic_note_paths(project_root: Path) -> list[Path]:
    notes_root = project_root / "04_atomic_notes"
    paths: list[Path] = []
    for folder in sorted(notes_root.iterdir()):
        if folder.is_dir():
            paths.extend(sorted(folder.glob("*.md")))
    return paths


def _check_note(path: Path, project_root: Path) -> dict[str, object]:
    issues = atomic_note_quality_issues(path, project_root)
    return {
        "file": path.relative_to(project_root / "04_atomic_notes").as_posix(),
        "status": "fail" if issues else "pass",
        "issues": issues,
    }


def _note_quality_manifest(
    project_root: Path,
    note_paths: list[Path],
    rows: list[dict[str, object]],
    *,
    passed: int,
    failed: int,
) -> dict[str, object]:
    row_by_file = {str(row["file"]): row for row in rows}
    return {
        "schema_version": 1,
        "checked": len(note_paths),
        "passed": passed,
        "failed": failed,
        "notes": [
            _note_manifest_entry(
                project_root,
                note_path,
                row_by_file.get(
                    note_path.relative_to(project_root / "04_atomic_notes").as_posix(),
                    {},
                ),
            )
            for note_path in note_paths
        ],
    }


def _note_manifest_entry(
    project_root: Path,
    note_path: Path,
    quality_row: dict[str, object],
) -> dict[str, object]:
    text = note_path.read_text(encoding="utf-8")
    issues = quality_row.get("issues", [])
    if not isinstance(issues, list):
        issues = []
    return {
        "id": note_path.stem,
        "path": note_path.relative_to(project_root).as_posix(),
        "quality_status": quality_row.get("status", "unknown"),
        "issues": issues,
        "frontmatter": _note_frontmatter(text),
        "sections": _note_section_manifest(text),
    }


def _note_frontmatter(text: str) -> dict[str, object]:
    values: dict[str, object] = {}
    for key in (
        "status",
        "review_status",
        "reviewed_by_user",
        "type",
        "topic",
        "concept",
        "created_by",
        "source_id",
        "source_title",
        "source_location",
    ):
        value = _frontmatter_value(text, key)
        if value is None:
            continue
        values[key] = _bool_if_possible(value) if key == "reviewed_by_user" else value
    values["tags"] = _frontmatter_list(text, "tags")
    values["related"] = _frontmatter_list(text, "related")
    return values


def _note_section_manifest(text: str) -> dict[str, object]:
    return {
        "has_title": _has_title_heading(text),
        "has_key_examples": "## Key Examples" in text,
        "has_non_examples": (
            "## Non-Examples" in text or "## Counterexamples" in text
        ),
        "has_common_mistakes": "## Common Mistakes" in text,
        "review_question_count": _bullet_count(
            _section_text(text, "## Review Questions")
        ),
        "has_reference_context": "## Reference Context" in text,
        "related_concept_count": _bullet_count(
            _section_text(text, "## Related Concepts")
        ),
    }


def atomic_note_quality_issues(path: Path, project_root: Path) -> list[str]:
    """Return checklist issues for one atomic note file."""

    text = path.read_text(encoding="utf-8")
    issues: list[str] = []
    if not text.startswith("---\n"):
        issues.append("missing YAML frontmatter")
    for field in NOTE_REQUIRED_FRONTMATTER:
        if field not in text:
            issues.append(f"missing frontmatter field {field.rstrip(':')}")
    if not _has_title_heading(text):
        issues.append("missing title heading")
    if _invalid_note_status(text):
        issues.append("invalid status")
    if _invalid_note_review_status(text):
        issues.append("invalid review_status")
    if _invalid_note_type(text):
        issues.append("invalid type")
    if _missing_note_topic(text):
        issues.append("missing topic")
    if _missing_note_concept(text):
        issues.append("missing concept")
    if _invalid_note_creator(text):
        issues.append("invalid created_by")
    if _missing_note_source_id(text):
        issues.append("missing source id")
    if _invalid_reviewed_by_user(text):
        issues.append("invalid reviewed_by_user")
    if "tags:" in text and not _frontmatter_list(text, "tags"):
        issues.append("missing tags")
    for section in NOTE_REQUIRED_SECTIONS:
        if section not in text:
            issues.append(f"missing section {section.removeprefix('## ')}")
    if "## Review Questions" in text and _bullet_count(
        _section_text(text, "## Review Questions")
    ) == 0:
        issues.append("missing review questions")
    if not _has_related_concept_link(text):
        issues.append("missing related concept links")
    return issues


def _has_related_concept_link(text: str) -> bool:
    frontmatter_links = _frontmatter_list(text, "related")
    if any("[[" in item and "]]" in item for item in frontmatter_links):
        return True
    return any(
        "[[" in line and "]]" in line
        for line in _section_text(text, "## Related Concepts").splitlines()
        if line.strip().startswith("- ")
    )


def _has_title_heading(text: str) -> bool:
    for line in text.splitlines():
        if line.startswith("# ") and line.removeprefix("# ").strip():
            return True
    return False


def _missing_note_source_id(text: str) -> bool:
    value = _frontmatter_value(text, "source_id")
    return value is None or value.casefold() in {"", "null"}


def _missing_note_concept(text: str) -> bool:
    value = _frontmatter_value(text, "concept")
    return value is None or value.casefold() in {"", "null"}


def _missing_note_topic(text: str) -> bool:
    value = _frontmatter_value(text, "topic")
    return value is None or value.casefold() in {"", "null"}


def _invalid_note_creator(text: str) -> bool:
    value = _frontmatter_value(text, "created_by")
    if value is None:
        return False
    return value.casefold() != "socrates"


def _invalid_reviewed_by_user(text: str) -> bool:
    value = _frontmatter_value(text, "reviewed_by_user")
    return value is not None and value.casefold() not in {"true", "false"}


def _invalid_note_status(text: str) -> bool:
    return _invalid_note_frontmatter_choice(text, "status", NOTE_ALLOWED_STATUSES)


def _invalid_note_review_status(text: str) -> bool:
    return _invalid_note_frontmatter_choice(
        text, "review_status", NOTE_ALLOWED_REVIEW_STATUSES
    )


def _invalid_note_type(text: str) -> bool:
    return _invalid_note_frontmatter_choice(text, "type", NOTE_ALLOWED_TYPES)


def _invalid_note_frontmatter_choice(
    text: str, key: str, allowed_values: set[str] | frozenset[str]
) -> bool:
    return _invalid_frontmatter_choice(text, key, allowed_values)


def _invalid_frontmatter_choice(
    text: str, key: str, allowed_values: set[str] | frozenset[str]
) -> bool:
    value = _frontmatter_value(text, key)
    return value is not None and value.casefold() not in allowed_values


def _invalid_frontmatter_iso_date(text: str, key: str) -> bool:
    value = _frontmatter_value(text, key)
    if value is None:
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return True
    return False


def _check_curated_reference(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    object_count = _extractable_object_count(text)
    source_metadata = _curated_source_metadata(text)
    issues: list[str] = []
    if object_count == 0:
        issues.append("no extractable mathematical object headings")
    if "Depends:" not in text:
        issues.append("no dependency metadata")
    if not source_metadata.get("source_id"):
        issues.append("missing source id metadata")
    return {
        "file": path.name,
        "status": "fail" if issues else "pass",
        "object_count": object_count,
        "issues": issues,
    }


def _ingestion_quality_manifest(
    project_root: Path,
    curated_paths: list[Path],
    rows: list[dict[str, object]],
    *,
    passed: int,
    failed: int,
    object_count: int,
) -> dict[str, object]:
    row_by_file = {str(row["file"]): row for row in rows}
    return {
        "schema_version": 1,
        "checked": len(curated_paths),
        "passed": passed,
        "failed": failed,
        "extractable_objects": object_count,
        "raw_references_modified": False,
        "curated_only_policy": "enforced",
        "curated_references": [
            _curated_reference_manifest_entry(
                project_root,
                curated_path,
                row_by_file.get(curated_path.name, {}),
            )
            for curated_path in curated_paths
        ],
    }


def _curated_reference_manifest_entry(
    project_root: Path,
    curated_path: Path,
    quality_row: dict[str, object],
) -> dict[str, object]:
    text = curated_path.read_text(encoding="utf-8")
    issues = quality_row.get("issues", [])
    if not isinstance(issues, list):
        issues = []
    objects = _extractable_object_manifest(text)
    return {
        "file": curated_path.name,
        "path": curated_path.relative_to(project_root).as_posix(),
        "quality_status": quality_row.get("status", "unknown"),
        "issues": issues,
        "source_metadata": _curated_source_metadata(text),
        "extractable_object_count": len(objects),
        "has_dependency_metadata": "Depends:" in text,
        "objects": objects,
    }


def _curated_source_metadata(text: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        key, separator, value = stripped.removeprefix("-").strip().partition(":")
        if not separator:
            continue
        normalized_key = key.strip().casefold()
        if normalized_key in {"source_id", "title", "role", "raw_path"}:
            metadata[normalized_key] = value.strip().strip('"')
    return metadata


def _extractable_object_manifest(text: str) -> list[dict[str, object]]:
    objects: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("### "):
            parsed = parse_object_heading(stripped.removeprefix("### ").strip())
            if parsed is None:
                current = None
                continue
            object_type, title, number = parsed
            current = {
                "line": line_number,
                "type": object_type,
                "title": title,
                "dependencies": [],
            }
            if number:
                current["number"] = number
            objects.append(current)
            continue
        if current is not None and stripped.casefold().startswith("depends:"):
            current["dependencies"] = [
                item.strip()
                for item in stripped.split(":", 1)[1].split(",")
                if item.strip()
            ]
    return objects


def _extractable_object_count(text: str) -> int:
    count = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("### "):
            continue
        if parse_object_heading(stripped.removeprefix("### ").strip()) is not None:
            count += 1
    return count


def _has_premature_solution(transcript: str) -> bool:
    if "Tutor follow-up:" not in transcript:
        return False
    if "Full solution withheld until after a student attempt." in transcript:
        return False
    return "Student attempt:" not in transcript


def _exercise_quality_report(
    rows: list[dict[str, object]],
    passed: int,
    failed: int,
    counterexample_rows: list[dict[str, object]],
    tool_verification_rows: list[dict[str, object]],
) -> str:
    lines = [
        "# Exercise Quality Eval",
        "",
        "## Summary",
        "",
        f"- Drafts checked: {len(rows)}",
        f"- Passed: {passed}",
        f"- Failed: {failed}",
        "",
        "## Results",
        "",
    ]
    if not rows:
        lines.append("- No generated exercise drafts found.")
        return "\n".join(lines) + "\n"
    for row in rows:
        lines.append(f"- {row['file']}: {row['status']}")
        issues = row.get("issues", [])
        if isinstance(issues, list):
            lines.extend(f"  - {issue}" for issue in issues)
    lines.extend(["", "## Counterexample Search", ""])
    lines.extend(_counterexample_search_report(counterexample_rows))
    lines.extend(["", "## Tool Verification Evidence", ""])
    lines.extend(_tool_verification_evidence_report(tool_verification_rows))
    return "\n".join(lines) + "\n"


def _counterexample_search_report(rows: list[dict[str, object]]) -> list[str]:
    if not rows:
        return ["- No exercise drafts found."]

    lines: list[str] = []
    for row in rows:
        matches = row.get("matches", [])
        if not isinstance(matches, list):
            matches = []
        line = (
            f"- {row['file']} | {row.get('concept') or 'unknown'} | "
            f"{row['status']}"
        )
        if row["status"] == "searched":
            line = f"{line} | matches: {len(matches)}"
        elif row.get("reason"):
            line = f"{line} | {row['reason']}"
        lines.append(line)
        lines.extend(f"  - {_counterexample_match_line(match)}" for match in matches)
    return lines


def _counterexample_match_line(match: dict[str, object]) -> str:
    source = match.get("source", {})
    if not isinstance(source, dict):
        source = {}
    return (
        f"{match.get('type', 'object')}: {match.get('title', 'Untitled')} "
        f"({_counterexample_source_location(source)})"
    )


def _counterexample_source_location(source: dict[str, object]) -> str:
    path = str(source.get("path") or "unknown")
    if source.get("line"):
        return f"{path}:{source['line']}"
    if source.get("page"):
        return f"{path}:p{source['page']}"
    return path


def _tool_verification_evidence_report(rows: list[dict[str, object]]) -> list[str]:
    if not rows:
        return ["- No exercise drafts found."]

    lines: list[str] = []
    for row in rows:
        records = row.get("records", [])
        if not isinstance(records, list):
            records = []
        line = f"- {row['file']} | {row['status']}"
        if row["status"] == "linked":
            line = (
                f"{line} | records: {len(records)}"
                f"{_tool_verification_quality_suffix(row)}"
            )
        elif row.get("reason"):
            line = f"{line} | {row['reason']}"
        lines.append(line)
        lines.extend(f"  - {_tool_verification_record_line(record)}" for record in records)
    return lines


def _tool_verification_quality_suffix(row: dict[str, object]) -> str:
    quality = row.get("quality", {})
    if not isinstance(quality, dict):
        return ""
    status = str(quality.get("status", "")).strip()
    if not status or status == "not_applicable":
        return ""
    suffix = f" | quality: {status}"
    reasons = quality.get("reasons", [])
    if isinstance(reasons, list) and reasons:
        reason_text = "; ".join(str(reason) for reason in reasons if str(reason).strip())
    else:
        reason_text = str(quality.get("reason", "")).strip()
    if reason_text:
        suffix = f"{suffix} ({reason_text})"
    return suffix


def _tool_verification_record_line(record: object) -> str:
    if not isinstance(record, dict):
        return "invalid record"
    artifact_path = str(
        record.get("skeleton_path")
        or record.get("artifact_path")
        or record.get("output_path")
        or ""
    )
    return (
        f"{record.get('kind', '')} | {record.get('status', '')} | "
        f"{artifact_path}"
    )


def _note_quality_report(
    rows: list[dict[str, object]],
    passed: int,
    failed: int,
) -> str:
    lines = [
        "# Note Quality Eval",
        "",
        "## Summary",
        "",
        f"- Notes checked: {len(rows)}",
        f"- Passed: {passed}",
        f"- Failed: {failed}",
        "",
        "## Results",
        "",
    ]
    if not rows:
        lines.append("- No atomic notes found.")
        return "\n".join(lines) + "\n"
    for row in rows:
        lines.append(f"- {row['file']}: {row['status']}")
        issues = row.get("issues", [])
        if isinstance(issues, list):
            lines.extend(f"  - {issue}" for issue in issues)
    return "\n".join(lines) + "\n"


def _ingestion_quality_report(
    rows: list[dict[str, object]],
    passed: int,
    failed: int,
    object_count: int,
) -> str:
    lines = [
        "# Ingestion Eval",
        "",
        "## Summary",
        "",
        f"- Curated files checked: {len(rows)}",
        f"- Extractable objects: {object_count}",
        f"- Passed: {passed}",
        f"- Failed: {failed}",
        "",
        "## Results",
        "",
    ]
    if not rows:
        lines.append("- No curated reference files found.")
        return "\n".join(lines) + "\n"
    for row in rows:
        lines.append(f"- {row['file']}: {row['status']}")
        lines.append(f"  - Extractable objects: {row['object_count']}")
        issues = row.get("issues", [])
        if isinstance(issues, list):
            lines.extend(f"  - {issue}" for issue in issues)
    return "\n".join(lines) + "\n"


def _tutoring_quality_report(
    session_id: str,
    status: str,
    missing: list[str],
    has_tutor_question: bool,
    hint_count: int,
    student_attempt_count: int,
    premature_solution: bool,
    issues: list[str],
    rubric: dict[str, int],
) -> str:
    total_score = sum(rubric.values())
    lines = [
        f"## Session Quality Check: {session_id}",
        "",
        f"- Status: {status}",
        f"- Missing artifacts: {', '.join(missing) if missing else 'none'}",
        f"- Tutor question present: {'yes' if has_tutor_question else 'no'}",
        f"- Hint count: {hint_count}",
        f"- Student attempts: {student_attempt_count}",
        f"- Premature solution: {'yes' if premature_solution else 'no'}",
        "",
        "### Rubric",
        f"- Required artifacts: {rubric['Required artifacts']}/25",
        f"- Tutor question: {rubric['Tutor question']}/25",
        f"- Hint ladder: {rubric['Hint ladder']}/25",
        f"- Attempt before solution: {rubric['Attempt before solution']}/25",
        f"- Total score: {total_score}/100",
        "",
        "### Issues",
    ]
    lines.extend(f"- {issue}" for issue in issues)
    if not issues:
        lines.append("- none recorded")
    return "\n".join(lines) + "\n"


def _tutoring_rubric(
    *,
    missing: list[str],
    has_tutor_question: bool,
    has_hint_ladder: bool,
    has_student_attempt: bool,
    premature_solution: bool,
) -> dict[str, int]:
    return {
        "Required artifacts": 0 if missing else 25,
        "Tutor question": 25 if has_tutor_question else 0,
        "Hint ladder": 25 if has_hint_ladder else 0,
        "Attempt before solution": 25 if has_student_attempt and not premature_solution else 0,
    }


def _benchmark_score(passed_gates: int, total_gates: int) -> int:
    if total_gates == 0:
        return 0
    return round((passed_gates / total_gates) * 100)


def _benchmark_report(gates: dict[str, bool], *, score: int) -> str:
    passed_gates = sum(1 for passed in gates.values() if passed)
    lines = [
        "# Benchmark Report",
        "",
        "## Summary",
        "",
        f"- Gates passed: {passed_gates}/{len(gates)}",
        f"- Benchmark score: {score}/100",
        "",
        "## Quality Gates",
        "",
    ]
    lines.extend(
        f"- {name}: {'pass' if passed else 'fail'}"
        for name, passed in gates.items()
    )
    return "\n".join(lines) + "\n"


def _benchmark_manifest(
    project_root: Path,
    gates: dict[str, bool],
    *,
    score: int,
    ingestion: IngestionQualityResult,
    note: NoteQualityResult,
    exercise: ExerciseQualityResult,
    tutoring: TutoringQualityResult,
) -> dict[str, object]:
    gate_entries = [
        _benchmark_gate_entry(
            project_root,
            "Ingestion",
            gates["Ingestion"],
            checked=ingestion.checked,
            failed=ingestion.failed,
            report_path=ingestion.report_path,
            manifest_path=ingestion.manifest_path,
        ),
        _benchmark_gate_entry(
            project_root,
            "Note quality",
            gates["Note quality"],
            checked=note.checked,
            failed=note.failed,
            report_path=note.report_path,
            manifest_path=note.manifest_path,
        ),
        _benchmark_gate_entry(
            project_root,
            "Exercise quality",
            gates["Exercise quality"],
            checked=exercise.checked,
            failed=exercise.failed,
            report_path=exercise.report_path,
            manifest_path=exercise.manifest_path,
        ),
        _benchmark_gate_entry(
            project_root,
            "Tutoring quality",
            gates["Tutoring quality"],
            checked=1,
            failed=0 if tutoring.status == "pass" else 1,
            report_path=tutoring.report_path,
            manifest_path=tutoring.manifest_path,
            extra={
                "session_id": tutoring.session_id,
                "status": tutoring.status,
            },
        ),
    ]
    return {
        "schema_version": 1,
        "score": score,
        "passed_gates": sum(1 for gate in gate_entries if gate["passed"]),
        "total_gates": len(gate_entries),
        "gates": gate_entries,
    }


def _benchmark_gate_entry(
    project_root: Path,
    name: str,
    passed: bool,
    *,
    checked: int,
    failed: int,
    report_path: Path,
    manifest_path: Path,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    entry: dict[str, object] = {
        "name": name,
        "passed": passed,
        "checked": checked,
        "failed": failed,
        "report_path": report_path.relative_to(project_root).as_posix(),
        "manifest_path": manifest_path.relative_to(project_root).as_posix(),
    }
    if extra:
        entry.update(extra)
    return entry


def _read_learning_state(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    state = json.loads(path.read_text(encoding="utf-8"))
    return state if isinstance(state, dict) else {}


def _has_learning_plans(project_root: Path) -> bool:
    plan_dir = project_root / "02_learning_plan"
    required = (
        "long_term_plan.md",
        "short_term_plan.md",
        "session_0001_plan.md",
    )
    return all((plan_dir / name).exists() for name in required)


def _has_complete_session(sessions_dir: Path) -> bool:
    if not sessions_dir.exists():
        return False
    for session_dir in sessions_dir.iterdir():
        if not session_dir.is_dir():
            continue
        if all((session_dir / name).exists() for name in SESSION_REQUIRED_FILES):
            return True
    return False


def _reviewed_note_count(project_root: Path) -> int:
    notes_root = project_root / "04_atomic_notes"
    if not notes_root.exists():
        return 0
    reviewed = 0
    for folder in notes_root.iterdir():
        if not folder.is_dir() or folder.name == "drafts":
            continue
        for note_path in folder.glob("*.md"):
            if "reviewed_by_user: true" in note_path.read_text(encoding="utf-8"):
                reviewed += 1
    return reviewed


def _has_misconception_records(state: dict[str, object]) -> bool:
    misconceptions = state.get("misconceptions", {})
    if not isinstance(misconceptions, dict):
        return False
    return any(isinstance(value, dict) for value in misconceptions.values())


def _has_reviewed_misconception_notes(
    project_root: Path,
    state: dict[str, object],
) -> bool:
    misconceptions = state.get("misconceptions", {})
    if not isinstance(misconceptions, dict):
        return False
    expected_note_ids = {
        slugify_topic(str(misconception_id))
        for misconception_id, value in misconceptions.items()
        if isinstance(value, dict)
    }
    if not expected_note_ids:
        return False

    notes_dir = project_root / "04_atomic_notes" / "misconceptions"
    if not notes_dir.exists():
        return False
    reviewed_ids: set[str] = set()
    for note_path in notes_dir.glob("*.md"):
        text = note_path.read_text(encoding="utf-8")
        if _frontmatter_value(text, "type") != "misconception":
            continue
        if _frontmatter_value(text, "reviewed_by_user") != "true":
            continue
        reviewed_ids.add(note_path.stem)
    return expected_note_ids <= reviewed_ids


def _markdown_count(path: Path) -> int:
    if not path.exists():
        return 0
    return len(list(path.glob("*.md")))


def _has_review_schedule(project_root: Path, state: dict[str, object]) -> bool:
    schedule = state.get("review_schedule", [])
    return (
        isinstance(schedule, list)
        and (project_root / "02_learning_plan" / "review_schedule.md").exists()
    )


def _has_learning_reports(project_root: Path) -> bool:
    reports_dir = project_root / "07_exports" / "reports"
    required = (
        "weekly_report.md",
        "monthly_report.md",
        "project_summary.md",
    )
    return all((reports_dir / name).exists() for name in required)


def _has_benchmark_report(project_root: Path) -> bool:
    report_path = project_root / "08_evals" / "benchmark_report.md"
    if not report_path.exists():
        return False
    if "- Benchmark score: 100/100" not in report_path.read_text(encoding="utf-8"):
        return False
    return _latest_benchmark_input_mtime(project_root) <= report_path.stat().st_mtime_ns


def _has_benchmark_manifest(project_root: Path) -> bool:
    manifest_path = project_root / "08_evals" / "benchmark_manifest.json"
    if not manifest_path.exists():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    if not _valid_benchmark_manifest(project_root, manifest):
        return False
    return _latest_benchmark_input_mtime(project_root) <= manifest_path.stat().st_mtime_ns


def _has_tool_verification_records(project_root: Path) -> bool:
    manifest_path = project_root / "08_evals" / "tool_verification" / "manifest.json"
    if not manifest_path.exists():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        return False
    records = manifest.get("records")
    if not isinstance(records, list) or not records:
        return False
    return all(_valid_tool_verification_record(project_root, record) for record in records)


def _valid_tool_verification_record(project_root: Path, record: object) -> bool:
    if not isinstance(record, dict):
        return False
    for key in ("kind", "object_id", "status", "report_path"):
        if not isinstance(record.get(key), str) or not record[key]:
            return False
    artifact_path = (
        record.get("skeleton_path")
        or record.get("artifact_path")
        or record.get("output_path")
    )
    return (
        _manifest_artifact_exists(project_root, artifact_path)
        and _manifest_artifact_exists(project_root, record.get("report_path"))
    )


def _valid_benchmark_manifest(project_root: Path, manifest: object) -> bool:
    if not isinstance(manifest, dict):
        return False
    if manifest.get("schema_version") != 1:
        return False
    total_gates = manifest.get("total_gates")
    passed_gates = manifest.get("passed_gates")
    score = manifest.get("score")
    gates = manifest.get("gates")
    if not isinstance(total_gates, int) or total_gates <= 0:
        return False
    if not isinstance(passed_gates, int) or passed_gates < 0:
        return False
    if not isinstance(score, int) or score < 0:
        return False
    if passed_gates != total_gates or score != 100:
        return False
    if not isinstance(gates, list) or len(gates) != total_gates:
        return False
    expected_gates = {
        "Ingestion",
        "Note quality",
        "Exercise quality",
        "Tutoring quality",
    }
    gate_names = {str(gate.get("name", "")) for gate in gates if isinstance(gate, dict)}
    if gate_names != expected_gates:
        return False
    passed_count = 0
    for gate in gates:
        if not isinstance(gate, dict):
            return False
        if not isinstance(gate.get("passed"), bool):
            return False
        if not isinstance(gate.get("checked"), int):
            return False
        if not isinstance(gate.get("failed"), int):
            return False
        if not _manifest_artifact_exists(project_root, gate.get("report_path")):
            return False
        if not _manifest_artifact_exists(project_root, gate.get("manifest_path")):
            return False
        if gate["passed"]:
            passed_count += 1
    return passed_count == passed_gates


def _manifest_artifact_exists(project_root: Path, value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        return False
    return (project_root / path).exists()


def _latest_benchmark_input_mtime(project_root: Path) -> int:
    roots = (
        project_root / "01_references" / "curated",
        project_root / "03_sessions",
        project_root / "04_atomic_notes",
        project_root / "05_exercises" / "generated",
    )
    latest = 0
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.md"):
            if path.is_file():
                latest = max(latest, path.stat().st_mtime_ns)
    return latest


def _lifecycle_report(checks: dict[str, bool]) -> str:
    lines = [
        "# Lifecycle Eval",
        "",
        "## Checks",
        "",
    ]
    lines.extend(
        f"- {name}: {'pass' if passed else 'fail'}"
        for name, passed in checks.items()
    )
    return "\n".join(lines) + "\n"


def _append_report(path: Path, content: str) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else "# Tutoring Eval\n\n"
    write_text(path, existing.rstrip() + "\n\n" + content.rstrip() + "\n")
