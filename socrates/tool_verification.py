"""Tool-verification artifact generation for Socrates projects."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re

from .context import append_project_log, load_project, write_json, write_text


@dataclass(frozen=True)
class LeanSkeletonResult:
    """Paths and status for a generated Lean statement skeleton."""

    skeleton_path: Path
    report_path: Path
    manifest_path: Path
    object_id: str
    status: str


def generate_lean_statement_skeleton(
    project_path: Path | str,
    *,
    object_id: str,
    namespace: str = "Socrates",
) -> LeanSkeletonResult:
    """Write an unchecked Lean statement skeleton for one reference-KB object."""

    context = load_project(project_path)
    item = _find_reference_object(context.root, object_id)
    lean_name = _lean_identifier(f"{object_id}_statement")
    lean_namespace = _lean_namespace(namespace)
    verification_dir = context.evals_dir / "tool_verification"
    skeleton_path = verification_dir / f"{lean_name}.lean"
    report_path = verification_dir / f"{lean_name}_report.md"
    manifest_path = verification_dir / "manifest.json"
    status = "unchecked_skeleton"

    write_text(
        skeleton_path,
        _lean_skeleton_text(
            item,
            lean_name=lean_name,
            namespace=lean_namespace,
            status=status,
        ),
    )
    write_text(
        report_path,
        _tool_verification_report(
            item,
            skeleton_path=skeleton_path.relative_to(context.root).as_posix(),
            status=status,
        ),
    )
    write_json(
        manifest_path,
        _updated_manifest(
            manifest_path,
            _manifest_record(
                context.root,
                item,
                skeleton_path=skeleton_path,
                report_path=report_path,
                status=status,
            ),
        ),
    )
    append_project_log(
        context,
        f"Generated Lean statement skeleton for reference object {object_id}.",
    )
    return LeanSkeletonResult(
        skeleton_path=skeleton_path,
        report_path=report_path,
        manifest_path=manifest_path,
        object_id=object_id,
        status=status,
    )


def _find_reference_object(project_root: Path, object_id: str) -> dict[str, object]:
    index_path = project_root / "06_kb" / "chunks" / "reference_index.json"
    if not index_path.exists():
        raise FileNotFoundError(f"Missing reference KB index: {index_path}")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    objects = index.get("objects", []) if isinstance(index, dict) else []
    if not isinstance(objects, list):
        raise ValueError(f"Reference KB index has invalid object list: {index_path}")
    for item in objects:
        if isinstance(item, dict) and str(item.get("id", "")) == object_id:
            return item
    raise ValueError(f"Reference KB object not found: {object_id}")


def _lean_skeleton_text(
    item: dict[str, object],
    *,
    lean_name: str,
    namespace: str,
    status: str,
) -> str:
    source = item.get("source", {})
    source_label = _source_label(source if isinstance(source, dict) else {})
    title = str(item.get("title", "Untitled"))
    object_type = str(item.get("type", "object"))
    object_id = str(item.get("id", lean_name))
    statement = str(item.get("statement", "")).strip()
    lines = [
        "/-!",
        "Socrates Lean statement skeleton.",
        "",
        f"Object: {object_id}",
        f"Title: {title}",
        f"Type: {object_type}",
        f"Status: {status}",
        f"Source: {source_label or 'unknown'}",
        "",
        "This scaffold is not a proof and has not been checked by Lean.",
        "-/",
        "",
        f"namespace {namespace}",
        "",
        "-- Source statement:",
        *_lean_comment_lines(statement or "No source statement indexed."),
        "",
        f"theorem {lean_name} : Prop := by",
        "  -- TODO: translate the source statement into typed Lean hypotheses and target.",
        "  sorry",
        "",
        f"end {namespace}",
        "",
    ]
    return "\n".join(lines)


def _tool_verification_report(
    item: dict[str, object],
    *,
    skeleton_path: str,
    status: str,
) -> str:
    source = item.get("source", {})
    source_label = _source_label(source if isinstance(source, dict) else {})
    statement = str(item.get("statement", "")).strip() or "No source statement indexed."
    lines = [
        "# Tool Verification: Lean Statement Skeleton",
        "",
        "## Summary",
        "",
        f"- Object: {item.get('id', '')}",
        f"- Title: {item.get('title', 'Untitled')}",
        f"- Type: {item.get('type', 'object')}",
        f"- Status: {status}",
        f"- Lean skeleton: {skeleton_path}",
        f"- Source: {source_label or 'unknown'}",
        "",
        "## Source Statement",
        "",
        statement,
        "",
        "## Verification Boundary",
        "",
        "- This is a deterministic translation scaffold only.",
        "- No Lean executable was invoked.",
        "- The statement still needs a human or tool-backed formalization pass.",
        "",
    ]
    return "\n".join(lines)


def _updated_manifest(path: Path, record: dict[str, object]) -> dict[str, object]:
    records: list[object] = []
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
        if isinstance(existing, dict) and isinstance(existing.get("records"), list):
            records = existing["records"]
    records = [
        existing
        for existing in records
        if not (
            isinstance(existing, dict)
            and existing.get("kind") == record["kind"]
            and existing.get("object_id") == record["object_id"]
        )
    ]
    records.append(record)
    return {"schema_version": 1, "records": records}


def _manifest_record(
    project_root: Path,
    item: dict[str, object],
    *,
    skeleton_path: Path,
    report_path: Path,
    status: str,
) -> dict[str, object]:
    source = item.get("source", {})
    return {
        "kind": "lean_statement_skeleton",
        "object_id": str(item.get("id", "")),
        "object_type": str(item.get("type", "")),
        "title": str(item.get("title", "")),
        "status": status,
        "skeleton_path": skeleton_path.relative_to(project_root).as_posix(),
        "report_path": report_path.relative_to(project_root).as_posix(),
        "source": source if isinstance(source, dict) else {},
    }


def _lean_identifier(value: str) -> str:
    identifier = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")
    if not identifier:
        return "socrates_statement"
    if not (identifier[0].isalpha() or identifier[0] == "_"):
        return f"socrates_{identifier}"
    return identifier


def _lean_namespace(value: str) -> str:
    parts = [
        _lean_identifier(part)
        for part in re.split(r"[^A-Za-z0-9_]+", value)
        if part.strip()
    ]
    return ".".join(parts) if parts else "Socrates"


def _lean_comment_lines(text: str) -> list[str]:
    return [f"-- {line}" if line.strip() else "--" for line in text.splitlines()]


def _source_label(source: dict[object, object]) -> str:
    path = str(source.get("path", "")).strip()
    line = source.get("line")
    page = str(source.get("page", "")).strip()
    location = path
    if page:
        location = f"{location}:p{page}" if location else f"p{page}"
    if line:
        location = f"{location}:{line}" if location else f"line {line}"
    return location
