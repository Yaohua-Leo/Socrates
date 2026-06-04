# v0.25 Study Brief Manifest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Back study brief status with a structured manifest so freshness checks do not depend on parsing Markdown when the current brief command writes new artifacts.

**Architecture:** Extend `socrates.study_brief` to write `07_exports/briefs/study_brief_manifest.json` beside the Markdown brief. Extend `socrates.study_brief_status` to prefer the manifest, treat malformed manifests conservatively as `invalid`, and keep Markdown next-action parsing only as a legacy fallback when a brief exists without a manifest.

**Tech Stack:** Python stdlib JSON, existing Socrates CLI, `unittest`, deterministic filesystem fixtures.

---

## File Map

- Modify `socrates/study_brief.py`: write a manifest after writing the Markdown brief.
- Modify `socrates/study_brief_status.py`: add manifest path, manifest validation, and legacy Markdown fallback.
- Modify `tests/test_study_brief.py`: add manifest and invalid-manifest coverage.
- Modify docs after GREEN: `README.md`, `docs/README.md`, `docs/development_log.md`, `docs/development_roadmap.md`.

## Acceptance Criteria

- `python -m socrates brief --project <project>` writes both `study_brief.md` and `study_brief_manifest.json`.
- The manifest records schema version, deterministic boundary, brief path, recorded next action, and action type.
- Dashboard/status still show `Study brief: current` after a generated brief.
- A malformed manifest makes dashboard/status show `Study brief: invalid` even if the Markdown brief still contains a parsable next action.
- A legacy Markdown brief without a manifest can still be classified by parsing its `- Next action:` row.

---

### Task 1: RED Manifest Tests

**Files:**
- Modify: `tests/test_study_brief.py`

- [x] **Step 1: Add failing manifest tests**

Add tests that:

1. Run `brief`, read `07_exports/briefs/study_brief_manifest.json`, and assert it contains `schema_version: 1`, `quality_boundary: deterministic_study_brief`, `status: generated`, `brief_path`, `recorded_next_action`, and `action_type`.
2. Corrupt the manifest after generating a brief, then assert dashboard and status show `Study brief: invalid`.

- [x] **Step 2: Run RED**

Run:

```powershell
python -m unittest tests.test_study_brief
```

Expected: fail because the manifest is not written yet and invalid manifest handling is not implemented.

---

### Task 2: Write and Read Structured Manifest

**Files:**
- Modify: `socrates/study_brief.py`
- Modify: `socrates/study_brief_status.py`

- [x] **Step 1: Write manifest from brief generation**

Use `write_json` to write `07_exports/briefs/study_brief_manifest.json` after the Markdown brief. Reuse the same recorded next action and action type shown in `## Start Here`.

- [x] **Step 2: Prefer manifest in status reader**

Add `STUDY_BRIEF_MANIFEST_RELATIVE_PATH`, read and validate the manifest first when it exists, and return `invalid` for malformed JSON or missing required fields.

- [x] **Step 3: Preserve Markdown fallback**

If the Markdown brief exists but no manifest exists, keep the v0.24 fallback that parses `- Next action:` from the brief.

- [x] **Step 4: Run GREEN**

Run:

```powershell
python -m unittest tests.test_study_brief tests.test_dashboard tests.test_status_quality_summary
```

Expected: tests OK.

---

### Task 3: Docs, Verification, Commit, and Wiki

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/development_log.md`
- Modify: `docs/development_roadmap.md`
- Modify: `docs/superpowers/plans/2026-06-04-v25-study-brief-manifest.md`
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.25**

Document that study brief status is manifest-backed for newly generated briefs and Markdown parsing remains a legacy fallback only.

- [x] **Step 2: Run verification**

Run:

```powershell
python -m unittest tests.test_study_brief tests.test_dashboard tests.test_status_quality_summary tests.test_learning_queue
python -m unittest discover -s tests
python -m compileall socrates
git diff --check
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
bash scripts/check.sh
```

- [x] **Step 3: Commit with Lore protocol**

Commit the v0.25 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.25 commit id, verification evidence, manifest path, and the reader-boundary lesson.
