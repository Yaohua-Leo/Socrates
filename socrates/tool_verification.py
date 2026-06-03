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


@dataclass(frozen=True)
class ToolVerificationSummary:
    """One persisted tool-verification record for CLI/report display."""

    kind: str
    object_id: str
    status: str
    title: str
    artifact_path: str
    report_path: str


@dataclass(frozen=True)
class ToolVerificationCheckResult:
    """Aggregate checklist result for persisted tool-verification records."""

    status: str
    checked: int
    passed: int
    failed: int
    report_path: Path
    manifest_path: Path


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


def list_tool_verification_records(
    project_path: Path | str,
    *,
    status: str = "all",
) -> list[ToolVerificationSummary]:
    """Return persisted tool-verification records from the project manifest."""

    allowed_statuses = {"all", "unchecked_skeleton", "verified", "failed"}
    if status not in allowed_statuses:
        allowed = ", ".join(sorted(allowed_statuses))
        raise ValueError(
            f"Unknown tool verification status {status!r}; expected one of: {allowed}"
        )

    context = load_project(project_path)
    manifest_path = context.evals_dir / "tool_verification" / "manifest.json"
    if not manifest_path.exists():
        return []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    records = manifest.get("records", []) if isinstance(manifest, dict) else []
    if not isinstance(records, list):
        return []

    summaries: list[ToolVerificationSummary] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        summary = _summary_from_record(record)
        if status == "all" or summary.status == status:
            summaries.append(summary)
    return sorted(summaries, key=lambda item: (item.kind, item.object_id))


