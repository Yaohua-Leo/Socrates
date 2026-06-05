# v0.43 Review Schedule JSON Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development to lock the writer JSON contract before implementation. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `review schedule --json` so wrappers, UI prototypes, and plugins can consume the schedule writer result without parsing the prose `Scheduled N review items: <path>` line.

**Architecture:** Preserve `review schedule` as an explicit writer. Reuse `build_review_schedule(...)` for selection and side effects, then read the persisted schedule rows from `learning_state.json` to build a structured output payload. Keep Markdown mode unchanged. The JSON flag changes output format only; it still writes `00_meta/learning_state.json` and `02_learning_plan/review_schedule.md`.

**Tech Stack:** Python argparse, existing Socrates review scheduler, `json`, `unittest`, deterministic temporary project fixtures.

---

## File Map

- Modify `tests/test_state_eval.py`: add RED coverage for `review schedule --json`, writer payload fields, schedule row fields, artifacts written, and empty schedule output.
- Modify `socrates/cli.py`: add `--json` to `review schedule`, route writer results through a small payload helper, and reuse persisted schedule rows.
- Modify docs after GREEN: `README.md`, `docs/README.md`, `docs/development_log.md`, `docs/development_roadmap.md`.
- Modify this plan as checklist state changes.
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`.

## Acceptance Criteria

- `python -m socrates review schedule --project <project> --threshold 0.8 --as-of 2026-06-04 --json` emits valid deterministic JSON with `schema_version: 1`, `quality_boundary: deterministic_review_schedule_writer`, `project`, `as_of`, `threshold`, `scheduled_count`, `schedule_path`, and `scheduled_reviews`.
- Each scheduled row includes `concept`, `priority`, `due`, `scheduled_for`, `reason`, and `repair`.
- The JSON command performs the same writer side effects as Markdown mode: it updates `00_meta/learning_state.json` and writes `02_learning_plan/review_schedule.md`.
- Empty schedules produce `scheduled_count: 0`, an empty `scheduled_reviews` list, and still write the schedule Markdown artifact.
- Existing Markdown `review schedule` output and clean error handling for invalid dates, nonfinite thresholds, or corrupt learning state remain compatible.
- The command boundary remains explicit: JSON output is a writer result payload, not a dry-run, read-only ledger, tutor, planner, repair command, exercise generator, report refresh, LLM call, or learning-state truth beyond the existing scheduler write.

---

### Task 1: RED Schedule-Writer JSON Tests

**Files:**
- Modify: `tests/test_state_eval.py`

- [x] **Step 1: Add failing writer JSON payload test**

Create a project with weak concepts, run `review schedule --project <project> --threshold 0.8 --as-of 2026-06-04 --json`, parse stdout, and assert schema fields, output-only prose absence, row fields/order, schedule path, and persisted schedule artifacts.

- [x] **Step 2: Add failing empty schedule JSON test**

Create a project with no weak concepts or active misconceptions, run `review schedule --project <project> --as-of 2026-06-04 --json`, and assert an empty deterministic payload while confirming `review_schedule.md` is written.

- [x] **Step 3: Run RED**

Run:

```powershell
python -m unittest tests.test_state_eval
```

Expected: fail because `review schedule --json` is not registered yet.

---

### Task 2: Add JSON Output

**Files:**
- Modify: `socrates/cli.py`

- [x] **Step 1: Register `--json`**

Add `--json` to the `review schedule` parser as an output mode flag. Keep existing `--threshold` and `--as-of` behavior.

- [x] **Step 2: Add payload helper**

After `build_review_schedule(...)` succeeds, read the persisted schedule rows and return:

```python
{
    "schema_version": 1,
    "quality_boundary": "deterministic_review_schedule_writer",
    "project": str(context.root),
    "as_of": as_of.isoformat(),
    "threshold": threshold,
    "scheduled_count": len(rows),
    "schedule_path": str(schedule_path),
    "scheduled_reviews": [...],
}
```

- [x] **Step 3: Route JSON output**

In `_handle_review_schedule`, print JSON with `indent=2` and `sort_keys=True` when `args.json` is true; otherwise keep the existing prose output.

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
- Modify: `docs/superpowers/plans/2026-06-04-v43-review-schedule-json.md`
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.43**

Document `review schedule --json` as a structured writer-result payload. Make clear that JSON output still writes the review schedule and is not a dry-run or read-only ledger.

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

Commit the v0.43 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.43 commit id, verification evidence, writer JSON boundary, and the reusable lesson that writer JSON payloads should describe the actual side effects rather than implying read-only behavior.
