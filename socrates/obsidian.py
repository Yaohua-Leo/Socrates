"""Shared helpers for reading Obsidian export artifacts."""

from __future__ import annotations

import json
from pathlib import Path


def obsidian_export_count(project_root: Path) -> int:
    """Count exported notes, falling back to markdown files when metadata is unusable."""

    exported_notes = _manifest_exported_notes(project_root)
    if exported_notes is not None:
        return len(exported_notes)
    return len(obsidian_exported_note_ids_from_files(project_root))


def obsidian_backlink_count(project_root: Path) -> int:
    """Count manifest-recorded backlinks when the export manifest can be read."""

    exported_notes = _manifest_exported_notes(project_root)
    if exported_notes is None:
        return 0
    backlink_count = 0
    for note in exported_notes:
        backlinks = note.get("backlinks", [])
        if isinstance(backlinks, list):
            backlink_count += len(backlinks)
    return backlink_count


def obsidian_exported_note_ids(project_root: Path) -> set[str]:
    """Return exported note ids from metadata, or from exported markdown files."""

    exported_notes = _manifest_exported_notes(project_root)
    if exported_notes is not None:
        return {str(item["note_id"]) for item in exported_notes}
    return obsidian_exported_note_ids_from_files(project_root)


def read_obsidian_export_manifest(project_root: Path) -> object | None:
    """Read export_manifest.json, treating invalid JSON as missing metadata."""

    manifest_path = project_root / "07_exports" / "obsidian" / "export_manifest.json"
    if not manifest_path.exists():
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _manifest_exported_notes(project_root: Path) -> list[dict[str, object]] | None:
    manifest = read_obsidian_export_manifest(project_root)
    if not isinstance(manifest, dict):
        return None
    exported_notes = manifest.get("exported_notes", [])
    if not isinstance(exported_notes, list):
        return None

    obsidian_dir = project_root / "07_exports" / "obsidian"
    obsidian_root = obsidian_dir.resolve()
    valid_notes: list[dict[str, object]] = []
    for item in exported_notes:
        if not isinstance(item, dict):
            continue
        note_id = str(item.get("note_id") or "").strip()
        path_value = item.get("path")
        if not note_id or not isinstance(path_value, str):
            continue
        export_path = (obsidian_dir / path_value).resolve()
        try:
            export_path.relative_to(obsidian_root)
        except ValueError:
            continue
        if (
            export_path.name == "_socrates_index.md"
            or export_path.suffix != ".md"
            or export_path.stem != note_id
            or not export_path.is_file()
            or not _is_socrates_obsidian_export(export_path)
        ):
            continue
        valid_notes.append(item)
    return valid_notes


def obsidian_exported_note_ids_from_files(project_root: Path) -> set[str]:
    obsidian_dir = project_root / "07_exports" / "obsidian"
    if not obsidian_dir.exists():
        return set()
    return {
        path.stem
        for path in obsidian_dir.glob("*.md")
        if path.name != "_socrates_index.md" and _is_socrates_obsidian_export(path)
    }


def _is_socrates_obsidian_export(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return _frontmatter_value(text, "created_by") == "socrates"


def _frontmatter_value(text: str, key: str) -> str | None:
    prefix = f"{key}:"
    for line in _frontmatter_lines(text):
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip().strip('"').strip("'")
    return None


def _frontmatter_lines(text: str) -> list[str]:
    if not text.startswith("---\n"):
        return []
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        return []
    return parts[1].splitlines()
