# v0.47 Review Exercises Dry-Run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development to lock the no-write preview contract before implementation. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `review exercises --dry-run` so operators and wrappers can preview targeted review exercise drafts before writing generated exercise files.

**Architecture:** Extract the existing targeted review exercise selection into a shared path that can either write missing drafts or return the would-be `ExerciseDraft` rows without writing. Keep normal `review exercises` and `review exercises --json` writer semantics unchanged. Dry-run mode supports prose and JSON output, and must not create generated exercise files.

**Tech Stack:** Python argparse, existing `ExerciseDraft` records, existing review-schedule selection logic, `json`, `unittest`, deterministic temporary project fixtures.

---

## File Map

- Modify `tests/test_state_eval.py`: add RED coverage for `review exercises --dry-run`, no-write behavior, preview rows, and `--dry-run --json`.
- Modify `socrates/artifacts.py`: expose a no-write targeted review exercise preview helper that reuses writer selection.
- Modify `socrates/cli.py`: add `--dry-run` to `review exercises`, route preview mode through the no-write helper, and support prose plus JSON output.
- Modify docs after GREEN: `README.md`, `docs/README.md`, `docs/development_log.md`, `docs/development_roadmap.md`.
- Modify this plan as checklist state changes.
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`.

## Acceptance Criteria

- `python -m socrates review exercises --project <project> --due-by 2026-06-04 --dry-run` exits 0, reports the targeted review exercise rows that would be generated, and does not create files under `05_exercises/generated/`.
- `python -m socrates review exercises --project <project> --due-by 2026-06-04 --dry-run --json` emits valid deterministic JSON with `schema_version: 1`, `quality_boundary: deterministic_review_exercise_preview`, `project`, `due_by`, `priority_filter`, `dry_run: true`, `generated_count`, and `generated_exercises`.
- Each preview row includes `id`, `type`, `difficulty`, and `path`.
- Normal write mode, including `--json`, remains unchanged and still writes generated exercise drafts when missing.
- Existing invalid `--due-by` and corrupt `learning_state.json` handling remains clean and non-traceback.
- The command boundary remains explicit: dry-run is a no-write targeted review exercise preview, not a writer, read-only ledger, scheduler, planner, tutor, report refresh, LLM call, exercise validation, approval, grading, or learning-state mutation.

---

### Task 1: RED Review Exercises Dry-Run Tests

**Files:**
- Modify: `tests/test_state_eval.py`

- [x] **Step 1: Add failing prose dry-run test**

Create a project with two scheduled review items, run `review exercises --due-by 2026-06-04 --dry-run`, assert preview output and row text, and assert no generated exercise draft files were created.

- [x] **Step 2: Add failing JSON dry-run test**

Run `review exercises --due-by 2026-06-07 --priority high --dry-run --json`, assert preview metadata and rows, and assert no generated exercise draft files were created.

- [x] **Step 3: Run RED**

Run:

```powershell
python -m unittest tests.test_state_eval
```

Expected: fail because `review exercises --dry-run` is not registered yet.

---

### Task 2: Add No-Write Preview

**Files:**
- Modify: `socrates/artifacts.py`
- Modify: `socrates/cli.py`

- [x] **Step 1: Extract shared selection**

Refactor the targeted review exercise writer so preview and writer modes share the same schedule filtering, IDs, difficulty, and paths.

- [x] **Step 2: Expose preview helper**

Add a public helper that returns the would-be `ExerciseDraft` rows without writing generated files.

- [x] **Step 3: Register `--dry-run`**

Add `--dry-run` to the `review exercises` parser. Keep existing `--due-by`, `--priority`, and `--json` behavior.

- [x] **Step 4: Route preview output**

When `args.dry_run` is true, call the preview helper. For JSON, print `quality_boundary: deterministic_review_exercise_preview` with `dry_run: true`; for prose, print a no-write preview line and generated exercise rows.

- [x] **Step 5: Run GREEN**

Run:

```powershell
python -m unittest tests.test_state_eval
```

Expected: tests OK.

---

### Task 3: Docs, Verification, Commit, and Wiki

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/development_log.md`
- Modify: `docs/development_roadmap.md`
- Modify: `docs/superpowers/plans/2026-06-04-v47-review-exercises-dry-run.md`
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.47**

Document `review exercises --dry-run` as a no-write targeted review exercise preview, including `--dry-run --json` for wrappers.

- [x] **Step 2: Run verification**

Run:

```powershell
python -m unittest tests.test_state_eval tests.test_status_quality_summary tests.test_learning_queue tests.test_reports
python -m unittest discover -s tests
python -m compileall socrates
git diff --check
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
bash scripts/check.sh
```

- [x] **Step 3: Commit with Lore protocol**

Commit the v0.47 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.47 commit id, verification evidence, no-write dry-run boundary, and the reusable lesson that exercise preview modes should share writer selection while proving generated files were not created.
