"""Exercise bank manifest for approved, validated exercises."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

from .context import load_project, write_json
from .exercise_schema import parse_exercise_markdown
from .exercises import list_exercises


BANK_MANIFEST = Path("05_exercises") / "exercise_bank_manifest.json"
VALIDATION_MANIFEST = Path("08_evals") / "exercise_validation_manifest.json"


@dataclass(frozen=True)
class ExerciseBankBuildResult:
    total_exercises: int
    manifest_path: Path


@dataclass(frozen=True)
class ExerciseBankSummary:
    exercise_id: str
    concept: str
    difficulty: int
    path: str
    validation_status: str


def build_exercise_bank(project_path: Path | str) -> ExerciseBankBuildResult:
    """Build the bank manifest from approved exercises with passing validation."""

    context = load_project(project_path)
    validation_by_id = _validation_by_id(context.root)
    records = []
    for summary in list_exercises(context.root, status="all"):
        validation = validation_by_id.get(summary.exercise_id, {})
        if validation.get("status") != "pass":
            continue
        spec = parse_exercise_markdown(context.root / summary.path)
        if spec.status != "approved" or spec.review_status != "approved":
            continue
        records.append(
            {
                "exercise_id": summary.exercise_id,
                "concept": spec.concept,
                "difficulty": spec.difficulty,
                "type": spec.exercise_type,
                "path": summary.path,
                "validation_status": "pass",
                "validation_artifact": validation["artifact_path"],
            }
        )
    manifest_path = context.root / BANK_MANIFEST
    write_json(
        manifest_path,
        {
            "schema_version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "total_exercises": len(records),
            "records": records,
        },
    )
    return ExerciseBankBuildResult(total_exercises=len(records), manifest_path=manifest_path)


def read_exercise_bank(project_path: Path | str) -> list[ExerciseBankSummary]:
    """Read the current exercise bank manifest."""

    context = load_project(project_path)
    manifest_path = context.root / BANK_MANIFEST
    if not manifest_path.exists():
        return []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("invalid exercise_bank_manifest.json") from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise ValueError("invalid exercise_bank_manifest.json")
    records = manifest.get("records")
    if not isinstance(records, list):
        raise ValueError("invalid exercise_bank_manifest.json")
    summaries: list[ExerciseBankSummary] = []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("invalid exercise_bank_manifest.json")
        try:
            summaries.append(
                ExerciseBankSummary(
                    exercise_id=str(record["exercise_id"]),
                    concept=str(record["concept"]),
                    difficulty=int(record["difficulty"]),
                    path=str(record["path"]),
                    validation_status=str(record["validation_status"]),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid exercise_bank_manifest.json") from exc
    return summaries


def _validation_by_id(project_root: Path) -> dict[str, dict[str, object]]:
    manifest_path = project_root / VALIDATION_MANIFEST
    if not manifest_path.exists():
        return {}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("invalid exercise_validation_manifest.json") from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise ValueError("invalid exercise_validation_manifest.json")
    records = manifest.get("records")
    if not isinstance(records, list):
        raise ValueError("invalid exercise_validation_manifest.json")
    validation: dict[str, dict[str, object]] = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("invalid exercise_validation_manifest.json")
        exercise_id = str(record.get("exercise_id", "")).strip()
        if exercise_id:
            validation[exercise_id] = record
    return validation
