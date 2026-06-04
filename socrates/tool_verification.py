"""Tool-verification artifact generation for Socrates projects."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import re
import shutil
import subprocess

from .context import append_project_log, load_project, write_json, write_text
from .kb import read_reference_index, reference_kb_status
from .project import slugify_topic


@dataclass(frozen=True)
class LeanSkeletonResult:
    """Paths and status for a generated Lean statement skeleton."""

    skeleton_path: Path
    report_path: Path
    manifest_path: Path
    object_id: str
    status: str


@dataclass(frozen=True)
class LeanCheckResult:
    """Persisted result for one optional Lean frontend check."""

    status: str
    checked: bool
    artifact_path: Path
    report_path: Path
    manifest_path: Path
    object_id: str


@dataclass(frozen=True)
class LeanDependencyMapResult:
    """Persisted result for one Lean-oriented dependency map."""

    status: str
    dependency_count: int
    resolved_count: int
    artifact_path: Path
    report_path: Path
    manifest_path: Path
    object_id: str


@dataclass(frozen=True)
class ToolVerificationSummary:
    """One persisted tool-verification record for CLI/report display."""

    kind: str
    object_id: str
    status: str
    title: str
    artifact_path: str
    report_path: str
    reference_kb_status: str = ""


@dataclass(frozen=True)
class ToolVerificationCheckResult:
    """Aggregate checklist result for persisted tool-verification records."""

    status: str
    checked: int
    passed: int
    failed: int
    report_path: Path
    manifest_path: Path


@dataclass(frozen=True)
class ToolInventoryResult:
    """Persisted availability inventory for optional mathematics tools."""

    status: str
    tools_checked: int
    available: int
    report_path: Path
    manifest_path: Path
    registry_manifest_path: Path


@dataclass(frozen=True)
class SympyIdentityResult:
    """Persisted result for one optional SymPy identity check."""

    status: str
    passed: bool
    artifact_path: Path
    report_path: Path
    manifest_path: Path
    object_id: str


@dataclass(frozen=True)
class SympyCounterexampleResult:
    """Persisted result for one optional SymPy counterexample search."""

    status: str
    counterexample_found: bool
    artifact_path: Path
    report_path: Path
    manifest_path: Path
    object_id: str


@dataclass(frozen=True)
class GapGroupOrderResult:
    """Persisted result for one optional GAP group order check."""

    status: str
    passed: bool
    artifact_path: Path
    report_path: Path
    manifest_path: Path
    object_id: str


@dataclass(frozen=True)
class SageGroupOrderResult:
    """Persisted result for one optional SageMath group order check."""

    status: str
    passed: bool
    artifact_path: Path
    report_path: Path
    manifest_path: Path
    object_id: str


def generate_lean_statement_skeleton(
    project_path: Path | str,
    *,
    object_id: str,
    namespace: str = "Socrates",
) -> LeanSkeletonResult:
    """Write an unchecked Lean statement skeleton for one reference-KB object."""

    context = load_project(project_path)
    kb_status = reference_kb_status(context.root)
    item = _find_reference_object(context.root, object_id)
    lean_name = _lean_identifier(f"{object_id}_statement")
    lean_namespace = _lean_namespace(namespace)
    verification_dir = context.evals_dir / "tool_verification"
    skeleton_path = verification_dir / f"{lean_name}.lean"
    report_path = verification_dir / f"{lean_name}_report.md"
    manifest_path = verification_dir / "manifest.json"
    status = _lean_skeleton_status(kb_status.status)

    write_text(
        skeleton_path,
        _lean_skeleton_text(
            item,
            lean_name=lean_name,
            namespace=lean_namespace,
            reference_kb_status=kb_status.status,
            status=status,
        ),
    )
    write_text(
        report_path,
        _tool_verification_report(
            item,
            skeleton_path=skeleton_path.relative_to(context.root).as_posix(),
            reference_kb_status=kb_status.status,
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
                reference_kb_status=kb_status.status,
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


def check_lean_file(
    project_path: Path | str,
    *,
    lean_file: Path | str,
    object_id: str | None = None,
    title: str | None = None,
    timeout_seconds: int = 10,
) -> LeanCheckResult:
    """Run an optional Lean frontend check for one project-local Lean file."""

    context = load_project(project_path)
    checked_path = _resolve_project_file(context.root, lean_file)
    check_id = object_id or checked_path.stem
    safe_id = _lean_identifier(f"{check_id}_lean_check")
    verification_dir = context.evals_dir / "tool_verification"
    artifact_path = verification_dir / f"{safe_id}.json"
    report_path = verification_dir / f"{safe_id}_report.md"
    manifest_path = verification_dir / "manifest.json"
    artifact = _lean_check_artifact(
        context.root,
        checked_path=checked_path,
        object_id=check_id,
        title=title,
        timeout_seconds=timeout_seconds,
    )
    write_text(
        report_path,
        _lean_check_report(
            artifact,
            artifact_path=artifact_path.relative_to(context.root).as_posix(),
        ),
    )
    write_json(artifact_path, artifact)
    write_json(
        manifest_path,
        _updated_manifest(
            manifest_path,
            _lean_check_record(
                context.root,
                object_id=check_id,
                title=title or check_id,
                artifact_path=artifact_path,
                report_path=report_path,
                status=str(artifact["status"]),
            ),
        ),
    )
    append_project_log(context, f"Recorded Lean frontend check for {check_id}.")
    return LeanCheckResult(
        status=str(artifact["status"]),
        checked=bool(artifact["checked"]),
        artifact_path=artifact_path,
        report_path=report_path,
        manifest_path=manifest_path,
        object_id=check_id,
    )


def map_lean_dependencies(
    project_path: Path | str,
    *,
    object_id: str,
) -> LeanDependencyMapResult:
    """Persist a Lean-oriented dependency map for one reference-KB object."""

    context = load_project(project_path)
    kb_status = reference_kb_status(context.root)
    item = _find_reference_object(context.root, object_id)
    verification_dir = context.evals_dir / "tool_verification"
    safe_id = _lean_identifier(f"{object_id}_lean_dependencies")
    artifact_path = verification_dir / f"{safe_id}.json"
    report_path = verification_dir / f"{safe_id}_report.md"
    manifest_path = verification_dir / "manifest.json"
    artifact = _lean_dependency_map_artifact(
        context.root,
        item,
        reference_kb_status=kb_status.status,
    )
    write_json(artifact_path, artifact)
    write_text(
        report_path,
        _lean_dependency_map_report(
            artifact,
            artifact_path=artifact_path.relative_to(context.root).as_posix(),
        ),
    )
    write_json(
        manifest_path,
        _updated_manifest(
            manifest_path,
            _lean_dependency_map_record(
                context.root,
                item,
                artifact_path=artifact_path,
                report_path=report_path,
                status=str(artifact["status"]),
                reference_kb_status=kb_status.status,
            ),
        ),
    )
    append_project_log(context, f"Recorded Lean dependency map for {object_id}.")
    return LeanDependencyMapResult(
        status=str(artifact["status"]),
        dependency_count=int(artifact["dependency_count"]),
        resolved_count=int(artifact["resolved_count"]),
        artifact_path=artifact_path,
        report_path=report_path,
        manifest_path=manifest_path,
        object_id=object_id,
    )


def list_tool_verification_records(
    project_path: Path | str,
    *,
    status: str = "all",
) -> list[ToolVerificationSummary]:
    """Return persisted tool-verification records from the project manifest."""

    allowed_statuses = {
        "all",
        "available",
        "counterexample_found",
        "failed",
        "lean_checked",
        "mapped",
        "no_counterexample_found",
        "partial",
        "stale_reference_kb",
        "unchecked_skeleton",
        "unavailable",
        "verified",
    }
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


def write_tool_inventory(project_path: Path | str) -> ToolInventoryResult:
    """Write a local availability inventory for optional math tools.

    The inventory is deliberately non-invasive: it checks command discovery and
    Python module specs only. It does not execute Lean, SageMath, GAP, SymPy, or
    other tool backends.
    """

    context = load_project(project_path)
    verification_dir = context.evals_dir / "tool_verification"
    report_path = verification_dir / "tool_inventory_report.md"
    manifest_path = verification_dir / "tool_inventory_manifest.json"
    registry_manifest_path = verification_dir / "manifest.json"
    tools = _tool_inventory_rows()
    tools_checked = len(tools)
    available = sum(1 for tool in tools if tool["status"] == "available")
    status = _inventory_status(available=available, total=tools_checked)
    manifest = {
        "schema_version": 1,
        "status": status,
        "tools_checked": tools_checked,
        "available": available,
        "missing": tools_checked - available,
        "external_verifier_invoked": False,
        "tools": tools,
    }
    write_text(report_path, _tool_inventory_report(manifest))
    write_json(manifest_path, manifest)
    write_json(
        registry_manifest_path,
        _updated_manifest(
            registry_manifest_path,
            _tool_inventory_record(
                context.root,
                report_path=report_path,
                manifest_path=manifest_path,
                status=status,
            ),
        ),
    )
    append_project_log(context, "Recorded local tool inventory.")
    return ToolInventoryResult(
        status=status,
        tools_checked=tools_checked,
        available=available,
        report_path=report_path,
        manifest_path=manifest_path,
        registry_manifest_path=registry_manifest_path,
    )


def verify_sympy_identity(
    project_path: Path | str,
    *,
    object_id: str,
    lhs: str,
    rhs: str,
    title: str | None = None,
) -> SympyIdentityResult:
    """Run an optional SymPy identity check and persist the result."""

    context = load_project(project_path)
    verification_dir = context.evals_dir / "tool_verification"
    safe_id = _lean_identifier(f"{object_id}_sympy_identity")
    artifact_path = verification_dir / f"{safe_id}.json"
    report_path = verification_dir / f"{safe_id}_report.md"
    manifest_path = verification_dir / "manifest.json"
    artifact = _sympy_identity_artifact(
        object_id=object_id,
        lhs=lhs,
        rhs=rhs,
        title=title,
    )
    write_json(artifact_path, artifact)
    write_text(
        report_path,
        _sympy_identity_report(
            artifact,
            artifact_path=artifact_path.relative_to(context.root).as_posix(),
        ),
    )
    write_json(
        manifest_path,
        _updated_manifest(
            manifest_path,
            _sympy_identity_record(
                context.root,
                object_id=object_id,
                title=title or object_id,
                artifact_path=artifact_path,
                report_path=report_path,
                status=str(artifact["status"]),
            ),
        ),
    )
    append_project_log(context, f"Recorded SymPy identity check for {object_id}.")
    return SympyIdentityResult(
        status=str(artifact["status"]),
        passed=bool(artifact["passed"]),
        artifact_path=artifact_path,
        report_path=report_path,
        manifest_path=manifest_path,
        object_id=object_id,
    )


def search_sympy_counterexample(
    project_path: Path | str,
    *,
    object_id: str,
    lhs: str,
    rhs: str,
    samples: tuple[int, ...] = (-2, -1, 0, 1, 2),
    title: str | None = None,
) -> SympyCounterexampleResult:
    """Use optional SymPy to search finite integer samples for a counterexample."""

    context = load_project(project_path)
    verification_dir = context.evals_dir / "tool_verification"
    safe_id = _lean_identifier(f"{object_id}_sympy_counterexample")
    artifact_path = verification_dir / f"{safe_id}.json"
    report_path = verification_dir / f"{safe_id}_report.md"
    manifest_path = verification_dir / "manifest.json"
    artifact = _sympy_counterexample_artifact(
        object_id=object_id,
        lhs=lhs,
        rhs=rhs,
        samples=samples,
        title=title,
    )
    write_json(artifact_path, artifact)
    write_text(
        report_path,
        _sympy_counterexample_report(
            artifact,
            artifact_path=artifact_path.relative_to(context.root).as_posix(),
        ),
    )
    write_json(
        manifest_path,
        _updated_manifest(
            manifest_path,
            _sympy_counterexample_record(
                context.root,
                object_id=object_id,
                title=title or object_id,
                artifact_path=artifact_path,
                report_path=report_path,
                status=str(artifact["status"]),
            ),
        ),
    )
    append_project_log(context, f"Recorded SymPy counterexample search for {object_id}.")
    return SympyCounterexampleResult(
        status=str(artifact["status"]),
        counterexample_found=bool(artifact["counterexample_found"]),
        artifact_path=artifact_path,
        report_path=report_path,
        manifest_path=manifest_path,
        object_id=object_id,
    )


def verify_gap_group_order(
    project_path: Path | str,
    *,
    object_id: str,
    group_expression: str,
    expected_order: int,
    title: str | None = None,
    timeout_seconds: int = 10,
) -> GapGroupOrderResult:
    """Use optional GAP to check the order of one finite group expression."""

    context = load_project(project_path)
    verification_dir = context.evals_dir / "tool_verification"
    safe_id = _lean_identifier(f"{object_id}_gap_order")
    artifact_path = verification_dir / f"{safe_id}.json"
    report_path = verification_dir / f"{safe_id}_report.md"
    manifest_path = verification_dir / "manifest.json"
    artifact = _gap_group_order_artifact(
        object_id=object_id,
        group_expression=group_expression,
        expected_order=expected_order,
        title=title,
        timeout_seconds=timeout_seconds,
    )
    write_json(artifact_path, artifact)
    write_text(
        report_path,
        _gap_group_order_report(
            artifact,
            artifact_path=artifact_path.relative_to(context.root).as_posix(),
        ),
    )
    write_json(
        manifest_path,
        _updated_manifest(
            manifest_path,
            _gap_group_order_record(
                context.root,
                object_id=object_id,
                title=title or object_id,
                artifact_path=artifact_path,
                report_path=report_path,
                status=str(artifact["status"]),
            ),
        ),
    )
    append_project_log(context, f"Recorded GAP group order check for {object_id}.")
    return GapGroupOrderResult(
        status=str(artifact["status"]),
        passed=bool(artifact["passed"]),
        artifact_path=artifact_path,
        report_path=report_path,
        manifest_path=manifest_path,
        object_id=object_id,
    )


def verify_sage_group_order(
    project_path: Path | str,
    *,
    object_id: str,
    group_expression: str,
    expected_order: int,
    title: str | None = None,
    timeout_seconds: int = 30,
) -> SageGroupOrderResult:
    """Use optional SageMath to check the order of one finite group expression."""

    context = load_project(project_path)
    verification_dir = context.evals_dir / "tool_verification"
    safe_id = _lean_identifier(f"{object_id}_sage_order")
    artifact_path = verification_dir / f"{safe_id}.json"
    report_path = verification_dir / f"{safe_id}_report.md"
    manifest_path = verification_dir / "manifest.json"
    artifact = _sage_group_order_artifact(
        object_id=object_id,
        group_expression=group_expression,
        expected_order=expected_order,
        title=title,
        timeout_seconds=timeout_seconds,
    )
    write_json(artifact_path, artifact)
    write_text(
        report_path,
        _sage_group_order_report(
            artifact,
            artifact_path=artifact_path.relative_to(context.root).as_posix(),
        ),
    )
    write_json(
        manifest_path,
        _updated_manifest(
            manifest_path,
            _sage_group_order_record(
                context.root,
                object_id=object_id,
                title=title or object_id,
                artifact_path=artifact_path,
                report_path=report_path,
                status=str(artifact["status"]),
            ),
        ),
    )
    append_project_log(context, f"Recorded Sage group order check for {object_id}.")
    return SageGroupOrderResult(
        status=str(artifact["status"]),
        passed=bool(artifact["passed"]),
        artifact_path=artifact_path,
        report_path=report_path,
        manifest_path=manifest_path,
        object_id=object_id,
    )


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
    index = read_reference_index(project_root)
    objects = index.get("objects", []) if isinstance(index, dict) else []
    if not isinstance(objects, list):
        raise ValueError(
            f"Reference KB index has invalid object list; "
            f"run socrates kb build --project {project_root} to rebuild it."
        )
    for item in objects:
        if isinstance(item, dict) and str(item.get("id", "")) == object_id:
            return item
    raise ValueError(f"Reference KB object not found: {object_id}")


def _lean_dependency_map_artifact(
    project_root: Path,
    item: dict[str, object],
    *,
    reference_kb_status: str,
) -> dict[str, object]:
    dependencies = [
        str(dependency).strip()
        for dependency in item.get("dependencies", [])
        if str(dependency).strip()
    ]
    dependency_rows = _lean_dependency_rows(project_root, dependencies)
    resolved_count = sum(1 for row in dependency_rows if row["status"] == "resolved")
    mapping_status = "mapped" if resolved_count == len(dependencies) else "partial"
    status = (
        "stale_reference_kb"
        if reference_kb_status == "stale"
        else mapping_status
    )
    issues = [
        f"Unresolved dependency: {row['label']}"
        for row in dependency_rows
        if row["status"] != "resolved"
    ]
    return {
        "schema_version": 1,
        "kind": "lean_dependency_map",
        "object_id": str(item.get("id", "")),
        "title": str(item.get("title", "")),
        "object_type": str(item.get("type", "")),
        "status": status,
        "mapping_status": mapping_status,
        "reference_kb_status": reference_kb_status,
        "dependency_count": len(dependencies),
        "resolved_count": resolved_count,
        "dependencies": dependency_rows,
        "issues": issues,
        "external_executable_invoked": False,
        "verification_boundary": {
            "scope": "reference_kb_dependency_mapping",
            "proof_status": "not_a_proof",
            "lean_invoked": False,
        },
    }


def _lean_dependency_rows(
    project_root: Path,
    dependencies: list[str],
) -> list[dict[str, object]]:
    lookup = _reference_object_lookup(project_root)
    rows: list[dict[str, object]] = []
    for label in dependencies:
        dependency_id = slugify_topic(label)
        matched = lookup.get(dependency_id)
        if matched is None:
            rows.append(
                {
                    "label": label,
                    "dependency_id": dependency_id,
                    "status": "unresolved",
                    "relationship": "prerequisite",
                    "lean_identifier": _lean_identifier(dependency_id),
                }
            )
            continue
        source = matched.get("source", {})
        rows.append(
            {
                "label": label,
                "dependency_id": dependency_id,
                "status": "resolved",
                "relationship": "prerequisite",
                "resolved_object_id": str(matched.get("id", "")),
                "resolved_object_type": str(matched.get("type", "")),
                "resolved_title": str(matched.get("title", "")),
                "lean_identifier": _lean_identifier(str(matched.get("id", dependency_id))),
                "source": source if isinstance(source, dict) else {},
            }
        )
    return rows


def _reference_object_lookup(project_root: Path) -> dict[str, dict[str, object]]:
    index = read_reference_index(project_root)
    objects = index.get("objects", []) if isinstance(index, dict) else []
    lookup: dict[str, dict[str, object]] = {}
    if not isinstance(objects, list):
        return lookup
    for item in objects:
        if not isinstance(item, dict):
            continue
        object_id = str(item.get("id", "")).strip()
        title = str(item.get("title", "")).strip()
        if object_id:
            lookup.setdefault(object_id, item)
        if title:
            lookup.setdefault(slugify_topic(title), item)
    return lookup


def _lean_dependency_map_report(
    artifact: dict[str, object],
    *,
    artifact_path: str,
) -> str:
    lines = [
        "# Tool Verification: Lean Dependency Map",
        "",
        "## Summary",
        "",
        f"- Object: {artifact.get('object_id', '')}",
        f"- Title: {artifact.get('title', '')}",
        f"- Type: {artifact.get('object_type', '')}",
        f"- Status: {artifact.get('status', '')}",
        f"- Reference KB status: {artifact.get('reference_kb_status', 'unknown')}",
        f"- Dependencies: {artifact.get('dependency_count', 0)}",
        f"- Resolved: {artifact.get('resolved_count', 0)}",
        f"- Artifact: {artifact_path}",
        "- External executable invoked: false",
        "",
        "## Dependencies",
        "",
    ]
    dependencies = artifact.get("dependencies", [])
    if isinstance(dependencies, list) and dependencies:
        for row in dependencies:
            if not isinstance(row, dict):
                continue
            lines.append(
                (
                    f"- {row.get('label', '')} | {row.get('status', '')} | "
                    f"{row.get('dependency_id', '')}"
                )
            )
            if row.get("resolved_object_id"):
                lines.append(f"  - resolved_object_id: {row.get('resolved_object_id', '')}")
                lines.append(f"  - resolved_title: {row.get('resolved_title', '')}")
            lines.append(f"  - lean_identifier: {row.get('lean_identifier', '')}")
    else:
        lines.append("- none")
    issues = artifact.get("issues", [])
    lines.extend(["", "## Issues", ""])
    if isinstance(issues, list) and issues:
        lines.extend(f"- {issue}" for issue in issues)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Verification Boundary",
            "",
            "- This map links Reference KB dependencies to Lean formalization targets.",
            "- It does not prove the statement or any prerequisite.",
            "- No Lean executable was invoked.",
            "",
        ]
    )
    return "\n".join(lines)


def _lean_dependency_map_record(
    project_root: Path,
    item: dict[str, object],
    *,
    artifact_path: Path,
    report_path: Path,
    status: str,
    reference_kb_status: str,
) -> dict[str, object]:
    source = item.get("source", {})
    return {
        "kind": "lean_dependency_map",
        "object_id": str(item.get("id", "")),
        "object_type": str(item.get("type", "")),
        "title": str(item.get("title", "")),
        "status": status,
        "reference_kb_status": reference_kb_status,
        "artifact_path": artifact_path.relative_to(project_root).as_posix(),
        "report_path": report_path.relative_to(project_root).as_posix(),
        "source": source if isinstance(source, dict) else {},
    }


def _resolve_project_file(project_root: Path, value: Path | str) -> Path:
    path = Path(value).expanduser()
    resolved = path.resolve() if path.is_absolute() else (project_root / path).resolve()
    try:
        resolved.relative_to(project_root)
    except ValueError as exc:
        raise ValueError(f"file must be inside the Socrates project: {value}") from exc
    return resolved


def _lean_check_artifact(
    project_root: Path,
    *,
    checked_path: Path,
    object_id: str,
    title: str | None,
    timeout_seconds: int,
) -> dict[str, object]:
    relative_checked_path = checked_path.relative_to(project_root).as_posix()
    artifact: dict[str, object] = {
        "schema_version": 1,
        "kind": "lean_frontend_check",
        "object_id": object_id,
        "title": title or object_id,
        "tool": "lean",
        "status": "failed",
        "checked": False,
        "input": {
            "lean_file": relative_checked_path,
            "timeout_seconds": timeout_seconds,
        },
        "output": {},
        "issues": [],
        "external_executable_invoked": False,
        "accepts_sorry": True,
    }
    if not checked_path.exists():
        artifact["issues"] = [f"Lean file does not exist: {relative_checked_path}"]
        return artifact
    lean_executable = shutil.which("lean")
    if not lean_executable:
        artifact["status"] = "unavailable"
        artifact["issues"] = ["Lean executable is not available on PATH."]
        return artifact

    command = [lean_executable, str(checked_path)]
    artifact["external_executable_invoked"] = True
    artifact["output"] = {"command": command}
    try:
        completed = subprocess.run(
            command,
            cwd=project_root,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        artifact["status"] = "failed"
        artifact["issues"] = [f"Lean check timed out after {timeout_seconds} seconds."]
        artifact["output"] = {
            "command": command,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
        }
        return artifact

    artifact["output"] = {
        "command": command,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    if completed.returncode == 0:
        artifact["status"] = "lean_checked"
        artifact["checked"] = True
    else:
        artifact["status"] = "failed"
        artifact["issues"] = [f"Lean exited with code {completed.returncode}."]
    return artifact


def _lean_check_report(
    artifact: dict[str, object],
    *,
    artifact_path: str,
) -> str:
    input_data = artifact.get("input", {})
    output_data = artifact.get("output", {})
    issues = artifact.get("issues", [])
    lines = [
        "# Tool Verification: Lean Frontend Check",
        "",
        "## Summary",
        "",
        f"- Object: {artifact.get('object_id', '')}",
        f"- Title: {artifact.get('title', '')}",
        f"- Status: {artifact.get('status', '')}",
        f"- Checked: {str(artifact.get('checked', False)).lower()}",
        f"- Artifact: {artifact_path}",
        "- Tool: Lean",
        (
            "- External executable invoked: "
            f"{str(artifact.get('external_executable_invoked', False)).lower()}"
        ),
        f"- Accepts sorry: {str(artifact.get('accepts_sorry', True)).lower()}",
        "",
        "## Input",
        "",
        f"- lean_file: {input_data.get('lean_file', '') if isinstance(input_data, dict) else ''}",
        f"- timeout_seconds: {input_data.get('timeout_seconds', '') if isinstance(input_data, dict) else ''}",
        "",
        "## Output",
        "",
    ]
    if isinstance(output_data, dict) and output_data:
        for key, value in sorted(output_data.items()):
            lines.append(f"- {key}: {value!r}")
    else:
        lines.append("- none")
    lines.extend(["", "## Issues", ""])
    if isinstance(issues, list) and issues:
        lines.extend(f"- {issue}" for issue in issues)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Verification Boundary",
            "",
            "- This check only records Lean frontend success or failure for the file.",
            "- Files containing `sorry` may still pass this check.",
            "- A passing check is not a completed formal proof.",
            "",
        ]
    )
    return "\n".join(lines)


def _lean_check_record(
    project_root: Path,
    *,
    object_id: str,
    title: str,
    artifact_path: Path,
    report_path: Path,
    status: str,
) -> dict[str, object]:
    return {
        "kind": "lean_frontend_check",
        "object_id": object_id,
        "object_type": "lean_file",
        "title": title,
        "status": status,
        "artifact_path": artifact_path.relative_to(project_root).as_posix(),
        "report_path": report_path.relative_to(project_root).as_posix(),
        "source": {"tool": "lean"},
    }


def _lean_skeleton_text(
    item: dict[str, object],
    *,
    lean_name: str,
    namespace: str,
    reference_kb_status: str,
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
        f"Reference KB status: {reference_kb_status}",
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
    reference_kb_status: str,
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
        f"- Reference KB status: {reference_kb_status}",
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
        reference_kb_status=str(record.get("reference_kb_status", "")),
    )


def _tool_inventory_rows() -> list[dict[str, object]]:
    targets = (
        {
            "id": "lean",
            "label": "Lean",
            "kind": "command",
            "command": "lean",
            "purpose": "formal statement/type checking",
        },
        {
            "id": "lake",
            "label": "Lake",
            "kind": "command",
            "command": "lake",
            "purpose": "Lean project orchestration",
        },
        {
            "id": "sage",
            "label": "SageMath",
            "kind": "command",
            "command": "sage",
            "purpose": "algebra and computational examples",
        },
        {
            "id": "gap",
            "label": "GAP",
            "kind": "command",
            "command": "gap",
            "purpose": "group and finite algebra computations",
        },
        {
            "id": "sympy",
            "label": "SymPy",
            "kind": "python_module",
            "module": "sympy",
            "purpose": "symbolic computation checks",
        },
    )
    return [_tool_inventory_row(target) for target in targets]


def _tool_inventory_row(target: dict[str, str]) -> dict[str, object]:
    kind = target["kind"]
    if kind == "command":
        command = target["command"]
        resolved = shutil.which(command)
        return {
            "id": target["id"],
            "label": target["label"],
            "kind": kind,
            "purpose": target["purpose"],
            "status": "available" if resolved else "missing",
            "command": command,
            "path": resolved or "",
            "probe": "PATH lookup only",
        }
    module = target["module"]
    spec = importlib.util.find_spec(module)
    return {
        "id": target["id"],
        "label": target["label"],
        "kind": kind,
        "purpose": target["purpose"],
        "status": "available" if spec is not None else "missing",
        "module": module,
        "path": str(spec.origin) if spec is not None and spec.origin else "",
        "probe": "importlib.util.find_spec only",
    }


def _inventory_status(*, available: int, total: int) -> str:
    if total > 0 and available == total:
        return "available"
    if available > 0:
        return "partial"
    return "unavailable"


def _tool_inventory_report(manifest: dict[str, object]) -> str:
    lines = [
        "# Tool Inventory",
        "",
        "## Summary",
        "",
        f"- Status: {manifest['status']}",
        f"- Tools checked: {manifest['tools_checked']}",
        f"- Available: {manifest['available']}",
        f"- Missing: {manifest['missing']}",
        "- External verifier invoked: false",
        "",
        "## Tools",
        "",
    ]
    tools = manifest.get("tools", [])
    if not isinstance(tools, list) or not tools:
        lines.append("- none")
    else:
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            location = str(tool.get("path", "")).strip() or "not found"
            lines.append(
                (
                    f"- {tool.get('id', '')} | {tool.get('status', '')} | "
                    f"{tool.get('kind', '')} | {location}"
                )
            )
            lines.append(f"  - purpose: {tool.get('purpose', '')}")
            lines.append(f"  - probe: {tool.get('probe', '')}")
    lines.extend(
        [
            "",
            "## Verification Boundary",
            "",
            "- This inventory records local tool availability only.",
            "- No external verifier executable was invoked.",
            "- Availability does not imply any theorem, exercise, or computation was verified.",
            "",
        ]
    )
    return "\n".join(lines)


def _tool_inventory_record(
    project_root: Path,
    *,
    report_path: Path,
    manifest_path: Path,
    status: str,
) -> dict[str, object]:
    return {
        "kind": "tool_inventory",
        "object_id": "local_tool_inventory",
        "object_type": "environment",
        "title": "Local Tool Inventory",
        "status": status,
        "artifact_path": manifest_path.relative_to(project_root).as_posix(),
        "report_path": report_path.relative_to(project_root).as_posix(),
        "source": {"scope": "local_environment"},
    }


def _sympy_identity_artifact(
    *,
    object_id: str,
    lhs: str,
    rhs: str,
    title: str | None,
) -> dict[str, object]:
    artifact: dict[str, object] = {
        "schema_version": 1,
        "kind": "sympy_identity_check",
        "object_id": object_id,
        "title": title or object_id,
        "tool": "sympy",
        "status": "failed",
        "passed": False,
        "input": {
            "lhs": lhs,
            "rhs": rhs,
        },
        "output": {},
        "issues": [],
        "tool_backend_invoked": False,
        "subprocess_invoked": False,
    }
    if importlib.util.find_spec("sympy") is None:
        artifact["status"] = "unavailable"
        artifact["issues"] = ["SymPy is not available in this Python environment."]
        return artifact
    try:
        import sympy  # type: ignore[import-not-found]

        left = _parse_sympy_expression(sympy, lhs)
        right = _parse_sympy_expression(sympy, rhs)
        difference = sympy.simplify(left - right)
        passed = bool(difference == 0)
        artifact["status"] = "verified" if passed else "failed"
        artifact["passed"] = passed
        artifact["output"] = {
            "normalized_lhs": str(left),
            "normalized_rhs": str(right),
            "simplified_difference": str(difference),
        }
        artifact["tool_backend_invoked"] = True
        if not passed:
            artifact["issues"] = ["SymPy did not simplify lhs - rhs to 0."]
    except Exception as exc:  # pragma: no cover - exact SymPy messages vary.
        artifact["status"] = "failed"
        artifact["issues"] = [f"SymPy identity check failed: {exc}"]
    return artifact


def _parse_sympy_expression(sympy_module: object, expression: str) -> object:
    if not _safe_sympy_expression(expression):
        raise ValueError(
            "expression contains unsupported characters; allowed: letters, "
            "digits, underscores, spaces, + - * / ^ ( ) , ="
        )
    normalized = expression.replace("^", "**")
    return sympy_module.sympify(normalized, evaluate=True)


def _safe_sympy_expression(expression: str) -> bool:
    if not expression.strip():
        return False
    if "__" in expression:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9_+\-*/^(),= ]+", expression))


def _sympy_identity_report(
    artifact: dict[str, object],
    *,
    artifact_path: str,
) -> str:
    input_data = artifact.get("input", {})
    output_data = artifact.get("output", {})
    issues = artifact.get("issues", [])
    lines = [
        "# Tool Verification: SymPy Identity Check",
        "",
        "## Summary",
        "",
        f"- Object: {artifact.get('object_id', '')}",
        f"- Title: {artifact.get('title', '')}",
        f"- Status: {artifact.get('status', '')}",
        f"- Passed: {str(artifact.get('passed', False)).lower()}",
        f"- Artifact: {artifact_path}",
        "- Tool: SymPy",
        f"- Tool backend invoked: {str(artifact.get('tool_backend_invoked', False)).lower()}",
        f"- Subprocess invoked: {str(artifact.get('subprocess_invoked', False)).lower()}",
        "",
        "## Input",
        "",
        f"- lhs: {input_data.get('lhs', '') if isinstance(input_data, dict) else ''}",
        f"- rhs: {input_data.get('rhs', '') if isinstance(input_data, dict) else ''}",
        "",
        "## Output",
        "",
    ]
    if isinstance(output_data, dict) and output_data:
        lines.extend(
            f"- {key}: {value}" for key, value in sorted(output_data.items())
        )
    else:
        lines.append("- none")
    lines.extend(["", "## Issues", ""])
    if isinstance(issues, list) and issues:
        lines.extend(f"- {issue}" for issue in issues)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Verification Boundary",
            "",
            "- This check only verifies whether SymPy simplified lhs - rhs to 0.",
            "- It is computation evidence, not a formal proof.",
            "- No external executable or shell subprocess was invoked.",
            "",
        ]
    )
    return "\n".join(lines)


def _sympy_identity_record(
    project_root: Path,
    *,
    object_id: str,
    title: str,
    artifact_path: Path,
    report_path: Path,
    status: str,
) -> dict[str, object]:
    return {
        "kind": "sympy_identity_check",
        "object_id": object_id,
        "object_type": "computed_identity",
        "title": title,
        "status": status,
        "artifact_path": artifact_path.relative_to(project_root).as_posix(),
        "report_path": report_path.relative_to(project_root).as_posix(),
        "source": {"tool": "sympy"},
    }


def _sympy_counterexample_artifact(
    *,
    object_id: str,
    lhs: str,
    rhs: str,
    samples: tuple[int, ...],
    title: str | None,
) -> dict[str, object]:
    artifact: dict[str, object] = {
        "schema_version": 1,
        "kind": "sympy_counterexample_search",
        "object_id": object_id,
        "title": title or object_id,
        "tool": "sympy",
        "status": "failed",
        "counterexample_found": False,
        "input": {
            "lhs": lhs,
            "rhs": rhs,
            "samples": list(samples),
        },
        "output": {},
        "issues": [],
        "tool_backend_invoked": False,
        "subprocess_invoked": False,
    }
    if importlib.util.find_spec("sympy") is None:
        artifact["status"] = "unavailable"
        artifact["issues"] = ["SymPy is not available in this Python environment."]
        return artifact
    try:
        import sympy  # type: ignore[import-not-found]

        left = _parse_sympy_expression(sympy, lhs)
        right = _parse_sympy_expression(sympy, rhs)
        difference = sympy.simplify(left - right)
        symbols = sorted(difference.free_symbols, key=lambda symbol: symbol.name)
        counterexample = _find_sympy_counterexample(
            sympy,
            difference,
            symbols=symbols,
            samples=samples,
        )
        artifact["tool_backend_invoked"] = True
        artifact["output"] = {
            "normalized_lhs": str(left),
            "normalized_rhs": str(right),
            "simplified_difference": str(difference),
            "variables": [symbol.name for symbol in symbols],
            "counterexample": counterexample or {},
            "sample_count": _sample_count(symbols=symbols, samples=samples),
        }
        if counterexample:
            artifact["status"] = "counterexample_found"
            artifact["counterexample_found"] = True
        else:
            artifact["status"] = "no_counterexample_found"
            artifact["issues"] = [
                "No counterexample was found in the configured finite sample set."
            ]
    except Exception as exc:  # pragma: no cover - exact SymPy messages vary.
        artifact["status"] = "failed"
        artifact["issues"] = [f"SymPy counterexample search failed: {exc}"]
    return artifact


def _find_sympy_counterexample(
    sympy_module: object,
    difference: object,
    *,
    symbols: list[object],
    samples: tuple[int, ...],
) -> dict[str, object] | None:
    if not symbols:
        value = sympy_module.simplify(difference)
        if value != 0:
            return {"assignment": {}, "difference": str(value)}
        return None

    for values in itertools.product(samples, repeat=len(symbols)):
        assignment = dict(zip(symbols, values))
        evaluated_difference = sympy_module.simplify(difference.subs(assignment))
        if evaluated_difference != 0:
            return {
                "assignment": {
                    symbol.name: int(sample_value)
                    for symbol, sample_value in zip(symbols, values)
                },
                "difference": str(evaluated_difference),
            }
    return None


def _sample_count(*, symbols: list[object], samples: tuple[int, ...]) -> int:
    if not symbols:
        return 1
    return len(samples) ** len(symbols)


def _sympy_counterexample_report(
    artifact: dict[str, object],
    *,
    artifact_path: str,
) -> str:
    input_data = artifact.get("input", {})
    output_data = artifact.get("output", {})
    issues = artifact.get("issues", [])
    lines = [
        "# Tool Verification: SymPy Counterexample Search",
        "",
        "## Summary",
        "",
        f"- Object: {artifact.get('object_id', '')}",
        f"- Title: {artifact.get('title', '')}",
        f"- Status: {artifact.get('status', '')}",
        (
            "- Counterexample found: "
            f"{str(artifact.get('counterexample_found', False)).lower()}"
        ),
        f"- Artifact: {artifact_path}",
        "- Tool: SymPy",
        f"- Tool backend invoked: {str(artifact.get('tool_backend_invoked', False)).lower()}",
        f"- Subprocess invoked: {str(artifact.get('subprocess_invoked', False)).lower()}",
        "",
        "## Input",
        "",
        f"- lhs: {input_data.get('lhs', '') if isinstance(input_data, dict) else ''}",
        f"- rhs: {input_data.get('rhs', '') if isinstance(input_data, dict) else ''}",
        f"- samples: {input_data.get('samples', []) if isinstance(input_data, dict) else []}",
        "",
        "## Output",
        "",
    ]
    if isinstance(output_data, dict) and output_data:
        for key, value in sorted(output_data.items()):
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- none")
    lines.extend(["", "## Issues", ""])
    if isinstance(issues, list) and issues:
        lines.extend(f"- {issue}" for issue in issues)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Verification Boundary",
            "",
            "- This search evaluates a finite integer sample set only.",
            "- A found counterexample is computation evidence that the identity fails there.",
            "- Not finding a counterexample is not a proof of the identity.",
            "- No external executable or shell subprocess was invoked.",
            "",
        ]
    )
    return "\n".join(lines)


def _sympy_counterexample_record(
    project_root: Path,
    *,
    object_id: str,
    title: str,
    artifact_path: Path,
    report_path: Path,
    status: str,
) -> dict[str, object]:
    return {
        "kind": "sympy_counterexample_search",
        "object_id": object_id,
        "object_type": "computed_counterexample_search",
        "title": title,
        "status": status,
        "artifact_path": artifact_path.relative_to(project_root).as_posix(),
        "report_path": report_path.relative_to(project_root).as_posix(),
        "source": {"tool": "sympy"},
    }


def _gap_group_order_artifact(
    *,
    object_id: str,
    group_expression: str,
    expected_order: int,
    title: str | None,
    timeout_seconds: int,
) -> dict[str, object]:
    artifact: dict[str, object] = {
        "schema_version": 1,
        "kind": "gap_group_order_check",
        "object_id": object_id,
        "title": title or object_id,
        "tool": "gap",
        "status": "failed",
        "passed": False,
        "input": {
            "group_expression": group_expression,
            "expected_order": expected_order,
            "timeout_seconds": timeout_seconds,
        },
        "output": {},
        "issues": [],
        "external_executable_invoked": False,
    }
    if expected_order <= 0:
        artifact["issues"] = ["Expected order must be a positive integer."]
        return artifact
    if not _safe_gap_expression(group_expression):
        artifact["issues"] = ["GAP group expression contains unsupported characters."]
        return artifact
    gap_executable = shutil.which("gap")
    if not gap_executable:
        artifact["status"] = "unavailable"
        artifact["issues"] = ["GAP executable is not available on PATH."]
        return artifact

    script = f'Print(Size({group_expression}), "\\n");\nQUIT;\n'
    command = [gap_executable, "-q"]
    artifact["external_executable_invoked"] = True
    try:
        completed = subprocess.run(
            command,
            input=script,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        artifact["issues"] = [f"GAP group order check timed out after {timeout_seconds} seconds."]
        artifact["output"] = {
            "command": command,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
        }
        return artifact

    actual_order = _parse_gap_integer_output(completed.stdout)
    artifact["output"] = {
        "command": command,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    if actual_order is not None:
        output = artifact["output"]
        if isinstance(output, dict):
            output["actual_order"] = actual_order
    if completed.returncode != 0:
        artifact["issues"] = [f"GAP exited with code {completed.returncode}."]
        return artifact
    if actual_order is None:
        artifact["issues"] = ["Could not parse an integer group order from GAP output."]
        return artifact
    artifact["passed"] = actual_order == expected_order
    artifact["status"] = "verified" if artifact["passed"] else "failed"
    if not artifact["passed"]:
        artifact["issues"] = [
            f"Expected group order {expected_order}, but GAP returned {actual_order}."
        ]
    return artifact


def _safe_gap_expression(expression: str) -> bool:
    if not expression.strip():
        return False
    if any(token in expression for token in ("\n", "\r", ";", '"', "'", "\\")):
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9_(),\[\] ]+", expression))


def _parse_gap_integer_output(stdout: str) -> int | None:
    matches = re.findall(r"(?m)^\s*(\d+)\s*$", stdout)
    if not matches:
        return None
    return int(matches[-1])


def _gap_group_order_report(
    artifact: dict[str, object],
    *,
    artifact_path: str,
) -> str:
    input_data = artifact.get("input", {})
    output_data = artifact.get("output", {})
    issues = artifact.get("issues", [])
    lines = [
        "# Tool Verification: GAP Group Order Check",
        "",
        "## Summary",
        "",
        f"- Object: {artifact.get('object_id', '')}",
        f"- Title: {artifact.get('title', '')}",
        f"- Status: {artifact.get('status', '')}",
        f"- Passed: {str(artifact.get('passed', False)).lower()}",
        f"- Artifact: {artifact_path}",
        "- Tool: GAP",
        (
            "- External executable invoked: "
            f"{str(artifact.get('external_executable_invoked', False)).lower()}"
        ),
        "",
        "## Input",
        "",
        (
            "- group_expression: "
            f"{input_data.get('group_expression', '') if isinstance(input_data, dict) else ''}"
        ),
        (
            "- expected_order: "
            f"{input_data.get('expected_order', '') if isinstance(input_data, dict) else ''}"
        ),
        "",
        "## Output",
        "",
    ]
    if isinstance(output_data, dict) and output_data:
        for key, value in sorted(output_data.items()):
            lines.append(f"- {key}: {value!r}")
    else:
        lines.append("- none")
    lines.extend(["", "## Issues", ""])
    if isinstance(issues, list) and issues:
        lines.extend(f"- {issue}" for issue in issues)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Verification Boundary",
            "",
            "- It is computation evidence for one finite-structure expression.",
            "- It is not a formal proof.",
            "- GAP availability and library behavior are environment-dependent.",
            "",
        ]
    )
    return "\n".join(lines)


def _gap_group_order_record(
    project_root: Path,
    *,
    object_id: str,
    title: str,
    artifact_path: Path,
    report_path: Path,
    status: str,
) -> dict[str, object]:
    return {
        "kind": "gap_group_order_check",
        "object_id": object_id,
        "object_type": "finite_group_order",
        "title": title,
        "status": status,
        "artifact_path": artifact_path.relative_to(project_root).as_posix(),
        "report_path": report_path.relative_to(project_root).as_posix(),
        "source": {"tool": "gap"},
    }


def _sage_group_order_artifact(
    *,
    object_id: str,
    group_expression: str,
    expected_order: int,
    title: str | None,
    timeout_seconds: int,
) -> dict[str, object]:
    artifact: dict[str, object] = {
        "schema_version": 1,
        "kind": "sage_group_order_check",
        "object_id": object_id,
        "title": title or object_id,
        "tool": "sage",
        "status": "failed",
        "passed": False,
        "input": {
            "group_expression": group_expression,
            "expected_order": expected_order,
            "timeout_seconds": timeout_seconds,
        },
        "output": {},
        "issues": [],
        "external_executable_invoked": False,
    }
    if expected_order <= 0:
        artifact["issues"] = ["Expected order must be a positive integer."]
        return artifact
    if not _safe_sage_expression(group_expression):
        artifact["issues"] = ["Sage group expression contains unsupported characters."]
        return artifact
    sage_executable = shutil.which("sage")
    if not sage_executable:
        artifact["status"] = "unavailable"
        artifact["issues"] = ["Sage executable is not available on PATH."]
        return artifact

    code = f"from sage.all import *\nG = {group_expression}\nprint(G.order())"
    command = [sage_executable, "-c", code]
    artifact["external_executable_invoked"] = True
    try:
        completed = subprocess.run(
            command,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        artifact["issues"] = [f"Sage group order check timed out after {timeout_seconds} seconds."]
        artifact["output"] = {
            "command": [sage_executable, "-c", "<generated group-order code>"],
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
        }
        return artifact

    actual_order = _parse_gap_integer_output(completed.stdout)
    artifact["output"] = {
        "command": [sage_executable, "-c", "<generated group-order code>"],
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    if actual_order is not None:
        output = artifact["output"]
        if isinstance(output, dict):
            output["actual_order"] = actual_order
    if completed.returncode != 0:
        artifact["issues"] = [f"Sage exited with code {completed.returncode}."]
        return artifact
    if actual_order is None:
        artifact["issues"] = ["Could not parse an integer group order from Sage output."]
        return artifact
    artifact["passed"] = actual_order == expected_order
    artifact["status"] = "verified" if artifact["passed"] else "failed"
    if not artifact["passed"]:
        artifact["issues"] = [
            f"Expected group order {expected_order}, but Sage returned {actual_order}."
        ]
    return artifact


def _safe_sage_expression(expression: str) -> bool:
    if not expression.strip():
        return False
    if any(token in expression for token in ("\n", "\r", ";", '"', "'", "\\")):
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9_().,\[\] ]+", expression))


def _sage_group_order_report(
    artifact: dict[str, object],
    *,
    artifact_path: str,
) -> str:
    input_data = artifact.get("input", {})
    output_data = artifact.get("output", {})
    issues = artifact.get("issues", [])
    lines = [
        "# Tool Verification: Sage Group Order Check",
        "",
        "## Summary",
        "",
        f"- Object: {artifact.get('object_id', '')}",
        f"- Title: {artifact.get('title', '')}",
        f"- Status: {artifact.get('status', '')}",
        f"- Passed: {str(artifact.get('passed', False)).lower()}",
        f"- Artifact: {artifact_path}",
        "- Tool: SageMath",
        (
            "- External executable invoked: "
            f"{str(artifact.get('external_executable_invoked', False)).lower()}"
        ),
        "",
        "## Input",
        "",
        (
            "- group_expression: "
            f"{input_data.get('group_expression', '') if isinstance(input_data, dict) else ''}"
        ),
        (
            "- expected_order: "
            f"{input_data.get('expected_order', '') if isinstance(input_data, dict) else ''}"
        ),
        "",
        "## Output",
        "",
    ]
    if isinstance(output_data, dict) and output_data:
        for key, value in sorted(output_data.items()):
            lines.append(f"- {key}: {value!r}")
    else:
        lines.append("- none")
    lines.extend(["", "## Issues", ""])
    if isinstance(issues, list) and issues:
        lines.extend(f"- {issue}" for issue in issues)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Verification Boundary",
            "",
            "- It is computation evidence for one Sage expression.",
            "- It is not a formal proof.",
            "- Sage availability and library behavior are environment-dependent.",
            "",
        ]
    )
    return "\n".join(lines)


def _sage_group_order_record(
    project_root: Path,
    *,
    object_id: str,
    title: str,
    artifact_path: Path,
    report_path: Path,
    status: str,
) -> dict[str, object]:
    return {
        "kind": "sage_group_order_check",
        "object_id": object_id,
        "object_type": "finite_group_order",
        "title": title,
        "status": status,
        "artifact_path": artifact_path.relative_to(project_root).as_posix(),
        "report_path": report_path.relative_to(project_root).as_posix(),
        "source": {"tool": "sage"},
    }


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
            "artifact_fingerprint": _empty_fingerprint(),
            "report_fingerprint": _empty_fingerprint(),
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
    reference_status = record.get("reference_kb_status")
    if isinstance(reference_status, str) and reference_status.strip():
        if reference_status != "current":
            issues.append(f"reference KB status is {reference_status}")
    return {
        "object_id": str(record.get("object_id") or f"record_{index}"),
        "kind": str(record.get("kind") or ""),
        "record_status": str(record.get("status") or ""),
        "quality_status": "fail" if issues else "pass",
        "artifact_path": artifact_path if isinstance(artifact_path, str) else "",
        "report_path": str(record.get("report_path") or ""),
        "artifact_fingerprint": _artifact_fingerprint(project_root, artifact_path),
        "report_fingerprint": _artifact_fingerprint(project_root, record.get("report_path")),
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


def _artifact_fingerprint(project_root: Path, value: object) -> dict[str, str]:
    if not isinstance(value, str) or not value.strip():
        return _empty_fingerprint()
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        return _empty_fingerprint()
    resolved = project_root / path
    if not resolved.exists():
        return _empty_fingerprint()
    return _source_manifest_fingerprint(resolved)


def _empty_fingerprint() -> dict[str, str]:
    return {"algorithm": "sha256", "value": ""}


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
        "source_manifest_fingerprint": _source_manifest_fingerprint(source_manifest_path),
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
        f"- Source manifest fingerprint: {_fingerprint_label(manifest)}",
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


def _source_manifest_fingerprint(path: Path) -> dict[str, str]:
    value = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""
    return {"algorithm": "sha256", "value": value}


def _fingerprint_label(manifest: dict[str, object]) -> str:
    fingerprint = manifest.get("source_manifest_fingerprint")
    if not isinstance(fingerprint, dict):
        return "not recorded"
    algorithm = str(fingerprint.get("algorithm", "")).strip()
    value = str(fingerprint.get("value", "")).strip()
    if not algorithm or not value:
        return "not recorded"
    return f"{algorithm}:{value}"


def _manifest_record(
    project_root: Path,
    item: dict[str, object],
    *,
    skeleton_path: Path,
    report_path: Path,
    reference_kb_status: str,
    status: str,
) -> dict[str, object]:
    source = item.get("source", {})
    return {
        "kind": "lean_statement_skeleton",
        "object_id": str(item.get("id", "")),
        "object_type": str(item.get("type", "")),
        "title": str(item.get("title", "")),
        "status": status,
        "reference_kb_status": reference_kb_status,
        "skeleton_path": skeleton_path.relative_to(project_root).as_posix(),
        "report_path": report_path.relative_to(project_root).as_posix(),
        "source": source if isinstance(source, dict) else {},
    }


def _lean_skeleton_status(reference_kb_status: str) -> str:
    if reference_kb_status == "stale":
        return "stale_reference_kb"
    return "unchecked_skeleton"


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
