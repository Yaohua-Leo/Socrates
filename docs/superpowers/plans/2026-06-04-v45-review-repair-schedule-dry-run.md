# v0.45 Review Repair-Schedule Dry-Run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development to lock the no-write repair preview contract before implementation. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `review repair-schedule --dry-run` so operators and wrappers can preview review-schedule repairs before mutating `learning_state.json` or rewriting `review_schedule.md`.

**Architecture:** Extract the existing repair computation into a public preview helper that returns repaired count plus the would-be repaired rows without writing. Keep the existing writer path for normal `review repair-schedule`. In dry-run mode, the CLI prints a preview result and supports `--json`; dry-run must not write `00_meta/learning_state.json` or `02_learning_plan/review_schedule.md`.

**Tech Stack:** Python argparse, existing Socrates review schedule repair computation, `json`, `unittest`, deterministic temporary project fixtures.

---

## File Map

- Modify `tests/test_state_eval.py`: add RED coverage for `review repair-schedule --dry-run`, no-write behavior, preview row fields, and `--dry-run --json`.
- Modify `socrates/state.py`: expose a repair preview helper that reuses `_repaired_review_items(...)` without writing.
- Modify `socrates/cli.py`: add `--dry-run` to `review repair-schedule`, route preview mode through the no-write helper, and support Markdown/prose plus JSON output.
- Modify docs after GREEN: `README.md`, `docs/README.md`, `docs/development_log.md`, `docs/development_roadmap.md`.
- Modify this plan as checklist state changes.
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`.

## Acceptance Criteria

- `python -m socrates review repair-schedule --project <project> --as-of 2026-06-04 --dry-run` exits 0, reports the number of schedule rows that would be repaired, and does not write `00_meta/learning_state.json` or `02_learning_plan/review_schedule.md`.
- `python -m socrates review repair-schedule --project <project> --as-of 2026-06-04 --dry-run --json` emits valid deterministic JSON with `schema_version: 1`, `quality_boundary: deterministic_review_schedule_repair_preview`, `project`, `as_of`, `dry_run: true`, `repaired_count`, and `scheduled_reviews`.
- Each preview row includes `concept`, `priority`, `due`, `scheduled_for`, `reason`, and `repair`.
- Normal write mode, including `--json`, remains unchanged and still mutates persisted repair artifacts.
- Existing clean error handling for invalid dates or corrupt learning state remains compatible.
- The command boundary remains explicit: dry-run is a no-write repair preview, not a scheduler, tutor, planner, exercise generator, report refresh, LLM call, or learning-state mutation.

---

### Task 1: RED Repair Dry-Run Tests

**Files:**
- Modify: `tests/test_state_eval.py`

- [x] **Step 1: Add failing prose dry-run test**

Create a project with missing and invalid persisted review schedule dates. Snapshot `learning_state.json`, assert `review_schedule.md` is absent, run `review repair-schedule --dry-run`, and assert preview output while snapshots and artifacts remain unchanged.

- [x] **Step 2: Add failing JSON dry-run test**

Use the same repair fixture, run `review repair-schedule --dry-run --json`, parse stdout, assert dry-run metadata and preview rows, and assert no writes.

- [x] **Step 3: Run RED**

Run:

```powershell
python -m unittest tests.test_state_eval
```

Expected: fail because `review repair-schedule --dry-run` is not registered yet.

---

### Task 2: Add No-Write Preview

**Files:**
- Modify: `socrates/state.py`
- Modify: `socrates/cli.py`

- [x] **Step 1: Expose preview helper**

Add a small public helper that loads state, calls `_repaired_review_items(...)`, and returns repaired count plus would-be repaired rows without writing files.

- [x] **Step 2: Register `--dry-run`**

Add `--dry-run` to the `review repair-schedule` parser. Keep existing `--as-of` and `--json` behavior.

- [x] **Step 3: Route preview output**

When `args.dry_run` is true, call the preview helper. For JSON, print `quality_boundary: deterministic_review_schedule_repair_preview` with `dry_run: true`; for prose, print a no-write preview line and the same row summaries.

- [x] **Step 4: Run GREEN**

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
- Modify: `docs/superpowers/plans/2026-06-04-v45-review-repair-schedule-dry-run.md`
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.45**

Document `review repair-schedule --dry-run` as a no-write repair preview, including `--dry-run --json` for wrappers.

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

Commit the v0.45 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.45 commit id, verification evidence, no-write dry-run boundary, and the reusable lesson that preview modes should share repair computation while proving no persisted artifacts changed.
