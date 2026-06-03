"""Atomic note review and Obsidian export workflows."""

from __future__ import annotations

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

    issues = atomic_note_quality_issues(draft_path, context.root)
    if issues:
        result = check_atomic_note_quality(context.root)
        raise ValueError(
            f"Draft note {note_id} failed quality gate: "
            f"{'; '.join(issues)}. See {result.report_path}"
        )

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
    for folder in sorted((context.root / "04_atomic_notes").iterdir()):
        if not folder.is_dir() or folder.name == "drafts":
            continue
        for note_path in sorted(folder.glob("*.md")):
            text = note_path.read_text(encoding="utf-8")
            if _frontmatter_value(text, "reviewed_by_user") != "true":
                continue
            destination = context.root / "07_exports" / "obsidian" / note_path.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(note_path, destination)
            exported.append(destination)
    if exported:
        append_project_log(context, f"Exported {len(exported)} reviewed note(s) to Obsidian.")
    return exported


def _frontmatter_value(text: str, key: str) -> str | None:
    frontmatter = _frontmatter_lines(text)
    prefix = f"{key}:"
    for line in frontmatter:
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip().strip('"')
    return None


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
