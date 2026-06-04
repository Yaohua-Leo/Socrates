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


@dataclass(frozen=True)
class ReferenceKbStatus:
    """Current freshness state of the reference KB index."""

    index_path: Path
    object_count: int
    status: str


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
RELATIONSHIP_METADATA_KEYS = {
    "example of": "example_of",
    "counterexample to": "counterexample_to",
    "proof of": "used_in_proof_of",
    "used in proof of": "used_in_proof_of",
    "generalizes": "generalizes",
    "special case of": "special_case_of",
    "equivalent to": "equivalent_to",
}
CONCEPT_RELATIONSHIP_TYPES = set(RELATIONSHIP_METADATA_KEYS.values())
REFERENCE_KB_ARTIFACTS = (
    ("concept_graph.json", ("nodes", "edges")),
    ("dependency_graph.json", ("nodes", "edges")),
    ("chapter_index.json", ("chapters",)),
    ("theorem_index.json", ("theorems",)),
    ("exercise_index.json", ("exercises",)),
)


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


def reference_kb_status(project_path: Path | str) -> ReferenceKbStatus:
    """Return object count plus freshness for the curated-reference KB."""

    context = load_project(project_path)
    curated_paths = sorted((context.references_dir / "curated").glob("*.md"))
    index_path = context.root / "06_kb" / "chunks" / "reference_index.json"

    object_count = 0
    index_status = "missing" if curated_paths else "not_applicable"
    index_mtime_ns = 0

    if index_path.exists():
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return ReferenceKbStatus(
                index_path=index_path,
                object_count=0,
                status="invalid",
            )
        if not _valid_reference_index_schema(
            index,
            context.root,
            validate_source_text=False,
        ):
            return ReferenceKbStatus(
                index_path=index_path,
                object_count=0,
                status="invalid",
            )
        objects = index["objects"]
        object_count = len(objects)
        artifact_status, artifact_mtime_ns = _reference_kb_artifacts_status(context.root)
        if artifact_status != "current":
            return ReferenceKbStatus(
                index_path=index_path,
                object_count=0,
                status=artifact_status,
            )
        index_mtime_ns = min(index_path.stat().st_mtime_ns, artifact_mtime_ns)
        index_status = "current" if curated_paths else "not_applicable"

        if curated_paths and any(
            path.stat().st_mtime_ns > index_mtime_ns for path in curated_paths
        ):
            index_status = "stale"
        elif not _valid_reference_index_schema(index, context.root):
            return ReferenceKbStatus(
                index_path=index_path,
                object_count=0,
                status="invalid",
            )

    return ReferenceKbStatus(
        index_path=index_path,
        object_count=object_count,
        status=index_status,
    )


def search_reference_kb(
    project_path: Path | str,
    query: str,
    *,
    limit: int = 10,
    object_type: str = "all",
    source_id: str | None = None,
    relationship_type: str = "all",
) -> list[dict[str, object]]:
    """Return source-grounded reference objects matching a query."""

    allowed_types = {"all", *OBJECT_TYPES}
    if object_type not in allowed_types:
        allowed = ", ".join(sorted(allowed_types))
        raise ValueError(
            f"Unknown reference object type {object_type!r}; expected one of: {allowed}"
        )
    allowed_relationship_types = {"all", *CONCEPT_RELATIONSHIP_TYPES}
    if relationship_type not in allowed_relationship_types:
        allowed = ", ".join(sorted(allowed_relationship_types))
        raise ValueError(
            f"Unknown reference relationship type {relationship_type!r}; expected one of: {allowed}"
        )
    return _search_reference_objects(
        project_path,
        query,
        limit=limit,
        object_type=None if object_type == "all" else object_type,
        source_id=source_id,
        relationship_type=None if relationship_type == "all" else relationship_type,
    )


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
    index = read_reference_index(context.root, index_path)
    objects = index.get("objects", []) if isinstance(index, dict) else []
    if not isinstance(objects, list):
        return []
    quality_by_source_path = _ingestion_quality_by_source_path(context.root)

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
        source_path = _object_source_path(item)
        if source_path in quality_by_source_path:
            item = dict(item)
            item["source_quality_status"] = quality_by_source_path[source_path]
        items.append(item)
    return items


