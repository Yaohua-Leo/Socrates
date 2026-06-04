# v0.44 Review Repair-Schedule JSON Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development to lock the writer JSON contract before implementation. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `review repair-schedule --json` so wrappers, UI prototypes, and plugins can consume review-schedule repair writer results without parsing the prose `Repaired N review schedule items: <path>` line.

**Architecture:** Preserve `review repair-schedule` as an explicit writer. Reuse `repair_review_schedule(...)` for repair behavior and side effects, then serialize the persisted schedule rows from `learning_state.json`. Keep Markdown/prose mode unchanged. The JSON flag changes output format only; it still repairs `00_meta/learning_state.json` and rewrites `02_learning_plan/review_schedule.md`.

**Tech Stack:** Python argparse, existing Socrates review schedule repairer, `json`, `unittest`, deterministic temporary project fixtures.

---

## File Map

- Modify `tests/test_state_eval.py`: add RED coverage for `review repair-schedule --json`, repaired count, schedule row fields, written artifacts, and no-op repairs.
- Modify `socrates/cli.py`: add `--json` to `review repair-schedule` and route writer results through a small payload helper that reuses persisted schedule rows.
- Modify docs after GREEN: `README.md`, `docs/README.md`, `docs/development_log.md`, `docs/development_roadmap.md`.
- Modify this plan as checklist state changes.
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`.

## Acceptance Criteria

- `python -m socrates review repair-schedule --project <project> --as-of 2026-06-04 --json` emits valid deterministic JSON with `schema_version: 1`, `quality_boundary: deterministic_review_schedule_repair_writer`, `project`, `as_of`, `repaired_count`, `schedule_path`, and `scheduled_reviews`.
- Each scheduled row includes `concept`, `priority`, `due`, `scheduled_for`, `reason`, and `repair`.
- JSON mode performs the same writer side effects as prose mode: it repairs missing or invalid persisted schedule dates, updates `00_meta/learning_state.json`, and rewrites `02_learning_plan/review_schedule.md`.
- No-op repairs produce `repaired_count: 0`, still return current scheduled rows, and still rewrite the schedule Markdown artifact through the existing repair writer.
- Existing prose `review repair-schedule` output and clean error handling for invalid dates or corrupt learning state remain compatible.
- The command boundary remains explicit: JSON output is a repair writer result payload, not a dry-run, read-only ledger, scheduler, tutor, planner, exercise generator, report refresh, LLM call, or learning-state truth beyond the existing repair write.

---

### Task 1: RED Repair-Writer JSON Tests

**Files:**
- Modify: `tests/test_state_eval.py`

- [x] **Step 1: Add failing repair JSON payload test**

Create a project with missing and invalid persisted review schedule dates. Run `review repair-schedule --project <project> --as-of 2026-06-04 --json`, parse stdout, and assert schema fields, repaired count, schedule path, row fields/order, and repaired persisted artifacts.

- [x] **Step 2: Add failing no-op repair JSON test**

Create a project with already valid review schedule rows. Run `review repair-schedule --project <project> --as-of 2026-06-04 --json`, assert `repaired_count: 0`, current rows are returned, and the schedule Markdown artifact is written.

- [x] **Step 3: Run RED**

Run:

```powershell
python -m unittest tests.test_state_eval
```

Expected: fail because `review repair-schedule --json` is not registered yet.

---

### Task 2: Add JSON Output

**Files:**
- Modify: `socrates/cli.py`

- [x] **Step 1: Register `--json`**

Add `--json` to the `review repair-schedule` parser as an output mode flag. Keep existing `--as-of` behavior.

- [x] **Step 2: Add payload helper**

After `repair_review_schedule(...)` succeeds, read the persisted schedule rows and return:

```python
{
    "schema_version": 1,
    "quality_boundary": "deterministic_review_schedule_repair_writer",
    "project": str(context.root),
    "as_of": as_of.isoformat(),
    "repaired_count": repaired_count,
    "schedule_path": str(schedule_path),
    "scheduled_reviews": [...],
}
```

- [x] **Step 3: Route JSON output**

In `_handle_review_repair_schedule`, print JSON with `indent=2` and `sort_keys=True` when `args.json` is true; otherwise keep the existing prose output.

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
- Modify: `docs/superpowers/plans/2026-06-04-v44-review-repair-schedule-json.md`
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.44**

Document `review repair-schedule --json` as a structured repair-writer result. Make clear that JSON output still repairs and rewrites the review schedule and is not a dry-run or read-only ledger.

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

Commit the v0.44 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.44 commit id, verification evidence, repair-writer JSON boundary, and the reusable lesson that repair writer JSON should expose repaired counts and post-write rows rather than requiring prose parsing.
