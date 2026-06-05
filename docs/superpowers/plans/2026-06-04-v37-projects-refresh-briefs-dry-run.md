# v0.37 Multi-Project Brief Refresh Dry-Run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development to lock the no-write behavior before implementation. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `projects refresh-briefs --dry-run` so operators and wrappers can preview which child projects would receive refreshed study briefs without mutating any child project.

**Architecture:** Extend `refresh_project_briefs_payload(root_path, *, dry_run=False)` as the single selection source. Add additive payload fields for mode and selected rows while preserving the existing writer fields. Route Markdown and JSON output through the same payload so dry-run changes only write behavior, not selection policy.

**Tech Stack:** Python argparse, existing Socrates project brief refresh payload, `json`, `unittest`, deterministic temporary project fixtures.

---

## File Map

- Modify `tests/test_project_index.py`: add RED coverage for Markdown and JSON dry-run previews that do not write child brief artifacts, manifests, project logs, or root indexes.
- Modify `socrates/project_brief_refresh.py`: add a `dry_run` payload mode, selected preview rows, and Markdown dry-run rendering.
- Modify `socrates/cli.py`: add `--dry-run` to `projects refresh-briefs` and pass it to Markdown/JSON payload helpers.
- Modify docs after GREEN: `README.md`, `docs/README.md`, `docs/development_log.md`, `docs/development_roadmap.md`.
- Modify this plan as checklist state changes.
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`.

## Acceptance Criteria

- `python -m socrates projects refresh-briefs --root <root> --dry-run` reports `Mode: dry_run`, selected refresh-needed child projects, `Refreshed: 0`, and skipped ready projects.
- `python -m socrates projects refresh-briefs --root <root> --dry-run --json` emits deterministic JSON with `mode: dry_run`, `dry_run: true`, `selected_count`, `selected`, `refreshed_count: 0`, `refreshed: []`, and existing skipped rows.
- Dry-run mode must not create `07_exports/briefs/study_brief.md`, `07_exports/briefs/study_brief_manifest.json`, child project-log entries, or root `socrates_projects.json`.
- Non-dry-run Markdown and JSON outputs still write the same selected child study brief artifacts as v0.36.
- The command boundary remains explicit: dry-run changes write behavior only, not selection semantics, scoring, LLM usage, report refresh, repairs, or learning-state truth.

---

### Task 1: RED Dry-Run Tests

**Files:**
- Modify: `tests/test_project_index.py`

- [x] **Step 1: Add failing Markdown dry-run test**

Add a test that:

1. Creates a `SocratesProjects` root with one ready project and one refresh-needed project.
2. Generates a current brief for the ready project before running the batch command.
3. Runs `projects refresh-briefs --root <root> --dry-run`.
4. Asserts Markdown summary mode is `dry_run`, selected count is 1, refreshed count is 0, and skipped count is 1.
5. Asserts the refresh-needed project is listed as selected with its would-be `07_exports/briefs/study_brief.md` path.
6. Asserts refreshed projects are `none`.
7. Asserts no fresh project brief, manifest, or project-log entry was written.
8. Asserts the ready project's project log still has exactly one `Generated study brief.` entry.
9. Asserts no root `socrates_projects.json` is written.

- [x] **Step 2: Add failing JSON dry-run test**

Add a test that runs `projects refresh-briefs --root <root> --dry-run --json` and asserts the structured payload mirrors the Markdown dry-run boundary: selected row present, refreshed empty, skipped ready project present, and no writes.

- [x] **Step 3: Run RED**

Run:

```powershell
python -m unittest tests.test_project_index
```

Expected: fail because `projects refresh-briefs --dry-run` is not registered yet.

---

### Task 2: Add Dry-Run Mode

**Files:**
- Modify: `socrates/project_brief_refresh.py`
- Modify: `socrates/cli.py`

- [x] **Step 1: Add payload mode and selected rows**

Extend `refresh_project_briefs_payload(root_path, *, dry_run=False)` to include:

- `mode`: `write` or `dry_run`
- `dry_run`: boolean
- `selected_count`: count of refresh-needed child projects
- `selected`: refresh-needed child rows with would-be `brief_path`

In dry-run mode, do not call `generate_study_brief`.

- [x] **Step 2: Render Markdown preview**

Extend `format_project_brief_refresh(root_path, *, dry_run=False)` to render:

- `Mode`
- `Selected`
- `Refreshed`
- `Skipped`
- `Selected Projects`
- `Refreshed Projects`
- `Skipped Projects`
- mode-specific boundary text

- [x] **Step 3: Register and route `--dry-run`**

Add `--dry-run` to `projects refresh-briefs` and pass `dry_run=args.dry_run` to both JSON and Markdown helpers.

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
- Modify: `docs/superpowers/plans/2026-06-04-v37-projects-refresh-briefs-dry-run.md`
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.37**

Document `projects refresh-briefs --dry-run` as a preview mode for the same explicit collection writer selection, not a read-only resume command, report refresh, new selector, or LLM/tooling action.

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

Commit the v0.37 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.37 commit id, verification evidence, dry-run preview boundary, and the reusable lesson that preview modes should expose the same selection policy while making non-writes explicit.