def list_reference_kb_relationships(
    project_path: Path | str,
    *,
    relationship_type: str = "all",
) -> list[dict[str, str]]:
    """Return explicit non-prerequisite concept-graph relationships."""

    allowed_types = {"all", *CONCEPT_RELATIONSHIP_TYPES}
    if relationship_type not in allowed_types:
        allowed = ", ".join(sorted(allowed_types))
        raise ValueError(
            f"Unknown reference relationship type {relationship_type!r}; expected one of: {allowed}"
        )

    context = load_project(project_path)
    graph = read_reference_concept_graph(context.root)
    edges = graph.get("edges", []) if isinstance(graph, dict) else []
    if not isinstance(edges, list):
        return []

    relationships: list[dict[str, str]] = []
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        relationship = str(edge.get("relationship", "")).strip()
        if relationship == "prerequisite":
            continue
        if relationship_type != "all" and relationship != relationship_type:
            continue
        source = str(edge.get("source", "")).strip()
        target = str(edge.get("target", "")).strip()
        if not source or not target:
            continue
        relationships.append(
            {
                "source": source,
                "target": target,
                "relationship": relationship,
            }
        )
    return relationships


def read_reference_chapter_index(project_path: Path | str) -> dict[str, object]:
    """Read the generated chapter index or raise an actionable rebuild error."""

    context = load_project(project_path)
    index_path = context.root / "06_kb" / "chapter_index.json"
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(
            _reference_chapter_index_rebuild_message(context.root, "is missing")
        ) from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            _reference_chapter_index_rebuild_message(context.root, "is invalid")
        ) from exc
    if not isinstance(index, dict) or not isinstance(index.get("chapters", []), list):
        raise ValueError(
            _reference_chapter_index_rebuild_message(
                context.root,
                "has invalid schema",
            )
        )
    return index


def read_reference_concept_graph(project_path: Path | str) -> dict[str, object]:
    """Read the generated concept graph or raise an actionable rebuild error."""

    context = load_project(project_path)
    graph_path = context.root / "06_kb" / "concept_graph.json"
    try:
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(
            _reference_concept_graph_rebuild_message(context.root, "is missing")
        ) from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            _reference_concept_graph_rebuild_message(context.root, "is invalid")
        ) from exc
    if not isinstance(graph, dict) or not isinstance(graph.get("edges", []), list):
        raise ValueError(
            _reference_concept_graph_rebuild_message(
                context.root,
                "has invalid schema",
            )
        )
    return graph


def _search_reference_objects(
    project_path: Path | str,
    query: str,
    *,
    limit: int,
    object_type: str | None = None,
    source_id: str | None = None,
    relationship_type: str | None = None,
) -> list[dict[str, object]]:
    context = load_project(project_path)
    index_path = context.root / "06_kb" / "chunks" / "reference_index.json"
    index = read_reference_index(context.root, index_path)
    query_text = query.casefold()
    matches = []
    for item in index.get("objects", []):
        if not isinstance(item, dict):
            continue
        if object_type is not None and str(item.get("type", "")).casefold() != object_type:
            continue
        if source_id is not None and _object_source_id(item) != source_id:
            continue
        if relationship_type is not None and not _has_relationship_type(
            item,
            relationship_type,
        ):
            continue
        haystack = _search_haystack(item)
        if query_text in haystack:
            matches.append(item)
        if len(matches) >= limit:
            break
    return matches


def read_reference_index(
    project_root: Path,
    index_path: Path | None = None,
) -> dict[str, object]:
    """Read the generated reference index or raise an actionable rebuild error."""

    if index_path is None:
        index_path = project_root / "06_kb" / "chunks" / "reference_index.json"
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(_reference_index_rebuild_message(project_root, "is missing")) from exc
    except json.JSONDecodeError as exc:
        raise ValueError(_reference_index_rebuild_message(project_root, "is invalid")) from exc
    if not _valid_reference_index_schema(
        index,
        project_root,
        validate_source_text=False,
    ):
        raise ValueError(_reference_index_rebuild_message(project_root, "has invalid schema"))
    if not _reference_index_is_stale(project_root, index_path) and not _valid_reference_index_schema(
        index,
        project_root,
    ):
        raise ValueError(_reference_index_rebuild_message(project_root, "has invalid schema"))
    return index


