"""Atomic note review and Obsidian export workflows."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from .context import append_project_log, load_project, write_text
from .obsidian import obsidian_exported_note_ids, read_obsidian_export_manifest
from .project import slugify_topic
from .quality import atomic_note_quality_issues, check_atomic_note_quality


NOTE_TYPE_DIRS = {
    "definition": "definitions",
    "theorem": "theorems",
    "example": "examples",
    "counterexample": "counterexamples",
    "technique": "techniques",
    "exercise": "exercises",
}


@dataclass(frozen=True)
class AtomicNoteSummary:
    """A lifecycle summary for one atomic note."""

    note_id: str
    status: str
    note_type: str
    concept: str
    path: str


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
    obsidian_dir = context.root / "07_exports" / "obsidian"
    exported: list[Path] = []
    manifest_notes: list[dict[str, object]] = []
    reviewed_notes: list[dict[str, object]] = []
    for folder in sorted((context.root / "04_atomic_notes").iterdir()):
        if not folder.is_dir() or folder.name == "drafts":
            continue
        for note_path in sorted(folder.glob("*.md")):
            text = note_path.read_text(encoding="utf-8")
            if _frontmatter_value(text, "reviewed_by_user") != "true":
                continue
            _require_note_quality(context.root, note_path, f"Reviewed note {note_path.stem}")
            destination = obsidian_dir / note_path.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            exported.append(destination)
            note_entry = {
                "note_id": note_path.stem,
                "concept": _frontmatter_value(text, "concept") or note_path.stem,
                "type": _frontmatter_value(text, "type") or folder.name.rstrip("s"),
                "topic": _frontmatter_value(text, "topic") or "",
                "created_by": _frontmatter_value(text, "created_by") or "",
                "path": destination.relative_to(destination.parent).as_posix(),
                "review_status": _frontmatter_value(text, "review_status") or "",
                "source_id": _frontmatter_value(text, "source_id") or "",
                "source_title": _frontmatter_value(text, "source_title") or "",
                "source_location": _frontmatter_value(text, "source_location") or "",
                "tags": _frontmatter_list(text, "tags"),
                "related": _frontmatter_list(text, "related"),
            }
            manifest_notes.append(note_entry)
            reviewed_notes.append({"text": text, "destination": destination, "entry": note_entry})
    backlinks = _obsidian_backlinks(manifest_notes)
    _attach_obsidian_backlinks(manifest_notes, backlinks)
    _prune_stale_obsidian_exports(context.root, obsidian_dir, {path.name for path in exported})
    for note in reviewed_notes:
        entry = note["entry"]
        if not isinstance(entry, dict):
            continue
        destination = note["destination"]
        if not isinstance(destination, Path):
            continue
        write_text(
            destination,
            _with_obsidian_backlinks(
                str(note["text"]),
                str(entry["note_id"]),
                backlinks,
            ),
        )
    _write_export_manifest(obsidian_dir, manifest_notes)
    _write_export_index(obsidian_dir, manifest_notes)
    append_project_log(context, f"Exported {len(exported)} reviewed note(s) to Obsidian.")
    return exported


def list_atomic_notes(project_path: Path | str, *, status: str = "all") -> list[AtomicNoteSummary]:
    """List atomic notes by their current lifecycle state."""

    allowed_statuses = {"all", "pending", "reviewed", "exported"}
    if status not in allowed_statuses:
        allowed = ", ".join(sorted(allowed_statuses))
        raise ValueError(f"Unknown note status {status!r}; expected one of: {allowed}")

    context = load_project(project_path)
    exported_ids = _exported_note_ids(context.root)
    reviewed = _reviewed_note_summaries(context.root, exported_ids)
    reviewed_ids = {item.note_id for item in reviewed}
    pending = _pending_note_summaries(context.root, reviewed_ids)
    items = [*pending, *reviewed]
    if status != "all":
        items = [item for item in items if item.status == status]
    return sorted(items, key=lambda item: (_note_status_order(item.status), item.note_id))


def _write_export_manifest(obsidian_dir: Path, exported_notes: list[dict[str, object]]) -> None:
    manifest = {
        "version": 3,
        "exported_notes": sorted(exported_notes, key=lambda item: item["note_id"]),
    }
    write_text(
        obsidian_dir / "export_manifest.json",
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    )


def _write_export_index(obsidian_dir: Path, exported_notes: list[dict[str, object]]) -> None:
    notes = sorted(exported_notes, key=lambda item: (str(item["type"]), str(item["concept"])))
    lines = ["# Socrates Obsidian Export", ""]
    if not notes:
        lines.append("No reviewed notes exported.")
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


def _prune_stale_obsidian_exports(
    project_root: Path,
    obsidian_dir: Path,
    active_filenames: set[str],
) -> None:
    manifest = read_obsidian_export_manifest(project_root)
    if not isinstance(manifest, dict):
        return
    exported_notes = manifest.get("exported_notes", [])
    if not isinstance(exported_notes, list):
        return
    for note in exported_notes:
        if not isinstance(note, dict):
            continue
        path_value = note.get("path")
        if not isinstance(path_value, str) or not path_value:
            continue
        stale_path = obsidian_dir / path_value
        if stale_path.name in active_filenames:
            continue
        try:
            stale_path.resolve().relative_to(obsidian_dir.resolve())
        except ValueError:
            continue
        if stale_path.suffix != ".md" or not stale_path.is_file():
            continue
        stale_path.unlink()


def _obsidian_backlinks(exported_notes: list[dict[str, object]]) -> dict[str, list[dict[str, str]]]:
    by_target: dict[str, str] = {}
    for note in exported_notes:
        note_id = str(note["note_id"])
        concept = str(note["concept"])
        by_target[note_id] = note_id
        by_target[slugify_topic(concept)] = note_id

    backlinks: dict[str, list[dict[str, str]]] = {str(note["note_id"]): [] for note in exported_notes}
    for note in exported_notes:
        source_id = str(note["note_id"])
        source_concept = str(note["concept"])
        source_path = str(note["path"])
        related = note.get("related", [])
        if not isinstance(related, list):
            continue
        for item in related:
            target_id = by_target.get(_obsidian_link_target_id(str(item)))
            if not target_id or target_id == source_id:
                continue
            backlinks[target_id].append(
                {"note_id": source_id, "concept": source_concept, "path": source_path}
            )
    return {
        note_id: sorted(_unique_backlinks(items), key=lambda item: item["concept"])
        for note_id, items in backlinks.items()
    }


def _attach_obsidian_backlinks(
    exported_notes: list[dict[str, object]],
    backlinks: dict[str, list[dict[str, str]]],
) -> None:
    for note in exported_notes:
        note["backlinks"] = backlinks.get(str(note["note_id"]), [])


def _obsidian_link_target_id(value: str) -> str:
    text = value.strip().strip('"')
    if text.startswith("[[") and text.endswith("]]"):
        text = text[2:-2]
    target = text.split("|", 1)[0].strip()
    return slugify_topic(target)


def _unique_backlinks(items: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for item in items:
        note_id = item["note_id"]
        if note_id in seen:
            continue
        seen.add(note_id)
        unique.append(item)
    return unique


def _with_obsidian_backlinks(
    text: str,
    note_id: str,
    backlinks: dict[str, list[dict[str, str]]],
) -> str:
    links = backlinks.get(note_id, [])
    if not links:
        return text
    lines = ["## Socrates Backlinks", ""]
    lines.extend(f"- [[{item['note_id']}|{item['concept']}]]" for item in links)
    return text.rstrip() + "\n\n" + "\n".join(lines) + "\n"


def _pending_note_summaries(
    project_root: Path,
    reviewed_ids: set[str],
) -> list[AtomicNoteSummary]:
    draft_dir = project_root / "04_atomic_notes" / "drafts"
    if not draft_dir.exists():
        return []
    items: list[AtomicNoteSummary] = []
    for note_path in sorted(draft_dir.glob("*.md"), key=lambda path: path.stem):
        if note_path.stem in reviewed_ids:
            continue
        text = note_path.read_text(encoding="utf-8")
        items.append(
            _note_summary(
                project_root=project_root,
                note_path=note_path,
                status="pending",
                text=text,
            )
        )
    return items


def _reviewed_note_summaries(
    project_root: Path,
    exported_ids: set[str],
) -> list[AtomicNoteSummary]:
    notes_root = project_root / "04_atomic_notes"
    if not notes_root.exists():
        return []
    items: list[AtomicNoteSummary] = []
    for folder in sorted(notes_root.iterdir(), key=lambda path: path.name):
        if not folder.is_dir() or folder.name == "drafts":
            continue
        for note_path in sorted(folder.glob("*.md"), key=lambda path: path.stem):
            text = note_path.read_text(encoding="utf-8")
            if _frontmatter_value(text, "reviewed_by_user") != "true":
                continue
            status = "exported" if note_path.stem in exported_ids else "reviewed"
            items.append(
                _note_summary(
                    project_root=project_root,
                    note_path=note_path,
                    status=status,
                    text=text,
                )
            )
    return items


def _note_summary(
    *,
    project_root: Path,
    note_path: Path,
    status: str,
    text: str,
) -> AtomicNoteSummary:
    return AtomicNoteSummary(
        note_id=note_path.stem,
        status=status,
        note_type=_frontmatter_value(text, "type") or "definition",
        concept=_frontmatter_value(text, "concept") or note_path.stem,
        path=note_path.relative_to(project_root).as_posix(),
    )


def _exported_note_ids(project_root: Path) -> set[str]:
    return obsidian_exported_note_ids(project_root)


def _note_status_order(status: str) -> int:
    return {"pending": 0, "reviewed": 1, "exported": 2}.get(status, 3)


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
