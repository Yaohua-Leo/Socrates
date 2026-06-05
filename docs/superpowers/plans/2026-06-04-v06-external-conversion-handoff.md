# v06 External Conversion Handoff Implementation Plan
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the remaining PDF/OCR ingestion gap without introducing a bundled OCR/PDF dependency by letting users attach an externally converted Markdown file to an imported reference.

**Architecture:** Add a reference-layer handoff function that copies a user-provided Markdown conversion into `01_references/converted/markdown/`, creates the normal curated draft, updates `source_registry.yaml`, and records project-log provenance. Keep raw references immutable and keep curation review required before Reference KB trust.

**Tech Stack:** Python standard library, existing Socrates source registry helpers, unittest, Markdown artifacts.

---

## Scope

- Add an API for attaching an external Markdown conversion to an imported source.
- Expose it through `socrates sources attach-conversion --project ... --source-id ... --markdown ...`.
- Support PDF sources that were previously `conversion_pending`; keep behavior useful for any imported source where the user has a better external conversion.
- Preserve raw imported file bytes.
- Keep curated output a draft and keep Reference KB build gated on curated Markdown.
- Do not add PDF/OCR dependencies or call external OCR tools.

## Data Contract

Input:

```powershell
python -m socrates sources attach-conversion --project ".\projects\group_theory" --source-id abstract_algebra --markdown ".\abstract_algebra.converted.md"
```

Writes:

- `01_references/converted/markdown/<source_id>.md`
- `01_references/curated/<source_id>.curated.md`
- registry status `curated_draft`
- `processed_paths.markdown` and `processed_paths.curated`
- project log entry

Converted Markdown should include Socrates provenance metadata showing:

- original `source_id`
- raw source path
- external conversion source file name/path
- review requirement

## Tasks

- [ ] Add tests for a conversion-pending PDF being upgraded to a curated draft by attaching external Markdown.
- [ ] Add tests that the CLI prints the converted and curated paths.
- [ ] Add tests that raw imported files remain unchanged.
- [ ] Implement `attach_converted_markdown`.
- [ ] Wire `sources attach-conversion`.
- [ ] Update README, docs index, roadmap, and development log.
- [ ] Update `D:\llmwiki` with the reusable boundary: external conversion handoff is accepted, but OCR/PDF extraction remains external and curated drafts remain review-gated.
- [ ] Run targeted tests, full unittest discovery, compileall, diff check, and check scripts.
- [ ] Commit with Lore protocol.

## Validation Commands

```powershell
python -m unittest tests.test_reference_import
python -m unittest discover -s tests
python -m compileall socrates
git diff --check
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
bash scripts/check.sh
```

## Stop Condition

v06 is complete when a PDF can move from conversion-pending to curated draft through an explicit external Markdown handoff, provenance is visible in artifacts, raw source bytes are unchanged, docs/wiki record the boundary, the full checks pass, and a Lore commit is created.
