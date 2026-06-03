"""Checklist-based quality checks for generated artifacts."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from .context import load_project, write_text


@dataclass(frozen=True)
class ExerciseQualityResult:
    """Summary of a generated-exercise quality check."""

    checked: int
    passed: int
    failed: int
    report_path: Path


@dataclass(frozen=True)
class NoteQualityResult:
    """Summary of an atomic-note quality check."""

    checked: int
    passed: int
    failed: int
    report_path: Path


@dataclass(frozen=True)
class TutoringQualityResult:
    """Summary of a tutoring-session quality check."""

    session_id: str
    status: str
    report_path: Path


@dataclass(frozen=True)
class IngestionQualityResult:
    """Summary of curated-reference ingestion quality checks."""

    checked: int
    passed: int
    failed: int
    object_count: int
    report_path: Path


@dataclass(frozen=True)
class BenchmarkResult:
    """Summary of a project-level quality benchmark run."""

    total_gates: int
    passed_gates: int
    report_path: Path


@dataclass(frozen=True)
class LifecycleAuditResult:
    """Summary of a persisted lifecycle completion audit."""

    total_checks: int
    passed_checks: int
    report_path: Path


REQUIRED_FRONTMATTER = ("status:", "review_status:", "type:", "concept:")
REQUIRED_SECTIONS = (
    "## Target Training Point",
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
    "concept:",
    "source_id:",
    "tags:",
    "related:",
)
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
INGESTION_OBJECT_TYPES = {
    "definition",
    "theorem",
    "proposition",
    "lemma",
    "corollary",
    "example",
    "counterexample",
    "proof",
    "exercise",
    "remark",
    "notation",
}


def check_generated_exercise_quality(project_path: Path | str) -> ExerciseQualityResult:
    """Check generated exercise drafts and write a quality report."""

    context = load_project(project_path)
    exercise_paths = sorted(context.generated_exercises_dir.glob("*.md"))
    rows = [_check_exercise(path) for path in exercise_paths]
    passed = sum(1 for row in rows if row["status"] == "pass")
    failed = len(rows) - passed
    report_path = context.evals_dir / "exercise_quality_eval.md"
    write_text(report_path, _exercise_quality_report(rows, passed, failed))
    return ExerciseQualityResult(
        checked=len(rows),
        passed=passed,
        failed=failed,
        report_path=report_path,
    )


def check_atomic_note_quality(project_path: Path | str) -> NoteQualityResult:
    """Check atomic notes and write a note-quality report."""

    context = load_project(project_path)
    note_paths = _atomic_note_paths(context.root)
    rows = [_check_note(path, context.root) for path in note_paths]
    passed = sum(1 for row in rows if row["status"] == "pass")
    failed = len(rows) - passed
    report_path = context.evals_dir / "note_quality_eval.md"
    write_text(report_path, _note_quality_report(rows, passed, failed))
    return NoteQualityResult(
        checked=len(rows),
        passed=passed,
        failed=failed,
        report_path=report_path,
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
    if "Tutor:" not in transcript:
        issues.append("missing tutor question")
    if "Hint 1:" not in transcript:
        issues.append("missing first hint")
    premature_solution = _has_premature_solution(transcript)
    if premature_solution:
        issues.append("premature full solution")

    status = "fail" if issues else "pass"
    report_path = context.evals_dir / "tutoring_eval.md"
    _append_report(report_path, _tutoring_quality_report(session_id, status, missing, premature_solution, issues))
    return TutoringQualityResult(session_id=session_id, status=status, report_path=report_path)


def check_reference_ingestion_quality(project_path: Path | str) -> IngestionQualityResult:
    """Check curated reference files for extractable KB objects."""

    context = load_project(project_path)
    curated_paths = sorted((context.references_dir / "curated").glob("*.md"))
    rows = [_check_curated_reference(path) for path in curated_paths]
    passed = sum(1 for row in rows if row["status"] == "pass")
    failed = len(rows) - passed
    object_count = sum(int(row["object_count"]) for row in rows)
    report_path = context.evals_dir / "ingestion_eval.md"
    write_text(report_path, _ingestion_quality_report(rows, passed, failed, object_count))
    return IngestionQualityResult(
        checked=len(rows),
        passed=passed,
        failed=failed,
        object_count=object_count,
        report_path=report_path,
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
    report_path = context.evals_dir / "benchmark_report.md"
    write_text(report_path, _benchmark_report(gates))
    return BenchmarkResult(
        total_gates=len(gates),
        passed_gates=sum(1 for passed in gates.values() if passed),
        report_path=report_path,
    )


def audit_project_lifecycle(project_path: Path | str) -> LifecycleAuditResult:
    """Check whether the project has persisted artifacts for the full learning loop."""

    context = load_project(project_path)
    state = _read_learning_state(context.learning_state)
    checks = {
        "Project metadata": context.project_file.exists() and context.learning_state.exists(),
        "Reference KB": _reference_object_count(context.root) > 0,
        "Learning plans": _has_learning_plans(context.root),
        "Tutoring session artifacts": _has_complete_session(context.sessions_dir),
        "Reviewed atomic notes": _reviewed_note_count(context.root) > 0,
        "Obsidian export": _markdown_count(context.root / "07_exports" / "obsidian") > 0,
        "Generated exercises": _markdown_count(context.generated_exercises_dir) >= 5,
        "Exercise attempts": _markdown_count(context.root / "05_exercises" / "attempted") > 0,
        "Graded exercises": _markdown_count(context.root / "05_exercises" / "graded") > 0,
        "Learning state": bool(state.get("concept_mastery")),
        "Review schedule": _has_review_schedule(context.root, state),
        "Learning reports": _has_learning_reports(context.root),
    }
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
    if "## Statement" not in text and "## Review Prompt" not in text:
        issues.append("missing statement or review prompt")
    for section in REQUIRED_SECTIONS:
        if section not in text:
            issues.append(f"missing section {section.removeprefix('## ')}")
    return issues


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


def atomic_note_quality_issues(path: Path, project_root: Path) -> list[str]:
    """Return checklist issues for one atomic note file."""

    text = path.read_text(encoding="utf-8")
    issues: list[str] = []
    if not text.startswith("---\n"):
        issues.append("missing YAML frontmatter")
    for field in NOTE_REQUIRED_FRONTMATTER:
        if field not in text:
            issues.append(f"missing frontmatter field {field.rstrip(':')}")
    if "# " not in text:
        issues.append("missing title heading")
    if "source_id: null" in text or 'source_id: ""' in text:
        issues.append("missing source id")
    for section in NOTE_REQUIRED_SECTIONS:
        if section not in text:
            issues.append(f"missing section {section.removeprefix('## ')}")
    return issues


def _check_curated_reference(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    object_count = _extractable_object_count(text)
    issues: list[str] = []
    if object_count == 0:
        issues.append("no extractable mathematical object headings")
    if "Depends:" not in text:
        issues.append("no dependency metadata")
    return {
        "file": path.name,
        "status": "fail" if issues else "pass",
        "object_count": object_count,
        "issues": issues,
    }


def _extractable_object_count(text: str) -> int:
    count = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("### "):
            continue
        label, separator, _ = stripped.removeprefix("### ").partition(":")
        if separator and label.strip().casefold() in INGESTION_OBJECT_TYPES:
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
    return "\n".join(lines) + "\n"


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
    premature_solution: bool,
    issues: list[str],
) -> str:
    lines = [
        f"## Session Quality Check: {session_id}",
        "",
        f"- Status: {status}",
        f"- Missing artifacts: {', '.join(missing) if missing else 'none'}",
        f"- Premature solution: {'yes' if premature_solution else 'no'}",
        "",
        "### Issues",
    ]
    lines.extend(f"- {issue}" for issue in issues)
    if not issues:
        lines.append("- none recorded")
    return "\n".join(lines) + "\n"


def _benchmark_report(gates: dict[str, bool]) -> str:
    lines = [
        "# Benchmark Report",
        "",
        "## Quality Gates",
        "",
    ]
    lines.extend(
        f"- {name}: {'pass' if passed else 'fail'}"
        for name, passed in gates.items()
    )
    return "\n".join(lines) + "\n"


def _read_learning_state(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    state = json.loads(path.read_text(encoding="utf-8"))
    return state if isinstance(state, dict) else {}


def _reference_object_count(project_root: Path) -> int:
    index_path = project_root / "06_kb" / "chunks" / "reference_index.json"
    if not index_path.exists():
        return 0
    index = json.loads(index_path.read_text(encoding="utf-8"))
    objects = index.get("objects", []) if isinstance(index, dict) else []
    return len(objects) if isinstance(objects, list) else 0


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
