"""Shared helpers for reading Obsidian export artifacts."""

from __future__ import annotations

import json
from pathlib import Path


def obsidian_export_count(project_root: Path) -> int:
    """Count exported notes, falling back to markdown files when metadata is unusable."""

    manifest = read_obsidian_export_manifest(project_root)
    if isinstance(manifest, dict):
        exported_notes = manifest.get("exported_notes", [])
        if isinstance(exported_notes, list):
            return len(exported_notes)
    return len(obsidian_exported_note_ids_from_files(project_root))


def obsidian_backlink_count(project_root: Path) -> int:
    """Count manifest-recorded backlinks when the export manifest can be read."""

    manifest = read_obsidian_export_manifest(project_root)
    exported_notes = manifest.get("exported_notes", []) if isinstance(manifest, dict) else []
    if not isinstance(exported_notes, list):
        return 0
    backlink_count = 0
    for note in exported_notes:
        if not isinstance(note, dict):
            continue
        backlinks = note.get("backlinks", [])
        if isinstance(backlinks, list):
            backlink_count += len(backlinks)
    return backlink_count


def obsidian_exported_note_ids(project_root: Path) -> set[str]:
    """Return exported note ids from metadata, or from exported markdown files."""

    manifest = read_obsidian_export_manifest(project_root)
    if isinstance(manifest, dict):
        exported_notes = manifest.get("exported_notes", [])
        if isinstance(exported_notes, list):
            return {
                str(item.get("note_id"))
                for item in exported_notes
                if isinstance(item, dict) and item.get("note_id")
            }
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


def obsidian_exported_note_ids_from_files(project_root: Path) -> set[str]:
    obsidian_dir = project_root / "07_exports" / "obsidian"
    if not obsidian_dir.exists():
        return set()
    return {
        path.stem
        for path in obsidian_dir.glob("*.md")
        if path.name != "_socrates_index.md"
    }
