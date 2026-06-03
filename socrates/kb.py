"""Reference knowledge-base construction and retrieval."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

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
    _write_ingestion_eval(context.evals_dir / "ingestion_eval.md", len(objects))

    return ReferenceKbBuildResult(
        index_path=index_path,
        object_count=len(objects),
        chunk_count=len(index["chunks"]),
    )


def search_reference_kb(project_path: Path | str, query: str, *, limit: int = 10) -> list[dict[str, object]]:
    """Return source-grounded reference objects matching a query."""

    context = load_project(project_path)
    index_path = context.root / "06_kb" / "chunks" / "reference_index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    query_text = query.casefold()
    matches = []
    for item in index.get("objects", []):
        haystack = " ".join(
            [
                str(item.get("title", "")),
                str(item.get("statement", "")),
                " ".join(str(dep) for dep in item.get("dependencies", [])),
            ]
        ).casefold()
        if query_text in haystack:
            matches.append(item)
        if len(matches) >= limit:
            break
    return matches


def _extract_objects(project_root: Path, markdown_path: Path) -> list[dict[str, object]]:
    lines = markdown_path.read_text(encoding="utf-8").splitlines()
    chapter = ""
    section = ""
    objects: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    body: list[str] = []

    def flush() -> None:
        nonlocal body, current
        if current is None:
            return
        statement, dependencies = _split_statement_and_dependencies(body)
        current["statement"] = statement
        current["dependencies"] = dependencies
        objects.append(current)
        body = []
        current = None

    for line_number, line in enumerate(lines, start=1):
        if line.startswith("### "):
            flush()
            parsed = _parse_object_heading(line.removeprefix("### ").strip())
            if parsed is None:
                current = None
                body = []
                continue
            object_type, title = parsed
            object_id = slugify_topic(title)
            current = {
                "id": object_id,
                "type": object_type,
                "title": title,
                "source": {
                    "path": markdown_path.relative_to(project_root).as_posix(),
                    "chapter": chapter,
                    "section": section,
                    "line": line_number,
                },
            }
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


def _parse_object_heading(heading: str) -> tuple[str, str] | None:
    label, separator, title = heading.partition(":")
    if not separator:
        return None
    object_type = label.strip().casefold()
    if object_type not in OBJECT_TYPES:
        return None
    return object_type, title.strip()


def _split_statement_and_dependencies(lines: list[str]) -> tuple[str, list[str]]:
    statement_lines: list[str] = []
    dependencies: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.casefold().startswith("depends:"):
            dependencies.extend(
                item.strip()
                for item in stripped.split(":", 1)[1].split(",")
                if item.strip()
            )
        else:
            statement_lines.append(line)
    return "\n".join(statement_lines).strip(), dependencies


def _chunk_from_object(item: dict[str, object]) -> dict[str, object]:
    return {
        "id": f"{item['id']}_chunk",
        "object_id": item["id"],
        "text": item.get("statement", ""),
        "metadata": {
            "type": item["type"],
            "title": item["title"],
            "source": item["source"],
            "dependencies": item.get("dependencies", []),
        },
    }


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


def _write_ingestion_eval(path: Path, object_count: int) -> None:
    write_text(
        path,
        "# Ingestion Eval\n\n"
        f"- Curated objects indexed: {object_count}\n"
        "- Raw references modified: no\n"
        "- Curated-only policy: enforced\n",
    )
