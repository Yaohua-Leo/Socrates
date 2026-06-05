# v0.38 Multi-Project Brief Refresh Limit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development to lock batch-control behavior before implementation. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `projects refresh-briefs --limit N` so operators can refresh a bounded number of selected child projects after previewing a collection root.

**Architecture:** Extend `refresh_project_briefs_payload(root_path, *, dry_run=False, limit=None)` as the single selection source. Preserve `selected`, `refreshed`, and `skipped`; add `limit`, `deferred_count`, and `deferred` rows for refresh-needed projects that match the writer selection but are held back by the limit.

**Tech Stack:** Python argparse, existing Socrates project brief refresh payload, `json`, `unittest`, deterministic temporary project fixtures.

---

## File Map

- Modify `tests/test_project_index.py`: add RED coverage for limited writer JSON, limited dry-run Markdown, and non-positive limit rejection.
- Modify `socrates/project_brief_refresh.py`: add limit validation, limit-aware selection, and deferred rows/Markdown rendering.
- Modify `socrates/cli.py`: add `--limit` to `projects refresh-briefs`, reject non-positive values, and pass the limit to Markdown/JSON payload helpers.
- Modify docs after GREEN: `README.md`, `docs/README.md`, `docs/development_log.md`, `docs/development_roadmap.md`.
- Modify this plan as checklist state changes.
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`.

## Acceptance Criteria

- `python -m socrates projects refresh-briefs --root <root> --limit 1 --json` writes only the first deterministic refresh-needed child project and reports later refresh-needed projects as `deferred` with `reason: limit_reached`.
- `python -m socrates projects refresh-briefs --root <root> --dry-run --limit 1` previews only the first selected refresh-needed child project, reports over-limit refresh-needed projects as deferred, and writes nothing.
- Ready projects remain in `skipped` with `reason: resume_state_ready`.
- Deferred projects must not receive study brief artifacts, manifests, or `Generated study brief.` project-log entries.
- `--limit 0` and negative limits fail before writes with a clear error.
- Existing no-limit Markdown and JSON behavior remains compatible.
- The command boundary remains explicit: limit changes batch size only, not project discovery, readiness rules, scoring, LLM usage, report refresh, repairs, or learning-state truth.

---

### Task 1: RED Limit Tests

**Files:**
- Modify: `tests/test_project_index.py`

- [x] **Step 1: Add failing limited writer JSON test**

Create a collection with one ready child and two refresh-needed children. Run `projects refresh-briefs --root <root> --limit 1 --json` and assert:

1. The payload records `limit: 1`, `selected_count: 1`, `refreshed_count: 1`, `deferred_count: 1`, and `skipped_count: 1`.
2. The first deterministic refresh-needed project is selected/refreshed and receives brief artifacts plus a project-log entry.
3. The second refresh-needed project appears in `deferred` with `reason: limit_reached` and receives no artifacts or project-log entry.
4. The ready project remains skipped and receives no extra project-log entry.
5. No root `socrates_projects.json` is written.

- [x] **Step 2: Add failing limited dry-run Markdown test**

Run `projects refresh-briefs --root <root> --dry-run --limit 1` over the same fixture shape and assert:

1. Markdown reports `Mode: dry_run`, `Limit: 1`, `Selected: 1`, `Refreshed: 0`, `Deferred: 1`, and `Skipped: 1`.
2. The first refresh-needed project appears under selected projects.
3. The second refresh-needed project appears under deferred projects.
4. Neither refresh-needed project receives brief artifacts, manifests, or project-log entries.

- [x] **Step 3: Add failing non-positive limit test**

Run `projects refresh-briefs --root <root> --limit 0` and assert exit code 2, stderr contains `limit must be positive`, and no root index is written.

- [x] **Step 4: Run RED**

Run:

```powershell
python -m unittest tests.test_project_index
```

Expected: fail because `projects refresh-briefs --limit` is not registered yet.

---

### Task 2: Add Limit and Deferred Rows

**Files:**
- Modify: `socrates/project_brief_refresh.py`
- Modify: `socrates/cli.py`

- [x] **Step 1: Add payload limit support**

Extend `refresh_project_briefs_payload` to accept `limit: int | None = None`, reject non-positive limits, and add:

- `limit`
- `deferred_count`
- `deferred`

Over-limit refresh-needed rows should include the would-be `brief_path` plus `reason: limit_reached`.

- [x] **Step 2: Render Markdown limit/deferred output**

Add summary `Limit` and `Deferred` rows plus a `## Deferred Projects` section. Keep existing selected/refreshed/skipped sections.

- [x] **Step 3: Register and route `--limit`**

Add `--limit` to `projects refresh-briefs`, reject non-positive values in `_handle_projects_refresh_briefs`, and pass it to payload/formatter helpers.

- [x] **Step 4: Run GREEN**

Run:

```powershell
python -m unittest tests.test_project_index tests.test_resume tests.test_study_brief
```

Expected: tests OK.

---

### Task 3: Docs, Verification, Commit, and Wiki

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/development_log.md`
- Modify: `docs/development_roadmap.md`
- Modify: `docs/superpowers/plans/2026-06-04-v38-projects-refresh-briefs-limit.md`
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.38**

Document `projects refresh-briefs --limit N` as a batch-size control over the same writer selection, not a new selector, readiness rule, queue, scanner, or automation layer.

- [x] **Step 2: Run verification**

Run:

```powershell
python -m unittest tests.test_project_index tests.test_resume tests.test_study_brief tests.test_dashboard tests.test_status_quality_summary tests.test_learning_queue
python -m unittest discover -s tests
python -m compileall socrates
git diff --check
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
bash scripts/check.sh
```

- [x] **Step 3: Commit with Lore protocol**

Commit the v0.38 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.38 commit id, verification evidence, deferred-row boundary, and the reusable lesson that limited writers should make over-limit work explicit instead of hiding it as skipped or silently ignoring it.
