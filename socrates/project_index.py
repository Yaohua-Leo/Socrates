"""Multi-project discovery and index helpers."""

from __future__ import annotations

import json
from pathlib import Path

from .context import write_json


INDEX_FILENAME = "socrates_projects.json"


def scan_project_root(root_path: Path | str) -> Path:
    """Discover Socrates projects under a collection root and write an index."""

    root = Path(root_path).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    write_json(root / INDEX_FILENAME, _index_payload(root, discover_projects(root)))
    return root / INDEX_FILENAME


def list_projects(root_path: Path | str) -> list[dict[str, str]]:
    """Return indexed projects, scanning the root if no index exists yet."""

    root = Path(root_path).expanduser().resolve()
    index_path = root / INDEX_FILENAME
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding="utf-8"))
        projects = index.get("projects", []) if isinstance(index, dict) else []
        return [project for project in projects if _is_project_record(project)]
    return discover_projects(root)


def discover_projects(root_path: Path | str) -> list[dict[str, str]]:
    """Find immediate child directories that look like Socrates projects."""

    root = Path(root_path).expanduser().resolve()
    if not root.exists():
        return []

    projects: list[dict[str, str]] = []
    for child in sorted(root.iterdir(), key=lambda path: path.name.casefold()):
        project_file = child / "project.yaml"
        if not child.is_dir() or not project_file.exists():
            continue
        metadata = _read_project_metadata(project_file)
        projects.append(
            {
                "id": metadata.get("id") or child.name,
                "title": metadata.get("title") or child.name,
                "status": metadata.get("status") or "unknown",
                "phase": metadata.get("phase") or "unknown",
                "path": child.relative_to(root).as_posix(),
            }
        )
    return sorted(projects, key=lambda project: project["id"])


def _index_payload(root: Path, projects: list[dict[str, str]]) -> dict[str, object]:
    return {
        "version": 1,
        "root": str(root),
        "projects": projects,
    }


def _is_project_record(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    return all(isinstance(value.get(key), str) for key in ("id", "title", "status", "path"))


def _read_project_metadata(project_file: Path) -> dict[str, str]:
    metadata: dict[str, str] = {}
    section = ""
    for line in project_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if not line.startswith(" ") and stripped.endswith(":"):
            section = stripped.removesuffix(":")
            continue
        key, separator, raw_value = stripped.partition(":")
        if not separator:
            continue
        value = _yaml_like_string(raw_value.strip())
        if section == "project" and key in {"id", "title", "status"}:
            metadata[key] = value
        elif section == "learning" and key == "current_phase":
            metadata["phase"] = value
    return metadata


def _yaml_like_string(value: str) -> str:
    if value == "null":
        return ""
    if value.startswith('"') and value.endswith('"'):
        return str(json.loads(value))
    return value
