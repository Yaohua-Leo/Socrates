# v0.39 Multi-Project Brief Refresh Project-ID Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development to lock targeted writer behavior before implementation. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `projects refresh-briefs --project-id <id>` so operators can refresh or preview specific child projects by id after inspecting collection resume or dry-run output.

**Architecture:** Extend `refresh_project_briefs_payload(root_path, *, dry_run=False, limit=None, project_ids=None)` as the single selection source. Preserve `selected`, `refreshed`, `deferred`, and `skipped`; add `project_ids`, `excluded_count`, and `excluded` rows for child projects filtered out by the requested ids. Reject unknown project ids before any write.

**Tech Stack:** Python argparse, existing Socrates project brief refresh payload, `json`, `unittest`, deterministic temporary project fixtures.

---

## File Map

- Modify `tests/test_project_index.py`: add RED coverage for targeted writer JSON and unknown project-id rejection.
- Modify `socrates/project_brief_refresh.py`: add project-id validation, filter-aware selection, and excluded rows/Markdown rendering.
- Modify `socrates/cli.py`: add repeatable `--project-id`, catch unknown-id validation errors, and pass ids to Markdown/JSON payload helpers.
- Modify docs after GREEN: `README.md`, `docs/README.md`, `docs/development_log.md`, `docs/development_roadmap.md`.
- Modify this plan as checklist state changes.
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`.

## Acceptance Criteria

- `python -m socrates projects refresh-briefs --root <root> --project-id ring_theory --json` writes only the matching refresh-needed child project.
- Nonmatching child projects appear in `excluded` with `reason: project_id_filter`, not in `skipped`.
- A matching ready child project appears in `skipped` with `reason: resume_state_ready`.
- Unknown project ids fail before writes with exit code 2 and a clear `unknown project id` error.
- `--project-id` composes with existing `--dry-run`, `--json`, and `--limit` through the shared payload contract.
- Existing no-filter Markdown and JSON behavior remains compatible.
- The command boundary remains explicit: project-id filtering changes target selection only, not readiness rules, scoring, LLM usage, report refresh, repairs, project discovery, or learning-state truth.

---

### Task 1: RED Project-ID Tests

**Files:**
- Modify: `tests/test_project_index.py`

- [x] **Step 1: Add failing targeted writer JSON test**

Create a collection with one ready child and two refresh-needed children. Run `projects refresh-briefs --root <root> --project-id ring_theory --json` and assert:

1. The payload records `project_ids: ["ring_theory"]`, `selected_count: 1`, `refreshed_count: 1`, `excluded_count: 2`, `deferred_count: 0`, and `skipped_count: 0`.
2. The matching `ring_theory` project is selected/refreshed and receives brief artifacts plus a project-log entry.
3. The nonmatching ready and refresh-needed projects appear in `excluded` with `reason: project_id_filter`.
4. The nonmatching refresh-needed project receives no artifacts or project-log entry.
5. The ready project's project log still has exactly one `Generated study brief.` entry.
6. No root `socrates_projects.json` is written.

- [x] **Step 2: Add failing unknown project-id test**

Run `projects refresh-briefs --root <root> --project-id missing_project` over a collection containing a refresh-needed project and assert exit code 2, stderr contains `unknown project id: missing_project`, and no child or root artifacts are written.

- [x] **Step 3: Run RED**

Run:

```powershell
python -m unittest tests.test_project_index
```

Expected: fail because `projects refresh-briefs --project-id` is not registered yet.

---

### Task 2: Add Project-ID Filtering

**Files:**
- Modify: `socrates/project_brief_refresh.py`
- Modify: `socrates/cli.py`

- [x] **Step 1: Add payload filter support**

Extend `refresh_project_briefs_payload` to accept `project_ids`. Normalize duplicate ids while preserving requested order, validate all requested ids against discovered projects before any writes, and add:

- `project_ids`
- `excluded_count`
- `excluded`

Nonmatching rows should include `reason: project_id_filter`.

- [x] **Step 2: Render Markdown excluded output**

Add summary `Project ids` and `Excluded` rows plus a `## Excluded Projects` section. Keep existing selected/refreshed/deferred/skipped sections.

- [x] **Step 3: Register and route `--project-id`**

Add repeatable `--project-id` to `projects refresh-briefs`, catch payload `ValueError` in `_handle_projects_refresh_briefs`, and pass project ids to both JSON and Markdown helpers.

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
- Modify: `docs/superpowers/plans/2026-06-04-v39-projects-refresh-briefs-project-id.md`
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.39**

Document `projects refresh-briefs --project-id <id>` as a targeted filter over explicit collection writer selection, not a new readiness rule, scanner, queue, or hidden child-project discovery mode.

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

Commit the v0.39 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.39 commit id, verification evidence, targeted refresh boundary, and the reusable lesson that writer filters should make nonmatching rows explicit and reject unknown targets before mutation.
