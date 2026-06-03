"""Local reference import and source registry updates."""

from __future__ import annotations

from pathlib import Path
import shutil

from .context import append_project_log, load_project
from .contracts import SourceRecord
from .project import slugify_topic


REFERENCE_TYPES = {
    ".pdf": ("pdf", "books"),
    ".md": ("markdown", "markdown"),
    ".markdown": ("markdown", "markdown"),
    ".tex": ("latex", "latex"),
    ".txt": ("text", "text"),
}


def import_reference(
    project_path: Path | str,
    source_path: Path | str,
    *,
    role: str,
    title: str | None = None,
    priority: int = 1,
    notes: str = "",
) -> SourceRecord:
    """Import a local reference file into a Socrates project."""

    context = load_project(project_path)
    source = Path(source_path).expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise FileNotFoundError(f"Reference file does not exist: {source}")

    source_type, folder = _reference_type(source)
    raw_dir = context.references_dir / "raw" / folder
    raw_dir.mkdir(parents=True, exist_ok=True)
    destination = raw_dir / source.name
    shutil.copy2(source, destination)

    display_title = title or source.stem.replace("_", " ").title()
    source_id = _unique_source_id(context.source_registry.read_text(encoding="utf-8"), display_title)
    record = SourceRecord(
        id=source_id,
        type=source_type,
        title=display_title,
        role=role,
        priority=priority,
        status="raw_imported",
        local_path=_relative_project_path(context.root, destination),
        processed_paths={"markdown": None, "curated": None},
        notes=notes,
    )

    _append_source_record(context.source_registry, record)
    append_project_log(context, f"Imported reference {record.id} from {source.name}.")
    return record


def _reference_type(source: Path) -> tuple[str, str]:
    return REFERENCE_TYPES.get(source.suffix.lower(), ("file", "files"))


def _unique_source_id(registry_text: str, title: str) -> str:
    existing_ids = _registry_ids(registry_text)
    base = slugify_topic(title)
    candidate = base
    index = 2
    while candidate in existing_ids:
        candidate = f"{base}_{index}"
        index += 1
    return candidate


def _registry_ids(registry_text: str) -> set[str]:
    ids: set[str] = set()
    for line in registry_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- id: "):
            ids.add(stripped.removeprefix("- id: ").strip())
    return ids


def _append_source_record(registry_path: Path, record: SourceRecord) -> None:
    current = registry_path.read_text(encoding="utf-8").rstrip()
    item_yaml = _indent_registry_item(record.to_registry_yaml())
    if current == "sources: []":
        updated = "sources:\n" + item_yaml
    elif current == "sources:":
        updated = current + "\n" + item_yaml
    else:
        updated = current + "\n" + item_yaml
    registry_path.write_text(updated.rstrip() + "\n", encoding="utf-8", newline="\n")


def _indent_registry_item(item_yaml: str) -> str:
    return "\n".join(f"  {line}" if line else line for line in item_yaml.rstrip().splitlines()) + "\n"


def _relative_project_path(project_root: Path, path: Path) -> str:
    return path.relative_to(project_root).as_posix()