def _valid_reference_index_schema(
    index: object,
    project_root: Path | None = None,
    *,
    validate_source_text: bool = True,
) -> bool:
    if not isinstance(index, dict) or index.get("schema_version") != 1:
        return False
    objects = index.get("objects")
    chunks = index.get("chunks")
    if not isinstance(objects, list) or not isinstance(chunks, list):
        return False
    if not all(isinstance(item, dict) for item in objects) or not all(
        isinstance(item, dict) for item in chunks
    ):
        return False
    if project_root is None:
        return True
    return _valid_reference_index_provenance(
        project_root,
        objects,
        chunks,
        validate_source_text=validate_source_text,
    )


def _valid_reference_index_provenance(
    project_root: Path,
    objects: list[object],
    chunks: list[object],
    *,
    validate_source_text: bool = True,
) -> bool:
    object_records: dict[str, tuple[str, int, str]] = {}
    for item in objects:
        if not isinstance(item, dict):
            return False
        object_id = item.get("id")
        if not isinstance(object_id, str) or not object_id.strip():
            return False
        if object_id in object_records:
            return False
        source = item.get("source")
        if not isinstance(source, dict):
            return False
        source_path = source.get("path")
        source_line = source.get("line")
        statement = item.get("statement")
        if not isinstance(source_path, str) or not _valid_curated_source_location(
            project_root,
            source_path,
            source_line,
        ):
            return False
        if not isinstance(source_line, int) or isinstance(source_line, bool):
            return False
        if not isinstance(statement, str):
            return False
        if validate_source_text:
            if not _valid_curated_source_statement(
                project_root,
                source_path,
                source_line,
                statement,
            ):
                return False
        object_records[object_id] = (source_path, source_line, statement)
    for chunk in chunks:
        if not isinstance(chunk, dict):
            return False
        object_id = chunk.get("object_id")
        if not isinstance(object_id, str) or object_id not in object_records:
            return False
        chunk_text = chunk.get("text")
        if not isinstance(chunk_text, str):
            return False
        metadata = chunk.get("metadata")
        if not isinstance(metadata, dict):
            return False
        metadata_object_id = metadata.get("object_id")
        if metadata_object_id != object_id:
            return False
        source = metadata.get("source")
        if not isinstance(source, dict):
            return False
        source_path = source.get("path")
        metadata_source_path = metadata.get("source_path")
        source_line = source.get("line")
        metadata_source_line = metadata.get("source_line")
        object_source_path, object_source_line, object_statement = object_records[object_id]
        if not isinstance(source_path, str) or not _valid_curated_source_location(
            project_root,
            source_path,
            source_line,
        ):
            return False
        if (source_path, source_line) != (object_source_path, object_source_line):
            return False
        if not isinstance(metadata_source_path, str) or not _valid_curated_source_location(
            project_root,
            metadata_source_path,
            metadata_source_line,
        ):
            return False
        if (metadata_source_path, metadata_source_line) != (
            object_source_path,
            object_source_line,
        ):
            return False
        if _normalize_reference_text(chunk_text) != _normalize_reference_text(
            object_statement,
        ):
            return False
    return True


def _reference_index_is_stale(project_root: Path, index_path: Path) -> bool:
    curated_paths = sorted((project_root / "01_references" / "curated").glob("*.md"))
    if not curated_paths or not index_path.exists():
        return False
    index_mtime_ns = index_path.stat().st_mtime_ns
    artifact_status, artifact_mtime_ns = _reference_kb_artifacts_status(project_root)
    if artifact_status == "current":
        index_mtime_ns = min(index_mtime_ns, artifact_mtime_ns)
    return any(path.stat().st_mtime_ns > index_mtime_ns for path in curated_paths)


def _reference_kb_artifacts_status(project_root: Path) -> tuple[str, int]:
    mtimes: list[int] = []
    kb_dir = project_root / "06_kb"
    for filename, keys in REFERENCE_KB_ARTIFACTS:
        path = kb_dir / filename
        try:
            artifact = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return ("missing", 0)
        except json.JSONDecodeError:
            return ("invalid", 0)
        if not isinstance(artifact, dict):
            return ("invalid", 0)
        for key in keys:
            rows = artifact.get(key)
            if not isinstance(rows, list) or not all(
                isinstance(item, dict) for item in rows
            ):
                return ("invalid", 0)
        if filename == "chapter_index.json" and not _valid_chapter_index_artifact(
            project_root,
            artifact,
        ):
            return ("invalid", 0)
        mtimes.append(path.stat().st_mtime_ns)
    return ("current", min(mtimes) if mtimes else 0)


