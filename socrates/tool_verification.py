"""Tool-verification artifact generation for Socrates projects."""

from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import itertools
import json
from pathlib import Path
import re
import shutil

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

    allowed_statuses = {
        "all",
        "available",
        "counterexample_found",
        "failed",
        "no_counterexample_found",
        "partial",
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
