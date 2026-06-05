# v0.55 Status JSON Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development before implementation. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `status --json` so wrappers, UI prototypes, plugins, and automation can consume the central deterministic project status without parsing prose.

**Architecture:** Build a structured read-only status payload from the same readers already used by prose `status`. JSON mode must not generate briefs, refresh reports, run repairs, call an LLM, score learning, approve artifacts, or mutate project state. Prose status should render from the same payload to reduce drift.

**Tech Stack:** Python argparse, existing status readers and queue/status helpers, shared project-title helper, `json`, `unittest`, deterministic temporary project fixtures.

---

## File Map

- Modify `tests/test_status_quality_summary.py`: add RED coverage for `status --json`, invalid manifest serialization, and no-write behavior.
- Modify `socrates/cli.py`: add `--json` to `status`, build a deterministic status payload, and render prose status from that payload.
- Modify docs after GREEN: `README.md`, `docs/README.md`, `docs/development_log.md`, `docs/development_roadmap.md`.
- Modify this plan as checklist state changes.
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`.

## Acceptance Criteria

- `python -m socrates status --project <project> --json` exits 0 and emits valid deterministic JSON.
- The payload includes `schema_version: 1`, `quality_boundary: deterministic_project_status`, `project`, `root`, `current_phase`, `counts`, `reference_kb`, `report_history`, `study_brief`, `queue`, `quality`, `session_score`, `session_closeout`, `multi_session_regression`, `next_session_plan`, `benchmark`, and `misconceptions`.
- Missing/not-run and invalid manifest semantics continue to match prose `status`.
- Prose `status` output remains stable.
- JSON mode is read-only and does not write project logs, reports, briefs, learning state, queue artifacts, or any project file.

---

### Task 1: RED Status JSON Tests

**Files:**
- Modify: `tests/test_status_quality_summary.py`

- [x] **Step 1: Add failing empty-project JSON test**

Run `status --json` on an empty project, assert payload metadata, core counts, not-run status fields, no prose output, and project file tree unchanged.

- [x] **Step 2: Add failing invalid-manifest JSON test**

Run `status --json` with corrupt quality, closeout, and regression manifests. Assert the structured payload reports invalid in the same places prose status already reports invalid.

- [x] **Step 3: Run RED**

Run:

```powershell
python -m unittest tests.test_status_quality_summary
```

Expected: fail because `status --json` is not registered yet.

---

### Task 2: Add Status JSON Payload

**Files:**
- Modify: `socrates/cli.py`

- [x] **Step 1: Register `--json`**

Add `--json` to the `status` parser and route JSON output through the status payload.

- [x] **Step 2: Build structured payload**

Create a deterministic status payload with project metadata, current phase, counts, reference KB, report history, study brief freshness, queue counts, quality status, session/workflow status, benchmark status, and misconception counts.

- [x] **Step 3: Preserve prose output**

Render the existing prose `status` lines from the payload without changing human-facing labels.

- [x] **Step 4: Preserve read-only boundary**

Ensure JSON mode reads only and does not write project artifacts.

- [x] **Step 5: Run GREEN**

Run:

```powershell
python -m unittest tests.test_status_quality_summary
```

Expected: tests OK.

---

### Task 3: Docs, Verification, Commit, and Wiki

**Files:**
- Modify `README.md`
- Modify `docs/README.md`
- Modify `docs/development_log.md`
- Modify `docs/development_roadmap.md`
- Modify `docs/superpowers/plans/2026-06-05-v55-status-json.md`
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.55**

Document `status --json` as a read-only structured project-status payload, not a writer, repair runner, score, or readiness-gate expansion.

- [x] **Step 2: Run verification**

Run:

```powershell
python -m unittest tests.test_status_quality_summary
python -m unittest tests.test_status_quality_summary tests.test_dashboard tests.test_study_brief tests.test_learning_queue tests.test_reports
python -m unittest discover -s tests
python -m compileall socrates
git diff --check
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
bash scripts/check.sh
```

- [ ] **Step 3: Commit with Lore protocol**

Commit the v0.55 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [ ] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.55 commit id, verification evidence, status JSON boundary, and the reusable lesson that central operator/readiness surfaces should expose structured payloads rather than forcing prose parsing.