def _valid_chapter_index_artifact(project_root: Path, artifact: dict[str, object]) -> bool:
    chapters = artifact.get("chapters")
    if not isinstance(chapters, list):
        return False
    for chapter in chapters:
        if not isinstance(chapter, dict):
            return False
        if not _has_nonempty_string_fields(chapter, ("title",)):
            return False
        sections = chapter.get("sections")
        if not isinstance(sections, list) or not all(
            isinstance(section, dict) for section in sections
        ):
            return False
        for section in sections:
            if not _has_nonempty_string_fields(section, ("title", "source_path")):
                return False
            if not _valid_curated_source_file(project_root, str(section["source_path"])):
                return False
            objects = section.get("objects")
            if not isinstance(objects, list) or not all(
                isinstance(item, dict) for item in objects
            ):
                return False
            for item in objects:
                if not _has_nonempty_string_fields(
                    item,
                    ("id", "type", "title", "source_path"),
                ):
                    return False
                if not _valid_curated_source_file(project_root, str(item["source_path"])):
                    return False
    return True


def _has_nonempty_string_fields(item: dict[str, object], fields: tuple[str, ...]) -> bool:
    return all(isinstance(item.get(field), str) and item[field].strip() for field in fields)


def _valid_curated_source_file(project_root: Path, relative_path: str) -> bool:
    path = project_root / relative_path
    curated_dir = project_root / "01_references" / "curated"
    try:
        path.resolve().relative_to(project_root.resolve())
        path.resolve().relative_to(curated_dir.resolve())
    except ValueError:
        return False
    return path.is_file()


def _valid_curated_source_location(
    project_root: Path,
    relative_path: str,
    line: object,
) -> bool:
    if not _valid_curated_source_file(project_root, relative_path):
        return False
    if not isinstance(line, int) or isinstance(line, bool) or line < 1:
        return False
    path = project_root / relative_path
    try:
        line_count = len(path.read_text(encoding="utf-8").splitlines())
    except OSError:
        return False
    return line <= line_count


def _valid_curated_source_statement(
    project_root: Path,
    relative_path: str,
    line: int,
    statement: str,
) -> bool:
    normalized_statement = _normalize_reference_text(statement)
    if not normalized_statement:
        return False
    path = project_root / relative_path
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    if line > len(lines):
        return False
    source_block = "\n".join(_object_block_from_source_line(lines, line))
    return normalized_statement in _normalize_reference_text(source_block)


def _normalize_reference_text(value: str) -> str:
    return " ".join(value.split())


def _object_block_from_source_line(lines: list[str], line: int) -> list[str]:
    start = line - 1
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("### "):
            end = index
            break
    return lines[start:end]


def _reference_index_rebuild_message(project_root: Path, reason: str) -> str:
    return (
        f"Reference KB index {reason}; "
        f"run socrates kb build --project {project_root} to rebuild it."
    )


def _reference_chapter_index_rebuild_message(project_root: Path, reason: str) -> str:
    return (
        f"Reference KB chapter index {reason}; "
        f"run socrates kb build --project {project_root} to rebuild it."
    )


def _reference_concept_graph_rebuild_message(project_root: Path, reason: str) -> str:
    return (
        f"Reference KB concept graph {reason}; "
        f"run socrates kb build --project {project_root} to rebuild it."
    )


def _object_source_id(item: dict[str, object]) -> str:
    source = item.get("source", {})
    if not isinstance(source, dict):
        return ""
    return str(source.get("source_id", ""))


def _object_source_path(item: dict[str, object]) -> str:
    source = item.get("source", {})
    if not isinstance(source, dict):
        return ""
    return str(source.get("path", ""))


def _ingestion_quality_by_source_path(project_root: Path) -> dict[str, str]:
    manifest_path = project_root / "08_evals" / "ingestion_quality_manifest.json"
    if not manifest_path.exists():
        return {}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    references = manifest.get("curated_references", []) if isinstance(manifest, dict) else []
    if not isinstance(references, list):
        return {}

    quality_by_path: dict[str, str] = {}
    for item in references:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "")).strip()
        quality_status = str(item.get("quality_status", "")).strip()
        if path and quality_status:
            quality_by_path[path] = quality_status
    return quality_by_path