def check_tool_verification_records(project_path: Path | str) -> ToolVerificationCheckResult:
    """Write an aggregate checklist report for tool-verification artifacts.

    This validates provenance files already written under ``08_evals``. It does
    not invoke Lean, SymPy, GAP, SageMath, or any other external verifier.
    """

    context = load_project(project_path)
    source_manifest_path = context.evals_dir / "tool_verification" / "manifest.json"
    report_path = context.evals_dir / "tool_verification_eval.md"
    manifest_path = context.evals_dir / "tool_verification_quality_manifest.json"
    records, manifest_issues = _checked_tool_records(context.root, source_manifest_path)
    passed = sum(1 for record in records if record["quality_status"] == "pass")
    failed = sum(1 for record in records if record["quality_status"] == "fail")
    checked = len(records)
    if manifest_issues:
        failed += len(manifest_issues)
    status = "pass" if failed == 0 and checked > 0 else "fail"
    manifest = _tool_quality_manifest(
        context.root,
        status=status,
        checked=checked,
        passed=passed,
        failed=failed,
        records=records,
        issues=manifest_issues,
        source_manifest_path=source_manifest_path,
    )
    write_text(
        report_path,
        _tool_quality_report(
            context.root,
            manifest,
            source_manifest_path=source_manifest_path,
        ),
    )
    write_json(manifest_path, manifest)
    append_project_log(context, "Checked tool-verification records.")
    return ToolVerificationCheckResult(
        status=status,
        checked=checked,
        passed=passed,
        failed=failed,
        report_path=report_path,
        manifest_path=manifest_path,
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


def _summary_from_record(record: dict[str, object]) -> ToolVerificationSummary:
    return ToolVerificationSummary(
        kind=str(record.get("kind", "")),
        object_id=str(record.get("object_id", "")),
        status=str(record.get("status", "unknown")),
        title=str(record.get("title", "")),
        artifact_path=str(
            record.get("skeleton_path")
            or record.get("artifact_path")
            or record.get("output_path")
            or ""
        ),
        report_path=str(record.get("report_path", "")),
    )


def _checked_tool_records(
    project_root: Path,
    manifest_path: Path,
) -> tuple[list[dict[str, object]], list[str]]:
    if not manifest_path.exists():
        return ([], ["missing tool-verification manifest"])
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ([], ["invalid tool-verification manifest JSON"])
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        return ([], ["invalid tool-verification manifest schema"])
    records = manifest.get("records")
    if not isinstance(records, list):
        return ([], ["tool-verification manifest records must be a list"])
    if not records:
        return ([], ["no tool-verification records"])
    return (
        [
            _checked_tool_record(project_root, record, index=index)
            for index, record in enumerate(records, start=1)
        ],
        [],
    )


def _checked_tool_record(
    project_root: Path,
    record: object,
    *,
    index: int,
) -> dict[str, object]:
    if not isinstance(record, dict):
        return {
            "object_id": f"record_{index}",
            "kind": "",
            "record_status": "",
            "quality_status": "fail",
            "artifact_path": "",
            "report_path": "",
            "issues": ["tool-verification record must be an object"],
        }

    issues: list[str] = []
    for key in ("kind", "object_id", "status", "report_path"):
        if not isinstance(record.get(key), str) or not str(record.get(key)).strip():
            issues.append(f"missing {key}")
    artifact_path = _record_artifact_path(record)
    artifact_issue = _artifact_issue(project_root, artifact_path, label="artifact")
    if artifact_issue:
        issues.append(artifact_issue)
    report_issue = _artifact_issue(project_root, record.get("report_path"), label="report")
    if report_issue:
        issues.append(report_issue)
    return {
        "object_id": str(record.get("object_id") or f"record_{index}"),
        "kind": str(record.get("kind") or ""),
        "record_status": str(record.get("status") or ""),
        "quality_status": "fail" if issues else "pass",
        "artifact_path": artifact_path if isinstance(artifact_path, str) else "",
        "report_path": str(record.get("report_path") or ""),
        "issues": issues,
    }


def _record_artifact_path(record: dict[object, object]) -> object:
    return (
        record.get("skeleton_path")
        or record.get("artifact_path")
        or record.get("output_path")
    )


def _artifact_issue(project_root: Path, value: object, *, label: str) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return f"missing {label}"
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        return f"unsafe {label}: {value}"
    if not (project_root / path).exists():
        return f"missing {label}: {value}"
    return None


def _tool_quality_manifest(
    project_root: Path,
    *,
    status: str,
    checked: int,
    passed: int,
    failed: int,
    records: list[dict[str, object]],
    issues: list[str],
    source_manifest_path: Path,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "status": status,
        "checked": checked,
        "passed": passed,
        "failed": failed,
        "source_manifest": source_manifest_path.relative_to(project_root).as_posix(),
        "records": records,
        "issues": issues,
        "verification_boundary": {
            "external_verifier_invoked": False,
            "unchecked_skeleton_policy": "scaffold_only_not_proof",
        },
    }


def _tool_quality_report(
    project_root: Path,
    manifest: dict[str, object],
    *,
    source_manifest_path: Path,
) -> str:
    source_manifest = source_manifest_path.relative_to(project_root).as_posix()
    lines = [
        "# Tool Verification Eval",
        "",
        "## Summary",
        "",
        f"- Status: {manifest['status']}",
        f"- Records checked: {manifest['checked']}",
        f"- Passed: {manifest['passed']}",
        f"- Failed: {manifest['failed']}",
        f"- Source manifest: {source_manifest}",
        "",
    ]
    issues = manifest.get("issues", [])
    if isinstance(issues, list) and issues:
        lines.extend(["## Issues", ""])
        lines.extend(f"- {issue}" for issue in issues)
        lines.append("")

    lines.extend(["## Records", ""])
    records = manifest.get("records", [])
    if not isinstance(records, list) or not records:
        lines.append("- none")
    else:
        for record in records:
            if not isinstance(record, dict):
                continue
            lines.append(
                (
                    f"- {record.get('object_id', '')}: {record.get('quality_status', '')} | "
                    f"{record.get('record_status', '')} | {record.get('kind', '')}"
                )
            )
            lines.append(f"  - artifact: {record.get('artifact_path', '')}")
            lines.append(f"  - report: {record.get('report_path', '')}")
            record_issues = record.get("issues", [])
            if isinstance(record_issues, list) and record_issues:
                lines.append(f"  - issues: {', '.join(str(issue) for issue in record_issues)}")
            else:
                lines.append("  - issues: none")
    lines.extend(
        [
            "",
            "## Verification Boundary",
            "",
            "- This check validates persisted tool-verification artifacts only.",
            "- `unchecked_skeleton` records are scaffolds, not verified proofs.",
            "- No external verifier executable was invoked.",
            "",
        ]
    )
    return "\n".join(lines)


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
