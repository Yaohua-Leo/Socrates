"""Atomic note review and Obsidian export workflows."""

from __future__ import annotations

import json
from pathlib import Path
import shutil

from .context import append_project_log, load_project, write_text
from .quality import atomic_note_quality_issues, check_atomic_note_quality


NOTE_TYPE_DIRS = {
    "definition": "definitions",
    "theorem": "theorems",
    "example": "examples",
    "counterexample": "counterexamples",
    "technique": "techniques",
    "exercise": "exercises",
}


def review_atomic_note(project_path: Path | str, note_id: str) -> Path:
    """Promote one draft atomic note into its reviewed type folder."""

    context = load_project(project_path)
    draft_path = context.atomic_note_drafts_dir / f"{note_id}.md"
    if not draft_path.exists():
        raise FileNotFoundError(f"Draft note does not exist: {draft_path}")

    _require_note_quality(context.root, draft_path, f"Draft note {note_id}")

    text = draft_path.read_text(encoding="utf-8")
    note_type = _frontmatter_value(text, "type") or "definition"
    target_dir = NOTE_TYPE_DIRS.get(note_type, f"{note_type}s")
    reviewed_path = context.root / "04_atomic_notes" / target_dir / draft_path.name
    reviewed_text = _set_frontmatter_values(
        text,
        {
            "status": '"reviewed"',
            "review_status": '"approved"',
            "reviewed_by_user": "true",
        },
    )
    write_text(reviewed_path, reviewed_text)
    append_project_log(context, f"Reviewed atomic note {note_id}.")
    return reviewed_path


def export_reviewed_notes_to_obsidian(project_path: Path | str) -> list[Path]:
    """Copy reviewed notes into the Obsidian export directory."""

    context = load_project(project_path)
    exported: list[Path] = []
    manifest_notes: list[dict[str, object]] = []
    for folder in sorted((context.root / "04_atomic_notes").iterdir()):
        if not folder.is_dir() or folder.name == "drafts":
            continue
        for note_path in sorted(folder.glob("*.md")):
            text = note_path.read_text(encoding="utf-8")
            if _frontmatter_value(text, "reviewed_by_user") != "true":
                continue
            _require_note_quality(context.root, note_path, f"Reviewed note {note_path.stem}")
            destination = context.root / "07_exports" / "obsidian" / note_path.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(note_path, destination)
            exported.append(destination)
            manifest_notes.append(
                {
                    "note_id": note_path.stem,
                    "concept": _frontmatter_value(text, "concept") or note_path.stem,
                    "type": _frontmatter_value(text, "type") or folder.name.rstrip("s"),
                    "path": destination.relative_to(destination.parent).as_posix(),
                    "review_status": _frontmatter_value(text, "review_status") or "",
                    "source_id": _frontmatter_value(text, "source_id") or "",
                    "source_title": _frontmatter_value(text, "source_title") or "",
                    "source_location": _frontmatter_value(text, "source_location") or "",
                    "tags": _frontmatter_list(text, "tags"),
                    "related": _frontmatter_list(text, "related"),
                }
            )
    if exported:
        obsidian_dir = context.root / "07_exports" / "obsidian"
        _write_export_manifest(obsidian_dir, manifest_notes)
        _write_export_index(obsidian_dir, manifest_notes)
        append_project_log(context, f"Exported {len(exported)} reviewed note(s) to Obsidian.")
    return exported


def _write_export_manifest(obsidian_dir: Path, exported_notes: list[dict[str, object]]) -> None:
    manifest = {
        "version": 2,
        "exported_notes": sorted(exported_notes, key=lambda item: item["note_id"]),
    }
    write_text(
        obsidian_dir / "export_manifest.json",
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    )


def _write_export_index(obsidian_dir: Path, exported_notes: list[dict[str, object]]) -> None:
    notes = sorted(exported_notes, key=lambda item: (str(item["type"]), str(item["concept"])))
    lines = ["# Socrates Obsidian Export", ""]
    current_type = ""
    for note in notes:
        note_type = str(note["type"])
        if note_type != current_type:
            current_type = note_type
            lines.extend([f"## {note_type.replace('_', ' ').title()}", ""])
        note_id = str(note["note_id"])
        concept = str(note["concept"])
        lines.append(f"- [[{note_id}|{concept}]]")
        source_line = _index_source_line(note)
        if source_line:
            lines.append(f"  - Source: {source_line}")
        tags = [f"#{tag}" for tag in note.get("tags", []) if str(tag).strip()]
        if tags:
            lines.append(f"  - Tags: {' '.join(tags)}")
        related = [str(item) for item in note.get("related", []) if str(item).strip()]
        if related:
            lines.append(f"  - Related: {', '.join(related)}")
    write_text(obsidian_dir / "_socrates_index.md", "\n".join(lines).rstrip() + "\n")


def _index_source_line(note: dict[str, object]) -> str:
    source_title = str(note.get("source_title") or "").strip()
    source_location = str(note.get("source_location") or "").strip()
    source_id = str(note.get("source_id") or "").strip()
    parts = [value for value in (source_title, source_location) if value]
    if parts:
        return ", ".join(parts)
    return source_id


def _require_note_quality(project_root: Path, note_path: Path, label: str) -> None:
    issues = atomic_note_quality_issues(note_path, project_root)
    if not issues:
        return
    result = check_atomic_note_quality(project_root)
    raise ValueError(
        f"{label} failed quality gate: "
        f"{'; '.join(issues)}. See {result.report_path}"
    )


def _frontmatter_value(text: str, key: str) -> str | None:
    frontmatter = _frontmatter_lines(text)
    prefix = f"{key}:"
    for line in frontmatter:
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


def _frontmatter_string(value: str) -> str:
    if (
        (value.startswith('"') and value.endswith('"'))
        or (value.startswith("'") and value.endswith("'"))
    ):
        return value[1:-1]
    return value


def _set_frontmatter_values(text: str, values: dict[str, str]) -> str:
    if not text.startswith("---\n"):
        added = ["---", *(f"{key}: {value}" for key, value in values.items()), "---", ""]
        return "\n".join(added) + text

    parts = text.split("---\n", 2)
    if len(parts) != 3:
        return text
    _, frontmatter_text, body = parts
    lines = frontmatter_text.rstrip("\n").splitlines()
    seen: set[str] = set()
    updated: list[str] = []
    for line in lines:
        key, separator, _ = line.partition(":")
        if separator and key in values:
            updated.append(f"{key}: {values[key]}")
            seen.add(key)
        else:
            updated.append(line)
    for key, value in values.items():
        if key not in seen:
            updated.append(f"{key}: {value}")
    return "---\n" + "\n".join(updated) + "\n---\n" + body


def _frontmatter_lines(text: str) -> list[str]:
    if not text.startswith("---\n"):
        return []
    parts = text.split("---\n", 2)
    if len(parts) != 3:
        return []
    return parts[1].splitlines()
