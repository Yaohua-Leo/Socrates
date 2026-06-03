"""Checklist-based quality checks for generated artifacts."""

from __future__ import annotations

from dataclasses import dataclass
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


REQUIRED_FRONTMATTER = ("status:", "review_status:", "type:", "concept:")
REQUIRED_SECTIONS = ("## Hints", "## Solution Outline", "## Rubric")
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


def _check_exercise(path: Path) -> dict[str, object]:
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
    return {
        "file": path.name,
        "status": "fail" if issues else "pass",
        "issues": issues,
    }


def _atomic_note_paths(project_root: Path) -> list[Path]:
    notes_root = project_root / "04_atomic_notes"
    paths: list[Path] = []
    for folder in sorted(notes_root.iterdir()):
        if folder.is_dir():
            paths.extend(sorted(folder.glob("*.md")))
    return paths


def _check_note(path: Path, project_root: Path) -> dict[str, object]:
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
    if "## Review Questions" not in text:
        issues.append("missing review questions")
    return {
        "file": path.relative_to(project_root / "04_atomic_notes").as_posix(),
        "status": "fail" if issues else "pass",
        "issues": issues,
    }


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
