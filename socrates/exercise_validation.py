"""Advisory validation reports for generated exercise drafts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

from .context import load_project, write_json, write_text
from .exercise_schema import parse_exercise_markdown, validate_exercise_spec
from .kb import find_counterexamples


VALIDATION_DIR = Path("08_evals") / "exercise_validation"
VALIDATION_MANIFEST = Path("08_evals") / "exercise_validation_manifest.json"


@dataclass(frozen=True)
class ExerciseValidationResult:
    exercise_id: str
    status: str
    issues: tuple[str, ...]
    report_path: Path
    artifact_path: Path


@dataclass(frozen=True)
class ProjectExerciseValidationResult:
    checked: int
    passed: int
    failed: int
    report_path: Path
    manifest_path: Path


def validate_exercise(project_path: Path | str, exercise_id: str) -> ExerciseValidationResult:
    """Validate one generated exercise and write JSON plus Markdown evidence."""

    context = load_project(project_path)
    exercise_path = context.generated_exercises_dir / f"{exercise_id}.md"
    if not exercise_path.exists():
        raise FileNotFoundError(f"Generated exercise does not exist: {exercise_path}")
    spec = parse_exercise_markdown(exercise_path)
    schema_issues = validate_exercise_spec(spec)
    counterexample = _counterexample_summary(context.root, spec.concept)
    issues = list(schema_issues)
    status = "fail" if issues else "pass"
    artifact_path = context.root / VALIDATION_DIR / f"{exercise_id}.json"
    report_path = context.root / VALIDATION_DIR / f"{exercise_id}.md"
    payload = {
        "schema_version": 1,
        "exercise_id": exercise_id,
        "path": exercise_path.relative_to(context.root).as_posix(),
        "status": status,
        "issues": issues,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "schema": {
            "status": "fail" if schema_issues else "pass",
            "issues": schema_issues,
            "concept": spec.concept,
            "difficulty": spec.difficulty,
            "exercise_schema_version": spec.schema_version,
            "rubric_total_points": spec.rubric.total_points,
        },
        "counterexample_search": counterexample,
    }
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(artifact_path, payload)
    write_text(report_path, _validation_report(payload))
    return ExerciseValidationResult(
        exercise_id=exercise_id,
        status=status,
        issues=tuple(issues),
        report_path=report_path,
        artifact_path=artifact_path,
    )


def validate_project_exercises(project_path: Path | str) -> ProjectExerciseValidationResult:
    """Validate all generated exercises and write a project-level manifest."""

    context = load_project(project_path)
    exercise_ids = sorted(path.stem for path in context.generated_exercises_dir.glob("*.md"))
    results = [validate_exercise(context.root, exercise_id) for exercise_id in exercise_ids]
    manifest_path = context.root / VALIDATION_MANIFEST
    report_path = context.evals_dir / "exercise_validation_eval.md"
    records = [
        {
            "exercise_id": result.exercise_id,
            "status": result.status,
            "issues": list(result.issues),
            "artifact_path": result.artifact_path.relative_to(context.root).as_posix(),
            "report_path": result.report_path.relative_to(context.root).as_posix(),
        }
        for result in results
    ]
    manifest = {
        "schema_version": 1,
        "status": "fail" if any(result.status == "fail" for result in results) else "pass",
        "checked": len(results),
        "passed": sum(1 for result in results if result.status == "pass"),
        "failed": sum(1 for result in results if result.status == "fail"),
        "records": records,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(manifest_path, manifest)
    write_text(report_path, _project_validation_report(manifest))
    return ProjectExerciseValidationResult(
        checked=int(manifest["checked"]),
        passed=int(manifest["passed"]),
        failed=int(manifest["failed"]),
        report_path=report_path,
        manifest_path=manifest_path,
    )


def _counterexample_summary(project_root: Path, concept: str) -> dict[str, object]:
    index_path = project_root / "06_kb" / "chunks" / "reference_index.json"
    if not index_path.exists():
        return {
            "status": "not_run",
            "reason": "reference KB index missing",
            "match_count": 0,
            "matches": [],
        }
    try:
        matches = find_counterexamples(project_root, concept, limit=3)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return {
            "status": "not_run",
            "reason": f"reference KB unreadable: {exc}",
            "match_count": 0,
            "matches": [],
        }
    return {
        "status": "searched",
        "match_count": len(matches),
        "matches": [_counterexample_match(match) for match in matches],
    }


def _counterexample_match(match: dict[str, object]) -> dict[str, object]:
    source = match.get("source", {})
    if not isinstance(source, dict):
        source = {}
    return {
        "id": str(match.get("id", "")),
        "title": str(match.get("title", "")),
        "statement": str(match.get("statement", "")),
        "source": {
            "path": str(source.get("path", "")),
            "line": source.get("line"),
            "page": source.get("page"),
        },
    }


def _validation_report(payload: dict[str, object]) -> str:
    issues = payload.get("issues", [])
    schema = payload.get("schema", {})
    counterexample = payload.get("counterexample_search", {})
    lines = [
        f"# Exercise Validation: {payload['exercise_id']}",
        "",
        f"- Status: {payload['status']}",
        f"- Exercise: {payload['path']}",
        f"- Created at: {payload['created_at']}",
        "",
        "## Schema",
        "",
        f"- Status: {_mapping_value(schema, 'status')}",
        f"- Concept: {_mapping_value(schema, 'concept')}",
        f"- Difficulty: {_mapping_value(schema, 'difficulty')}",
        f"- Rubric total points: {_mapping_value(schema, 'rubric_total_points')}",
        "",
        "## Issues",
        "",
    ]
    lines.extend(_issue_lines(issues))
    lines.extend(
        [
            "",
            "## Counterexample Search",
            "",
            f"- Status: {_mapping_value(counterexample, 'status')}",
            f"- Matches: {_mapping_value(counterexample, 'match_count')}",
            "",
            "This validation is advisory evidence. Passing validation does not prove the exercise.",
        ]
    )
    return "\n".join(lines) + "\n"


def _project_validation_report(manifest: dict[str, object]) -> str:
    lines = [
        "# Exercise Validation",
        "",
        f"- Status: {manifest['status']}",
        f"- Checked: {manifest['checked']}",
        f"- Passed: {manifest['passed']}",
        f"- Failed: {manifest['failed']}",
        "",
        "## Records",
        "",
    ]
    records = manifest.get("records", [])
    if not isinstance(records, list) or not records:
        lines.append("- none")
    else:
        for record in records:
            if not isinstance(record, dict):
                continue
            issues = record.get("issues", [])
            issue_text = ", ".join(str(issue) for issue in issues) if issues else "none"
            lines.append(
                f"- {record.get('exercise_id', 'unknown')}: "
                f"{record.get('status', 'unknown')} | issues: {issue_text}"
            )
    lines.extend(
        [
            "",
            "Validation reports are review aids and do not approve exercises automatically.",
        ]
    )
    return "\n".join(lines) + "\n"


def _issue_lines(value: object) -> list[str]:
    if not isinstance(value, list) or not value:
        return ["- none"]
    return [f"- {item}" for item in value]


def _mapping_value(value: object, key: str) -> object:
    if isinstance(value, dict):
        return value.get(key, "")
    return ""
