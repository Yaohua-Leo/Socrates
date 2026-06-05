# v0.54 Brief Status JSON Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development before implementation. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `brief status --json` so wrappers, UI prototypes, plugins, and automation can inspect saved study-brief freshness without parsing prose.

**Architecture:** Build a structured read-only status payload from the existing `summarize_study_brief(...)` reader. JSON mode must not generate briefs, refresh reports, run repairs, call an LLM, score learning, approve artifacts, or mutate project state.

**Tech Stack:** Python argparse, existing study-brief freshness reader, shared project-title helper, `json`, `unittest`, deterministic temporary project fixtures.

---

## File Map

- Modify `tests/test_study_brief.py`: add RED coverage for `brief status --json`, missing/current brief payloads, and no-write behavior.
- Modify `socrates/study_brief_status.py`: add `build_study_brief_status_payload(...)`.
- Modify `socrates/cli.py`: add `--json` to `brief status` and print deterministic JSON.
- Modify docs after GREEN: `README.md`, `docs/README.md`, `docs/development_log.md`, `docs/development_roadmap.md`.
- Modify this plan as checklist state changes.
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`.

## Acceptance Criteria

- `python -m socrates brief status --project <project> --json` exits 0 and emits valid deterministic JSON.
- The payload includes `schema_version: 1`, `quality_boundary: deterministic_study_brief_status`, `project`, `root`, `study_brief`, `study_brief_path`, `recorded_next_action`, and `current_next_action`.
- Missing, current, stale, and invalid status semantics continue to come from `summarize_study_brief(...)`.
- Prose `brief status` output remains stable.
- JSON mode is read-only and does not write `study_brief.md`, `study_brief_manifest.json`, project logs, learning state, queue artifacts, or any project file.

---

### Task 1: RED Brief Status JSON Tests

**Files:**
- Modify: `tests/test_study_brief.py`

- [x] **Step 1: Add failing missing-brief JSON test**

Run `brief status --json` on an empty project, assert payload metadata, not-run fields, no prose output, and project file tree unchanged.

- [x] **Step 2: Add failing current-brief JSON test**

Generate a brief, run `brief status --json`, assert current fields match the generated manifest/current queue action, and project file tree unchanged after the status read.

- [x] **Step 3: Run RED**

Run:

```powershell
python -m unittest tests.test_study_brief
```

Expected: fail because `brief status --json` is not registered yet.

---

### Task 2: Add Brief Status JSON Payload

**Files:**
- Modify: `socrates/study_brief_status.py`
- Modify: `socrates/cli.py`

- [x] **Step 1: Register `--json`**

Add `--json` to the `brief status` parser and route JSON output through the status payload.

- [x] **Step 2: Build structured payload**

Create `build_study_brief_status_payload(...)` with project metadata and status fields from `summarize_study_brief(...)`.

- [x] **Step 3: Preserve read-only boundary**

Ensure JSON mode reads only and does not write project artifacts.

- [x] **Step 4: Run GREEN**

Run:

```powershell
python -m unittest tests.test_study_brief
```

Expected: tests OK.

---

### Task 3: Docs, Verification, Commit, and Wiki

**Files:**
- Modify `README.md`
- Modify `docs/README.md`
- Modify `docs/development_log.md`
- Modify `docs/development_roadmap.md`
- Modify `docs/superpowers/plans/2026-06-04-v54-brief-status-json.md`
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.54**

Document `brief status --json` as a read-only structured study-brief freshness payload, not a generator or readiness gate.

- [x] **Step 2: Run verification**

Run:

```powershell
python -m unittest tests.test_study_brief
python -m unittest tests.test_study_brief tests.test_dashboard tests.test_status_quality_summary tests.test_learning_queue tests.test_reports
python -m unittest discover -s tests
python -m compileall socrates
git diff --check
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
bash scripts/check.sh
```

- [ ] **Step 3: Commit with Lore protocol**

Commit the v0.54 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [ ] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.54 commit id, verification evidence, brief-status JSON boundary, and the reusable lesson that freshness/status readers should expose structured status fields rather than forcing prose parsing.
