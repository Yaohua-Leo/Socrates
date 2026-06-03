"""Multi-project discovery and index helpers."""

from __future__ import annotations

import json
from pathlib import Path
import re

from .context import write_json
from .project import slugify_topic


INDEX_FILENAME = "socrates_projects.json"
CROSS_PROJECT_GRAPH_FILENAME = "cross_project_references.json"
OBSIDIAN_LINK_PATTERN = re.compile(
    r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]"
)


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


def find_project_references(
    root_path: Path | str,
    *,
    query: str = "",
) -> list[dict[str, str]]:
    """Return reviewed atomic notes as cross-project knowledge references."""

    root = Path(root_path).expanduser().resolve()
    query_text = query.casefold().strip()
    references: list[dict[str, str]] = []
    for reference, text in _reviewed_references_with_text(root):
        if query_text and query_text not in _reference_haystack(reference, text):
            continue
        references.append(reference)
    return sorted(references, key=lambda item: item["ref"])


def build_cross_project_reference_graph(root_path: Path | str) -> Path:
    """Build a graph of reviewed-note links across different projects."""

    root = Path(root_path).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    references_with_text = _reviewed_references_with_text(root)
    references = [reference for reference, _ in references_with_text]
    index = _reference_lookup(references)
    edges: list[dict[str, str]] = []
    seen_edges: set[tuple[str, str, str]] = set()

    for source, text in references_with_text:
        for label in _obsidian_link_labels(text):
            for target in index.get(slugify_topic(label), []):
                if target["project_id"] == source["project_id"]:
                    continue
                edge_key = (source["ref"], target["ref"], label)
                if edge_key in seen_edges:
                    continue
                seen_edges.add(edge_key)
                edges.append(
                    {
                        "source": source["ref"],
                        "target": target["ref"],
                        "label": label,
                    }
                )

    write_json(
        root / CROSS_PROJECT_GRAPH_FILENAME,
        {
            "version": 1,
            "nodes": references,
            "edges": sorted(
                edges,
                key=lambda edge: (edge["source"], edge["target"], edge["label"]),
            ),
        },
    )
    return root / CROSS_PROJECT_GRAPH_FILENAME


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


def _reviewed_note_paths(project_root: Path) -> list[Path]:
    notes_root = project_root / "04_atomic_notes"
    if not notes_root.exists():
        return []
    paths: list[Path] = []
    for folder in sorted(notes_root.iterdir(), key=lambda path: path.name.casefold()):
        if not folder.is_dir() or folder.name == "drafts":
            continue
        for note_path in sorted(folder.glob("*.md"), key=lambda path: path.name.casefold()):
            text = note_path.read_text(encoding="utf-8")
            if _frontmatter_values(text).get("reviewed_by_user") == "true":
                paths.append(note_path)
    return paths


def _reviewed_references_with_text(root: Path) -> list[tuple[dict[str, str], str]]:
    references: list[tuple[dict[str, str], str]] = []
    for project in list_projects(root):
        project_root = root / project["path"]
        project_id = project["id"]
        for note_path in _reviewed_note_paths(project_root):
            text = note_path.read_text(encoding="utf-8")
            metadata = _frontmatter_values(text)
            note_id = note_path.stem
            concept = metadata.get("concept") or _first_heading(text) or note_id
            note_type = metadata.get("type") or note_path.parent.name.rstrip("s")
            references.append(
                (
                    {
                        "ref": f"{project_id}.{note_id}",
                        "project_id": project_id,
                        "note_id": note_id,
                        "concept": concept,
                        "type": note_type,
                        "path": note_path.relative_to(root).as_posix(),
                    },
                    text,
                )
            )
    return sorted(references, key=lambda item: item[0]["ref"])


def _reference_lookup(references: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    index: dict[str, list[dict[str, str]]] = {}
    for reference in references:
        keys = {
            slugify_topic(reference["concept"]),
            slugify_topic(reference["note_id"]),
            reference["note_id"],
        }
        for key in keys:
            index.setdefault(key, []).append(reference)
    return index


def _obsidian_link_labels(text: str) -> list[str]:
    labels: list[str] = []
    for match in OBSIDIAN_LINK_PATTERN.finditer(text):
        label = match.group(1).strip()
        if label:
            labels.append(label)
    return labels


def _frontmatter_values(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    parts = text.split("---\n", 2)
    if len(parts) != 3:
        return {}
    values: dict[str, str] = {}
    for line in parts[1].splitlines():
        if line.startswith(" ") or not line.strip():
            continue
        key, separator, raw_value = line.partition(":")
        if separator:
            values[key] = _yaml_like_string(raw_value.strip())
    return values


def _first_heading(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line.removeprefix("# ").strip()
    return ""


def _reference_haystack(reference: dict[str, str], text: str) -> str:
    return " ".join(
        [
            reference["ref"],
            reference["concept"],
            reference["type"],
            reference["path"],
            text,
        ]
    ).casefold()


def _yaml_like_string(value: str) -> str:
    if value == "null":
        return ""
    if value.startswith('"') and value.endswith('"'):
        return str(json.loads(value))
    return value
