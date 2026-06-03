"""Local reference import and source registry updates."""

from __future__ import annotations

from pathlib import Path
import re
import shutil

from .context import append_project_log, load_project, write_text
from .contracts import SourceRecord, yaml_scalar
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


def curate_reference(project_path: Path | str, source_id: str) -> Path:
    """Create a curated Markdown draft for an imported text-like reference."""

    context = load_project(project_path)
    registry_text = context.source_registry.read_text(encoding="utf-8")
    record = _find_registry_record(registry_text, source_id)
    if record is None:
        raise ValueError(f"Unknown source id: {source_id}")

    source_type = record.get("type", "")
    if source_type not in {"markdown", "text", "latex"}:
        raise ValueError(f"Curated draft passthrough is not supported for {source_type} sources")

    raw_path = context.root / str(record["local_path"])
    if not raw_path.exists():
        raise FileNotFoundError(f"Imported source file is missing: {raw_path}")

    converted_path = context.references_dir / "converted" / "markdown" / f"{source_id}.md"
    converted_text = _converted_markdown(record, raw_path.read_text(encoding="utf-8"))
    write_text(converted_path, converted_text)

    curated_path = context.references_dir / "curated" / f"{source_id}.curated.md"
    write_text(curated_path, _curated_markdown(record, converted_text))
    relative_markdown_path = _relative_project_path(context.root, converted_path)
    relative_curated_path = _relative_project_path(context.root, curated_path)
    _update_registry_source(
        context.source_registry,
        source_id,
        status="curated_draft",
        markdown_path=relative_markdown_path,
        curated_path=relative_curated_path,
    )
    append_project_log(context, f"Created curated draft for reference {source_id}.")
    return curated_path


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


def _find_registry_record(registry_text: str, source_id: str) -> dict[str, str] | None:
    current: dict[str, str] | None = None
    in_processed_paths = False
    for line in registry_text.splitlines():
        if line.startswith("  - id: "):
            if current and current.get("id") == source_id:
                return current
            current = {"id": line.removeprefix("  - id: ").strip()}
            in_processed_paths = False
            continue
        if current is None:
            continue
        stripped = line.strip()
        if stripped == "processed_paths:":
            in_processed_paths = True
            continue
        if line.startswith("      ") and in_processed_paths:
            key, separator, value = stripped.partition(":")
            if separator:
                current[f"processed_paths.{key}"] = _registry_value(value.strip())
            continue
        if line.startswith("    ") and not line.startswith("      "):
            in_processed_paths = False
            key, separator, value = stripped.partition(":")
            if separator:
                current[key] = _registry_value(value.strip())
    if current and current.get("id") == source_id:
        return current
    return None


def _registry_value(value: str) -> str:
    if value == "null":
        return ""
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    return value


def _curated_markdown(record: dict[str, str], source_text: str) -> str:
    return (
        f"# Curated Reference: {record.get('title', record['id'])}\n\n"
        "<!-- socrates-curated-draft: review before building the reference KB -->\n\n"
        "## Source Metadata\n\n"
        f"- source_id: {record['id']}\n"
        f"- title: {record.get('title', '')}\n"
        f"- role: {record.get('role', '')}\n"
        f"- raw_path: {record.get('local_path', '')}\n\n"
        "## Curated Content\n\n"
        f"{source_text.rstrip()}\n"
    )


def _converted_markdown(record: dict[str, str], source_text: str) -> str:
    converted_text = _latex_to_markdown(source_text) if record.get("type") == "latex" else source_text
    return (
        f"# Converted Reference: {record.get('title', record['id'])}\n\n"
        "<!-- socrates-converted-reference: generated from imported raw source -->\n\n"
        "## Source Metadata\n\n"
        f"- source_id: {record['id']}\n"
        f"- raw_path: {record.get('local_path', '')}\n\n"
        "## Converted Content\n\n"
        f"{converted_text.rstrip()}\n"
    )


LATEX_OBJECT_TYPES = {
    "definition",
    "theorem",
    "proposition",
    "lemma",
    "corollary",
    "example",
    "counterexample",
    "proof",
    "exercise",
    "remark",
    "notation",
}
LATEX_SECTION_RE = re.compile(r"\\(?P<level>section|subsection|subsubsection)\{(?P<title>[^}]*)\}")
LATEX_BEGIN_RE = re.compile(
    r"\\begin\{(?P<kind>[a-zA-Z*]+)\}(?:\[(?P<title>[^\]]+)\])?"
)
LATEX_END_RE = re.compile(r"\\end\{(?P<kind>[a-zA-Z*]+)\}")


def _latex_to_markdown(source_text: str) -> str:
    lines: list[str] = []
    for raw_line in source_text.splitlines():
        stripped = raw_line.strip()
        section = LATEX_SECTION_RE.fullmatch(stripped)
        if section:
            lines.append(f"## {_plain_latex_title(section.group('title'))}")
            continue

        begin = LATEX_BEGIN_RE.fullmatch(stripped)
        if begin:
            kind = begin.group("kind").rstrip("*").casefold()
            if kind in LATEX_OBJECT_TYPES:
                title = begin.group("title") or kind.replace("_", " ").title()
                lines.append(f"### {kind.title()}: {_plain_latex_title(title)}")
                continue

        end = LATEX_END_RE.fullmatch(stripped)
        if end and end.group("kind").rstrip("*").casefold() in LATEX_OBJECT_TYPES:
            continue
        if stripped.startswith(r"\label{"):
            continue
        lines.append(raw_line)
    return "\n".join(lines).rstrip() + "\n"


def _plain_latex_title(title: str) -> str:
    return title.replace(r"\_", "_").strip()


def _update_registry_source(
    registry_path: Path,
    source_id: str,
    *,
    status: str,
    markdown_path: str,
    curated_path: str,
) -> None:
    lines = registry_path.read_text(encoding="utf-8").splitlines()
    updated: list[str] = []
    in_target = False
    in_processed_paths = False
    processed_updated = False
    for line in lines:
        if line.startswith("  - id: "):
            if in_target and in_processed_paths and not processed_updated:
                updated.append(f"      curated: {yaml_scalar(curated_path)}")
            in_target = line.removeprefix("  - id: ").strip() == source_id
            in_processed_paths = False
            processed_updated = False
            updated.append(line)
            continue

        if in_target and line.startswith("    status: "):
            updated.append(f"    status: {status}")
            continue

        if in_target and line.strip() == "processed_paths:":
            in_processed_paths = True
            updated.append(line)
            continue

        if in_target and in_processed_paths:
            if line.startswith("      markdown: "):
                updated.append(f"      markdown: {yaml_scalar(markdown_path)}")
                continue
            if line.startswith("      curated: "):
                updated.append(f"      curated: {yaml_scalar(curated_path)}")
                processed_updated = True
                continue
            if line.startswith("    ") and not line.startswith("      "):
                if not processed_updated:
                    updated.append(f"      curated: {yaml_scalar(curated_path)}")
                    processed_updated = True
                in_processed_paths = False

        updated.append(line)

    if in_target and in_processed_paths and not processed_updated:
        updated.append(f"      curated: {yaml_scalar(curated_path)}")
    registry_path.write_text("\n".join(updated).rstrip() + "\n", encoding="utf-8", newline="\n")


def _indent_registry_item(item_yaml: str) -> str:
    return "\n".join(f"  {line}" if line else line for line in item_yaml.rstrip().splitlines()) + "\n"


def _relative_project_path(project_root: Path, path: Path) -> str:
    return path.relative_to(project_root).as_posix()
