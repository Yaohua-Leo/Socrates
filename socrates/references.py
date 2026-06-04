"""Local reference import and source registry updates."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import shutil

from .context import append_project_log, load_project, write_text
from .contracts import SourceRecord, yaml_scalar
from .llm import LlmClient, LlmMessage, LlmRequest, parse_json_object, sha256_text
from .llm_artifacts import record_llm_suggestion
from .project import slugify_topic


REFERENCE_TYPES = {
    ".pdf": ("pdf", "books"),
    ".md": ("markdown", "markdown"),
    ".markdown": ("markdown", "markdown"),
    ".tex": ("latex", "latex"),
    ".txt": ("text", "text"),
}


@dataclass(frozen=True)
class SourceSummary:
    """A source registry entry prepared for CLI display."""

    id: str
    type: str
    title: str
    role: str
    priority: str
    status: str
    local_path: str
    markdown_path: str
    curated_path: str
    notes: str
    curated_quality_status: str | None = None


@dataclass(frozen=True)
class CorrectionPatchSummary:
    """A correction patch proposal prepared for CLI display."""

    patch_id: str
    status: str
    source_id: str
    risk_level: str
    location: str
    path: str


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


def list_source_registry(
    project_path: Path | str,
    *,
    status: str = "all",
    role: str = "all",
    source_type: str = "all",
) -> list[SourceSummary]:
    """List imported sources from ``source_registry.yaml``."""

    context = load_project(project_path)
    records = _registry_records(context.source_registry.read_text(encoding="utf-8"))
    quality_by_curated_path = _ingestion_quality_by_curated_path(context.root)
    summaries = [
        _source_summary(record, quality_by_curated_path=quality_by_curated_path)
        for record in records
    ]
    if status != "all":
        summaries = [summary for summary in summaries if summary.status == status]
    if role != "all":
        summaries = [summary for summary in summaries if summary.role == role]
    if source_type != "all":
        summaries = [summary for summary in summaries if summary.type == source_type]
    return summaries


def curate_reference(project_path: Path | str, source_id: str) -> Path:
    """Create a curated Markdown draft for an imported text-like reference."""

    context = load_project(project_path)
    registry_text = context.source_registry.read_text(encoding="utf-8")
    record = _find_registry_record(registry_text, source_id)
    if record is None:
        raise ValueError(f"Unknown source id: {source_id}")

    source_type = record.get("type", "")
    if source_type == "pdf":
        return _record_conversion_pending(context, record)
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


def create_correction_patch(
    project_path: Path | str,
    source_id: str,
    *,
    location: str,
    original: str,
    proposed_correction: str,
    reason: str,
    risk_level: str = "low",
) -> Path:
    """Write a patch-only correction proposal for a converted reference."""

    context = load_project(project_path)
    registry_text = context.source_registry.read_text(encoding="utf-8")
    record = _find_registry_record(registry_text, source_id)
    if record is None:
        raise ValueError(f"Unknown source id: {source_id}")

    patch_dir = context.references_dir / "converted" / "patches"
    patch_dir.mkdir(parents=True, exist_ok=True)
    patch_number = _next_patch_number(patch_dir, source_id)
    patch_path = patch_dir / f"{source_id}_patch_{patch_number:03d}.patch.md"
    write_text(
        patch_path,
        _correction_patch_markdown(
            record,
            patch_number=patch_number,
            location=location,
            original=original,
            proposed_correction=proposed_correction,
            reason=reason,
            risk_level=risk_level,
        ),
    )
    append_project_log(
        context,
        f"Wrote correction patch {patch_path.name} for reference {source_id}.",
    )
    return patch_path


def suggest_correction_patch_with_llm(
    project_path: Path | str,
    source_id: str,
    *,
    client: LlmClient,
    location_hint: str = "",
) -> Path:
    """Ask an LLM for a patch-only correction proposal for a curated reference."""

    context = load_project(project_path)
    registry_text = context.source_registry.read_text(encoding="utf-8")
    record = _find_registry_record(registry_text, source_id)
    if record is None:
        raise ValueError(f"Unknown source id: {source_id}")
    curated_relative = record.get("processed_paths.curated", "")
    if not curated_relative:
        raise ValueError(f"Reference {source_id} does not have a curated markdown path")
    curated_path = context.root / curated_relative
    curated_text = curated_path.read_text(encoding="utf-8")
    response = client.complete(
        LlmRequest(
            purpose="reference_patch_suggestion",
            messages=(
                LlmMessage(
                    role="system",
                    content=(
                        "Return one JSON object with keys location, original, "
                        "proposed_correction, reason, risk_level. The original value "
                        "must be an exact span from the curated reference."
                    ),
                ),
                LlmMessage(
                    role="user",
                    content=(
                        f"Source id: {source_id}\n"
                        f"Location hint: {location_hint}\n\n"
                        f"Curated reference:\n{curated_text[:12000]}"
                    ),
                ),
            ),
            temperature=0.1,
        )
    )
    suggestion = _parse_patch_suggestion(response.content)
    if suggestion["original"] not in curated_text:
        raise ValueError("LLM suggested original text was not found in the curated reference")
    patch_path = create_correction_patch(
        context.root,
        source_id,
        location=suggestion["location"],
        original=suggestion["original"],
        proposed_correction=suggestion["proposed_correction"],
        reason=suggestion["reason"],
        risk_level=suggestion["risk_level"],
    )
    record_llm_suggestion(
        context.root,
        artifact_path=patch_path,
        suggestion_type="reference_correction_patch",
        provider=client.provider,
        model=client.model,
        source_paths=[curated_relative],
        prompt_hash=sha256_text(curated_text + location_hint),
    )
    return patch_path


def list_correction_patches(
    project_path: Path | str,
    *,
    source_id: str | None = None,
) -> list[CorrectionPatchSummary]:
    """List persisted patch-only correction proposals."""

    context = load_project(project_path)
    patch_dir = context.references_dir / "converted" / "patches"
    if not patch_dir.exists():
        return []

    summaries: list[CorrectionPatchSummary] = []
    for patch_path in sorted(patch_dir.glob("*.patch.md"), key=lambda path: path.name):
        summary = _correction_patch_summary(context.root, patch_path)
        if source_id is not None and summary.source_id != source_id:
            continue
        summaries.append(summary)
    return summaries


def review_correction_patch(
    project_path: Path | str,
    patch_id: str,
    *,
    decision: str,
    note: str = "",
) -> Path:
    """Record a human review decision on a correction patch proposal."""

    context = load_project(project_path)
    normalized_id = patch_id.removesuffix(".patch.md").removesuffix(".patch")
    patch_path = context.references_dir / "converted" / "patches" / f"{normalized_id}.patch.md"
    if not patch_path.exists():
        raise FileNotFoundError(f"Correction patch does not exist: {patch_path}")

    text = patch_path.read_text(encoding="utf-8")
    write_text(patch_path, _with_review_decision(text, decision=decision, note=note))
    append_project_log(context, f"Reviewed correction patch {normalized_id}: {decision}.")
    return patch_path


def apply_correction_patch(project_path: Path | str, patch_id: str) -> Path:
    """Apply one accepted correction patch to its curated reference draft."""

    context = load_project(project_path)
    normalized_id = patch_id.removesuffix(".patch.md").removesuffix(".patch")
    patch_path = context.references_dir / "converted" / "patches" / f"{normalized_id}.patch.md"
    if not patch_path.exists():
        raise FileNotFoundError(f"Correction patch does not exist: {patch_path}")

    patch_text = patch_path.read_text(encoding="utf-8")
    if _patch_review_status(patch_text) != "accepted":
        raise ValueError(f"Correction patch {normalized_id} must be accepted before apply")

    target_path = context.root / _patch_target_relative_path(patch_text)
    if not target_path.exists():
        raise FileNotFoundError(f"Curated reference does not exist: {target_path}")

    original = _patch_fenced_section_value(patch_text, "Original")
    proposed = _patch_fenced_section_value(patch_text, "Proposed Correction")
    if not original or not proposed:
        raise ValueError(f"Correction patch {normalized_id} is missing original or proposed text")

    target_text = target_path.read_text(encoding="utf-8")
    match_count = target_text.count(original)
    if match_count != 1:
        raise ValueError(
            f"Correction patch {normalized_id} expected exactly one curated match, "
            f"found {match_count}"
        )

    write_text(target_path, target_text.replace(original, proposed, 1))
    write_text(
        patch_path,
        _with_apply_result(
            patch_text,
            target=target_path.relative_to(context.root).as_posix(),
        ),
    )
    append_project_log(context, f"Applied correction patch {normalized_id} to curated reference.")
    return target_path


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
    for record in _registry_records(registry_text):
        if record.get("id") == source_id:
            return record
    return None


def _registry_records(registry_text: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    in_processed_paths = False
    for line in registry_text.splitlines():
        if line.startswith("  - id: "):
            if current:
                records.append(current)
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
    if current:
        records.append(current)
    return records


def _source_summary(
    record: dict[str, str],
    *,
    quality_by_curated_path: dict[str, str] | None = None,
) -> SourceSummary:
    curated_path = record.get("processed_paths.curated", "")
    quality_lookup = quality_by_curated_path or {}
    return SourceSummary(
        id=record.get("id", ""),
        type=record.get("type", ""),
        title=record.get("title", ""),
        role=record.get("role", ""),
        priority=record.get("priority", ""),
        status=record.get("status", ""),
        local_path=record.get("local_path", ""),
        markdown_path=record.get("processed_paths.markdown", ""),
        curated_path=curated_path,
        notes=record.get("notes", ""),
        curated_quality_status=quality_lookup.get(curated_path),
    )


def _ingestion_quality_by_curated_path(project_root: Path) -> dict[str, str]:
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


def _registry_value(value: str) -> str:
    if value == "null":
        return ""
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    return value


def _parse_patch_suggestion(content: str) -> dict[str, str]:
    required = ("location", "original", "proposed_correction", "reason", "risk_level")
    data = parse_json_object(content, required_keys=required)
    result = {key: str(data.get(key, "")).strip() for key in required}
    missing = [key for key, value in result.items() if not value]
    if missing:
        raise ValueError(f"LLM patch suggestion missing fields: {', '.join(missing)}")
    if result["risk_level"] not in {"low", "medium", "high"}:
        raise ValueError("LLM patch suggestion risk_level must be low, medium, or high")
    return result


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


def _record_conversion_pending(context, record: dict[str, str]) -> Path:
    pending_path = (
        context.references_dir
        / "converted"
        / "markdown"
        / f"{record['id']}.conversion_pending.md"
    )
    write_text(pending_path, _conversion_pending_markdown(record))
    relative_pending_path = _relative_project_path(context.root, pending_path)
    _update_registry_source(
        context.source_registry,
        record["id"],
        status="conversion_pending",
        markdown_path=relative_pending_path,
        curated_path=None,
    )
    append_project_log(context, f"Marked reference {record['id']} conversion pending.")
    return pending_path


def _conversion_pending_markdown(record: dict[str, str]) -> str:
    return (
        f"# Conversion Pending: {record.get('title', record['id'])}\n\n"
        "<!-- socrates-conversion-pending: no approved PDF extraction backend configured -->\n\n"
        "## Source Metadata\n\n"
        f"- source_id: {record['id']}\n"
        f"- raw_path: {record.get('local_path', '')}\n\n"
        "## Pending Reason\n\n"
        "- PDF extraction requires an approved backend before curated content can be built.\n"
    )


def _next_patch_number(patch_dir: Path, source_id: str) -> int:
    prefix = f"{source_id}_patch_"
    existing_numbers: list[int] = []
    for patch_path in patch_dir.glob(f"{source_id}_patch_*.patch.md"):
        suffix = patch_path.name.removeprefix(prefix).removesuffix(".patch.md")
        if suffix.isdigit():
            existing_numbers.append(int(suffix))
    return max(existing_numbers, default=0) + 1


def _correction_patch_markdown(
    record: dict[str, str],
    *,
    patch_number: int,
    location: str,
    original: str,
    proposed_correction: str,
    reason: str,
    risk_level: str,
) -> str:
    title = record.get("title", record["id"])
    return (
        f"# Correction Patch: {title}\n\n"
        "review_status: pending\n\n"
        f"## Patch {patch_number:03d}\n\n"
        "### Source\n\n"
        f"- source_id: {record['id']}\n"
        f"- title: {title}\n"
        f"- raw_path: {record.get('local_path', 'none') or 'none'}\n"
        f"- converted_path: {record.get('processed_paths.markdown', 'none') or 'none'}\n"
        f"- curated_path: {record.get('processed_paths.curated', 'none') or 'none'}\n\n"
        "### Location\n\n"
        f"{location.strip()}\n\n"
        "### Original\n\n"
        f"{_fenced_text(original)}\n\n"
        "### Proposed Correction\n\n"
        f"{_fenced_text(proposed_correction)}\n\n"
        "### Reason\n\n"
        f"{reason.strip()}\n\n"
        "### Risk Level\n\n"
        f"{risk_level}\n"
    )


def _correction_patch_summary(project_root: Path, patch_path: Path) -> CorrectionPatchSummary:
    text = patch_path.read_text(encoding="utf-8")
    return CorrectionPatchSummary(
        patch_id=patch_path.stem.removesuffix(".patch"),
        status=_patch_review_status(text),
        source_id=_patch_source_id(text),
        risk_level=_patch_section_value(text, "Risk Level") or "unknown",
        location=_patch_section_value(text, "Location") or "unknown",
        path=patch_path.relative_to(project_root).as_posix(),
    )


def _patch_source_id(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- source_id:"):
            return stripped.removeprefix("- source_id:").strip()
    return "unknown"


def _patch_section_value(text: str, heading: str) -> str:
    marker = f"### {heading}"
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() != marker:
            continue
        values: list[str] = []
        for value in lines[index + 1 :]:
            if value.startswith("### "):
                break
            stripped = value.strip()
            if stripped:
                values.append(stripped)
        return " ".join(values)
    return ""


def _patch_review_status(text: str) -> str:
    apply_status = _patch_apply_field(text, "status")
    if apply_status == "applied":
        return "applied"
    decision = _patch_review_field(text, "decision")
    return decision if decision else "pending"


def _patch_review_field(text: str, key: str) -> str:
    in_review = False
    prefix = f"- {key}:"
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "### Review Decision":
            in_review = True
            continue
        if in_review and line.startswith("### "):
            return ""
        if in_review and stripped.startswith(prefix):
            return stripped.removeprefix(prefix).strip()
    return ""


def _patch_apply_field(text: str, key: str) -> str:
    in_apply = False
    prefix = f"- {key}:"
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "### Apply Result":
            in_apply = True
            continue
        if in_apply and line.startswith("### "):
            return ""
        if in_apply and stripped.startswith(prefix):
            return stripped.removeprefix(prefix).strip()
    return ""


def _patch_target_relative_path(text: str) -> Path:
    curated_path = _patch_source_field(text, "curated_path")
    if not curated_path or curated_path == "none":
        raise ValueError("Correction patch does not reference a curated target")
    return Path(curated_path)


def _patch_source_field(text: str, key: str) -> str:
    prefix = f"- {key}:"
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(prefix):
            return stripped.removeprefix(prefix).strip()
    return ""


def _patch_fenced_section_value(text: str, heading: str) -> str:
    marker = f"### {heading}"
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() != marker:
            continue
        fence = ""
        values: list[str] = []
        for value in lines[index + 1 :]:
            stripped = value.strip()
            if not fence:
                if not stripped:
                    continue
                if stripped.startswith("```"):
                    fence = stripped[: len(stripped) - len(stripped.lstrip("`"))]
                    continue
                return stripped
            if stripped == fence:
                return "\n".join(values)
            values.append(value)
    return ""


def _with_review_decision(text: str, *, decision: str, note: str) -> str:
    decision_block = _review_decision_markdown(decision=decision, note=note)
    marker = "\n### Review Decision\n"
    if marker not in text:
        return text.rstrip() + "\n\n" + decision_block
    before, _, existing_tail = text.partition(marker)
    _, separator, after = existing_tail.partition("\n### ")
    if separator:
        return before.rstrip() + "\n\n" + decision_block.rstrip() + "\n\n### " + after
    return before.rstrip() + "\n\n" + decision_block


def _review_decision_markdown(*, decision: str, note: str) -> str:
    lines = [
        "### Review Decision",
        "",
        f"- decision: {decision}",
    ]
    if note.strip():
        lines.append(f"- note: {note.strip()}")
    return "\n".join(lines).rstrip() + "\n"


def _with_apply_result(text: str, *, target: str) -> str:
    apply_block = _apply_result_markdown(target=target)
    marker = "\n### Apply Result\n"
    if marker not in text:
        return text.rstrip() + "\n\n" + apply_block
    before, _, existing_tail = text.partition(marker)
    _, separator, after = existing_tail.partition("\n### ")
    if separator:
        return before.rstrip() + "\n\n" + apply_block.rstrip() + "\n\n### " + after
    return before.rstrip() + "\n\n" + apply_block


def _apply_result_markdown(*, target: str) -> str:
    return (
        "### Apply Result\n\n"
        "- status: applied\n"
        f"- target: {target}\n"
    )


def _fenced_text(value: str) -> str:
    fence = "```"
    while fence in value:
        fence += "`"
    return f"{fence}text\n{value.rstrip()}\n{fence}"


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
LATEX_OBJECT_TYPE_ALIASES = {
    "def": "definition",
    "defn": "definition",
    "thm": "theorem",
    "prop": "proposition",
    "proposition": "proposition",
    "lem": "lemma",
    "lemma": "lemma",
    "cor": "corollary",
    "corr": "corollary",
    "ex": "example",
    "eg": "example",
    "exmp": "example",
    "cex": "counterexample",
    "counterex": "counterexample",
    "exer": "exercise",
    "exc": "exercise",
    "rem": "remark",
    "rmk": "remark",
    "ntn": "notation",
}
LATEX_SECTION_RE = re.compile(r"\\(?P<level>section|subsection|subsubsection)\{(?P<title>[^}]*)\}")
LATEX_BEGIN_RE = re.compile(
    r"\\begin\{(?P<kind>[a-zA-Z*]+)\}(?:\[(?P<title>[^\]]+)\])?"
)
LATEX_END_RE = re.compile(r"\\end\{(?P<kind>[a-zA-Z*]+)\}")
LATEX_OBJECT_NUMBER_RE = re.compile(
    r"^(?P<number>[A-Za-z]?\d+(?:\.\d+)*(?:[a-z])?)\s+(?P<title>.+)$"
)


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
            kind = _latex_object_type(begin.group("kind"))
            if kind is not None:
                title = begin.group("title") or kind.replace("_", " ").title()
                lines.append(_latex_object_heading(kind, title))
                continue

        end = LATEX_END_RE.fullmatch(stripped)
        if end and _latex_object_type(end.group("kind")) is not None:
            continue
        if stripped.startswith(r"\label{"):
            continue
        lines.append(raw_line)
    return "\n".join(lines).rstrip() + "\n"


def _latex_object_type(kind: str) -> str | None:
    normalized = kind.rstrip("*").casefold()
    if normalized in LATEX_OBJECT_TYPES:
        return normalized
    return LATEX_OBJECT_TYPE_ALIASES.get(normalized)


def _plain_latex_title(title: str) -> str:
    return title.replace(r"\_", "_").strip()


def _latex_object_heading(kind: str, title: str) -> str:
    object_type = kind.title()
    plain_title = _plain_latex_title(title)
    numbered = LATEX_OBJECT_NUMBER_RE.fullmatch(plain_title)
    if numbered:
        return f"### {object_type} {numbered.group('number')}: {numbered.group('title').strip()}"
    return f"### {object_type}: {plain_title}"


def _update_registry_source(
    registry_path: Path,
    source_id: str,
    *,
    status: str,
    markdown_path: str,
    curated_path: str | None,
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
