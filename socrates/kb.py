"""Reference knowledge-base construction and retrieval."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re

from .context import load_project, write_json, write_text
from .project import slugify_topic


@dataclass(frozen=True)
class ReferenceKbBuildResult:
    """Summary of a reference KB build."""

    index_path: Path
    object_count: int
    chunk_count: int


OBJECT_TYPES = {
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

OBJECT_NUMBER_PATTERN = re.compile(r"^[A-Za-z]?\d+(?:\.\d+)*(?:[a-z])?$")
SOURCE_METADATA_KEYS = {"source_id", "title", "role", "raw_path"}


def build_reference_kb(project_path: Path | str) -> ReferenceKbBuildResult:
    """Build a small source-grounded reference index from curated Markdown."""

    context = load_project(project_path)
    curated_dir = context.references_dir / "curated"
    objects: list[dict[str, object]] = []

    for markdown_path in sorted(curated_dir.glob("*.md")):
        objects.extend(_extract_objects(context.root, markdown_path))

    index = {
        "schema_version": 1,
        "objects": objects,
        "chunks": [_chunk_from_object(item) for item in objects],
    }
    index_path = context.root / "06_kb" / "chunks" / "reference_index.json"
    write_json(index_path, index)
    write_json(context.root / "06_kb" / "concept_graph.json", _concept_graph(objects))
    write_json(context.root / "06_kb" / "dependency_graph.json", _dependency_graph(objects))
    write_json(context.root / "06_kb" / "chapter_index.json", _chapter_index(objects))
    write_json(context.root / "06_kb" / "theorem_index.json", _theorem_index(objects))
    write_json(context.root / "06_kb" / "exercise_index.json", _exercise_index(objects))
    _write_ingestion_eval(context.evals_dir / "ingestion_eval.md", len(objects))

    return ReferenceKbBuildResult(
        index_path=index_path,
        object_count=len(objects),
        chunk_count=len(index["chunks"]),
    )


def search_reference_kb(project_path: Path | str, query: str, *, limit: int = 10) -> list[dict[str, object]]:
    """Return source-grounded reference objects matching a query."""

    return _search_reference_objects(project_path, query, limit=limit)


def find_counterexamples(project_path: Path | str, concept: str, *, limit: int = 10) -> list[dict[str, object]]:
    """Return matching counterexample objects from the reference KB."""

    return _search_reference_objects(
        project_path,
        concept,
        limit=limit,
        object_type="counterexample",
    )


def list_reference_kb_objects(
    project_path: Path | str,
    *,
    object_type: str = "all",
    source_id: str | None = None,
) -> list[dict[str, object]]:
    """Return indexed reference objects with optional lifecycle filters."""

    allowed_types = {"all", *OBJECT_TYPES}
    if object_type not in allowed_types:
        allowed = ", ".join(sorted(allowed_types))
        raise ValueError(
            f"Unknown reference object type {object_type!r}; expected one of: {allowed}"
        )

    context = load_project(project_path)
    index_path = context.root / "06_kb" / "chunks" / "reference_index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    objects = index.get("objects", []) if isinstance(index, dict) else []
    if not isinstance(objects, list):
        return []

    items: list[dict[str, object]] = []
    for item in objects:
        if not isinstance(item, dict):
            continue
        if (
            object_type != "all"
            and str(item.get("type", "")).casefold() != object_type
        ):
            continue
        if source_id is not None and _object_source_id(item) != source_id:
            continue
        items.append(item)
    return items


def _search_reference_objects(
    project_path: Path | str,
    query: str,
    *,
    limit: int,
    object_type: str | None = None,
) -> list[dict[str, object]]:
    context = load_project(project_path)
    index_path = context.root / "06_kb" / "chunks" / "reference_index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    query_text = query.casefold()
    matches = []
    for item in index.get("objects", []):
        if not isinstance(item, dict):
            continue
        if object_type is not None and str(item.get("type", "")).casefold() != object_type:
            continue
        haystack = _search_haystack(item)
        if query_text in haystack:
            matches.append(item)
        if len(matches) >= limit:
            break
    return matches


def _object_source_id(item: dict[str, object]) -> str:
    source = item.get("source", {})
    if not isinstance(source, dict):
        return ""
    return str(source.get("source_id", ""))


def _search_haystack(item: dict[str, object]) -> str:
    source = item.get("source", {})
    source_terms: list[str] = []
    if isinstance(source, dict):
        source_terms.extend(str(value) for value in source.values() if value)
        page = str(source.get("page", "")).strip()
        if page:
            source_terms.append(f"p{page}")
    return " ".join(
        [
            str(item.get("number", "")),
            str(item.get("title", "")),
            str(item.get("statement", "")),
            " ".join(str(dep) for dep in item.get("dependencies", [])),
            " ".join(source_terms),
        ]
    ).casefold()


def _extract_objects(project_root: Path, markdown_path: Path) -> list[dict[str, object]]:
    lines = markdown_path.read_text(encoding="utf-8").splitlines()
    chapter = ""
    section = ""
    source_metadata: dict[str, str] = {"source_id": ""}
    objects: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    body: list[str] = []

    def flush() -> None:
        nonlocal body, current
        if current is None:
            return
        statement, dependencies, page = _split_statement_and_metadata(body)
        current["statement"] = statement
        current["dependencies"] = dependencies
        if page:
            source = current.get("source")
            if isinstance(source, dict):
                source["page"] = page
        objects.append(current)
        body = []
        current = None

    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        metadata_key = _metadata_key(stripped)
        if metadata_key in SOURCE_METADATA_KEYS:
            if current is not None:
                body.append(line)
            else:
                source_metadata[metadata_key] = _metadata_value(stripped)
            continue

        if line.startswith("### "):
            flush()
            parsed = parse_object_heading(line.removeprefix("### ").strip())
            if parsed is None:
                current = None
                body = []
                continue
            object_type, title, number = parsed
            object_id = slugify_topic(title)
            current = {
                "id": object_id,
                "type": object_type,
                "title": title,
                "source": _source_for_object(
                    project_root,
                    markdown_path,
                    source_metadata,
                    chapter=chapter,
                    section=section,
                    line=line_number,
                ),
            }
            if number:
                current["number"] = number
            body = []
            continue

        if line.startswith("# ") and not line.startswith("## "):
            chapter = line.removeprefix("# ").strip()
        elif line.startswith("## "):
            section = line.removeprefix("## ").strip()
        elif current is not None:
            body.append(line)

    flush()
    return objects


def _source_for_object(
    project_root: Path,
    markdown_path: Path,
    source_metadata: dict[str, str],
    *,
    chapter: str,
    section: str,
    line: int,
) -> dict[str, object]:
    source: dict[str, object] = {
        "source_id": source_metadata.get("source_id", ""),
        "path": markdown_path.relative_to(project_root).as_posix(),
        "chapter": chapter,
        "section": section,
        "line": line,
    }
    for key in ("title", "role", "raw_path"):
        value = source_metadata.get(key, "")
        if value:
            source[key] = value
    return source


def parse_object_heading(heading: str) -> tuple[str, str, str | None] | None:
    label, separator, title = heading.partition(":")
    if not separator:
        return None
    label_parts = label.strip().split(maxsplit=1)
    object_type = label_parts[0].casefold() if label_parts else ""
    if object_type not in OBJECT_TYPES:
        return None
    number = label_parts[1].strip() if len(label_parts) == 2 else None
    if number and not OBJECT_NUMBER_PATTERN.match(number):
        return None
    return object_type, title.strip(), number


def _split_statement_and_metadata(lines: list[str]) -> tuple[str, list[str], str | None]:
    statement_lines: list[str] = []
    dependencies: list[str] = []
    page: str | None = None
    for line in lines:
        stripped = line.strip()
        if stripped.casefold().startswith("depends:"):
            dependencies.extend(
                item.strip()
                for item in stripped.split(":", 1)[1].split(",")
                if item.strip()
            )
        elif _metadata_key(stripped) == "page":
            page = _metadata_value(stripped)
        else:
            statement_lines.append(line)
    return "\n".join(statement_lines).strip(), dependencies, page


def _metadata_key(line: str) -> str:
    key, separator, _ = line.removeprefix("-").strip().partition(":")
    return key.strip().casefold() if separator else ""


def _metadata_value(line: str) -> str:
    _, _, value = line.removeprefix("-").strip().partition(":")
    return value.strip().strip('"')


def _chunk_from_object(item: dict[str, object]) -> dict[str, object]:
    metadata = {
        "object_id": item["id"],
        "type": item["type"],
        "title": item["title"],
        "source": item["source"],
        "dependencies": item.get("dependencies", []),
    }
    metadata.update(_chunk_provenance_metadata(item))
    if item.get("number"):
        metadata["number"] = item["number"]
    return {
        "id": f"{item['id']}_chunk",
        "object_id": item["id"],
        "text": item.get("statement", ""),
        "metadata": metadata,
    }


def _chunk_provenance_metadata(item: dict[str, object]) -> dict[str, object]:
    source = item.get("source", {})
    if not isinstance(source, dict):
        return {}
    metadata: dict[str, object] = {}
    for source_key, metadata_key in (
        ("source_id", "source_id"),
        ("chapter", "chapter"),
        ("section", "section"),
        ("page", "page"),
        ("title", "source_title"),
        ("role", "source_role"),
        ("raw_path", "raw_path"),
        ("path", "source_path"),
        ("line", "source_line"),
    ):
        value = source.get(source_key)
        if value:
            metadata[metadata_key] = value
    return metadata


def _concept_graph(objects: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    nodes: dict[str, dict[str, object]] = {}
    edges: list[dict[str, object]] = []
    for item in objects:
        object_id = str(item["id"])
        nodes[object_id] = {
            "id": object_id,
            "label": item["title"],
            "type": item["type"],
        }
        for dependency in item.get("dependencies", []):
            dependency_id = slugify_topic(str(dependency))
            nodes.setdefault(
                dependency_id,
                {"id": dependency_id, "label": str(dependency), "type": "concept"},
            )
            edges.append(
                {
                    "source": object_id,
                    "target": dependency_id,
                    "relationship": "prerequisite",
                }
            )
    return {"nodes": list(nodes.values()), "edges": edges}


def _dependency_graph(objects: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    graph = _concept_graph(objects)
    return {
        "nodes": graph["nodes"],
        "edges": [
            edge for edge in graph["edges"] if edge["relationship"] == "prerequisite"
        ],
    }


def _chapter_index(objects: list[dict[str, object]]) -> dict[str, object]:
    chapters: list[dict[str, object]] = []
    chapter_lookup: dict[str, dict[str, object]] = {}
    section_lookup: dict[tuple[str, str, str], dict[str, object]] = {}

    for item in objects:
        source = item.get("source", {})
        if not isinstance(source, dict):
            source = {}
        chapter_title = str(source.get("chapter") or "Unassigned")
        section_title = str(source.get("section") or "Unassigned")
        source_path = str(source.get("path") or "unknown")

        chapter = chapter_lookup.get(chapter_title)
        if chapter is None:
            chapter = {"title": chapter_title, "sections": []}
            chapter_lookup[chapter_title] = chapter
            chapters.append(chapter)

        section_key = (chapter_title, section_title, source_path)
        section = section_lookup.get(section_key)
        if section is None:
            section = {
                "title": section_title,
                "source_path": source_path,
                "objects": [],
            }
            section_lookup[section_key] = section
            sections = chapter["sections"]
            if isinstance(sections, list):
                sections.append(section)

        section_objects = section["objects"]
        if isinstance(section_objects, list):
            section_objects.append(_chapter_index_object(item))

    return {"schema_version": 2, "chapters": chapters}


def _chapter_index_object(item: dict[str, object]) -> dict[str, object]:
    source = item.get("source", {})
    if not isinstance(source, dict):
        source = {}
    indexed_object = {
        "id": str(item.get("id", "")),
        "type": str(item.get("type", "")),
        "title": str(item.get("title", "")),
        "source_path": str(source.get("path") or "unknown"),
    }
    if source.get("line"):
        indexed_object["line"] = source["line"]
    if source.get("source_id"):
        indexed_object["source_id"] = str(source["source_id"])
    if source.get("title"):
        indexed_object["source_title"] = str(source["title"])
    if source.get("role"):
        indexed_object["source_role"] = str(source["role"])
    if source.get("raw_path"):
        indexed_object["raw_path"] = str(source["raw_path"])
    if source.get("page"):
        indexed_object["page"] = str(source["page"])
    if item.get("number"):
        indexed_object["number"] = str(item["number"])
    return indexed_object


def _theorem_index(objects: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    theorem_types = {"theorem", "proposition", "lemma", "corollary"}
    return {
        "theorems": [
            item for item in objects if str(item.get("type", "")) in theorem_types
        ]
    }


def _exercise_index(objects: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    return {
        "exercises": [
            item for item in objects if str(item.get("type", "")) == "exercise"
        ]
    }


def _write_ingestion_eval(path: Path, object_count: int) -> None:
    write_text(
        path,
        "# Ingestion Eval\n\n"
        f"- Curated objects indexed: {object_count}\n"
        "- Raw references modified: no\n"
        "- Curated-only policy: enforced\n",
    )
