"""LLM suggestion artifact manifest helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

from socrates.context import write_json


MANIFEST_PATH = Path("08_evals") / "llm_suggestions_manifest.json"


@dataclass(frozen=True)
class LlmSuggestionSummary:
    suggestion_id: str
    suggestion_type: str
    status: str
    artifact_path: str
    provider: str
    model: str


def record_llm_suggestion(
    project_path: Path | str,
    *,
    artifact_path: Path,
    suggestion_type: str,
    provider: str,
    model: str,
    source_paths: list[str],
    prompt_hash: str,
) -> None:
    project = Path(project_path).resolve()
    manifest_path = project / MANIFEST_PATH
    manifest = _read_manifest(manifest_path)
    relative_artifact = artifact_path.resolve().relative_to(project).as_posix()
    record = {
        "suggestion_id": Path(relative_artifact).stem,
        "suggestion_type": suggestion_type,
        "status": "draft",
        "artifact_path": relative_artifact,
        "provider": provider,
        "model": model,
        "source_paths": list(source_paths),
        "prompt_hash": prompt_hash,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    manifest["records"].append(record)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(manifest_path, manifest)


def list_llm_suggestions(project_path: Path | str) -> list[LlmSuggestionSummary]:
    manifest = _read_manifest(Path(project_path).resolve() / MANIFEST_PATH)
    return [
        LlmSuggestionSummary(
            suggestion_id=str(item.get("suggestion_id", "")),
            suggestion_type=str(item.get("suggestion_type", "")),
            status=str(item.get("status", "draft")),
            artifact_path=str(item.get("artifact_path", "")),
            provider=str(item.get("provider", "")),
            model=str(item.get("model", "")),
        )
        for item in manifest.get("records", [])
        if isinstance(item, dict)
    ]


def validate_llm_suggestion_manifest(project_path: Path | str) -> bool:
    _read_manifest(Path(project_path).resolve() / MANIFEST_PATH)
    return True


def _read_manifest(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"schema_version": 1, "records": []}
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or not isinstance(manifest.get("records"), list):
        raise ValueError("invalid llm_suggestions_manifest.json")
    return manifest