def _has_relationship_type(item: dict[str, object], relationship_type: str) -> bool:
    relationships = item.get("relationships", [])
    if not isinstance(relationships, list):
        return False
    return any(
        isinstance(relationship, dict)
        and str(relationship.get("relationship", "")) == relationship_type
        for relationship in relationships
    )


def _search_haystack(item: dict[str, object]) -> str:
    source = item.get("source", {})
    source_terms: list[str] = []
    if isinstance(source, dict):
        source_terms.extend(str(value) for value in source.values() if value)
        page = str(source.get("page", "")).strip()
        if page:
            source_terms.append(f"p{page}")
    relationship_terms: list[str] = []
    relationships = item.get("relationships", [])
    if isinstance(relationships, list):
        for relationship in relationships:
            if not isinstance(relationship, dict):
                continue
            relationship_terms.extend(
                str(value)
                for key in ("relationship", "target")
                if (value := relationship.get(key))
            )
    return " ".join(
        [
            str(item.get("number", "")),
            str(item.get("title", "")),
            str(item.get("statement", "")),
            " ".join(str(dep) for dep in item.get("dependencies", [])),
            " ".join(source_terms),
            " ".join(relationship_terms),
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
        statement, dependencies, page, relationships = _split_statement_and_metadata(body)
        current["statement"] = statement
        current["dependencies"] = dependencies
        if relationships:
            current["relationships"] = relationships
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


def _split_statement_and_metadata(
    lines: list[str],
) -> tuple[str, list[str], str | None, list[dict[str, str]]]:
    statement_lines: list[str] = []
    dependencies: list[str] = []
    page: str | None = None
    relationships: list[dict[str, str]] = []
    for line in lines:
        stripped = line.strip()
        key = _metadata_key(stripped)
        if key == "depends":
            dependencies.extend(
                item.strip()
                for item in stripped.split(":", 1)[1].split(",")
                if item.strip()
            )
        elif key == "page":
            page = _metadata_value(stripped)
        elif key in RELATIONSHIP_METADATA_KEYS:
            relationships.extend(
                {
                    "relationship": RELATIONSHIP_METADATA_KEYS[key],
                    "target": item,
                }
                for item in _metadata_list(stripped)
            )
        else:
            statement_lines.append(line)
    return "\n".join(statement_lines).strip(), dependencies, page, relationships


def _metadata_key(line: str) -> str:
    key, separator, _ = line.removeprefix("-").strip().partition(":")
    return key.strip().casefold() if separator else ""


def _metadata_value(line: str) -> str:
    _, _, value = line.removeprefix("-").strip().partition(":")
    return value.strip().strip('"')


def _metadata_list(line: str) -> list[str]:
    return [
        item.strip().strip('"')
        for item in _metadata_value(line).split(",")
        if item.strip()
    ]


def _chunk_from_object(item: dict[str, object]) -> dict[str, object]:
    metadata = {
        "object_id": item["id"],
        "type": item["type"],
        "title": item["title"],
        "source": item["source"],
        "dependencies": item.get("dependencies", []),
    }
    relationships = item.get("relationships", [])
    if isinstance(relationships, list) and relationships:
        metadata["relationships"] = relationships
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
        for relationship in _explicit_relationship_edges(item):
            target_id = relationship["target"]
            nodes.setdefault(
                target_id,
                {
                    "id": target_id,
                    "label": relationship["target_label"],
                    "type": "concept",
                },
            )
            edges.append(
                {
                    "source": object_id,
                    "target": target_id,
                    "relationship": relationship["relationship"],
                }
            )
    return {"nodes": list(nodes.values()), "edges": edges}


def _explicit_relationship_edges(item: dict[str, object]) -> list[dict[str, str]]:
    relationships = item.get("relationships", [])
    if not isinstance(relationships, list):
        return []
    edges: list[dict[str, str]] = []
    for relationship in relationships:
        if not isinstance(relationship, dict):
            continue
        relationship_type = str(relationship.get("relationship", "")).strip()
        target_label = str(relationship.get("target", "")).strip()
        if not relationship_type or not target_label:
            continue
        edges.append(
            {
                "relationship": relationship_type,
                "target": slugify_topic(target_label),
                "target_label": target_label,
            }
        )
    return edges


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
