# v0.46 Review Exercises JSON Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development before implementation. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `review exercises --json` so wrappers, UI prototypes, and plugins can consume targeted review exercise writer results without parsing prose.

**Architecture:** Keep the existing `review exercises` writer semantics. JSON mode still calls `generate_targeted_review_exercise_drafts(...)` and then serializes the returned targeted exercise rows with explicit filter metadata. The command remains a writer, not a dry-run or read-only exercise ledger.

**Tech Stack:** Python argparse, existing `ExerciseDraft` records, `json`, `unittest`, deterministic temporary project fixtures.

---

## File Map

- Modify `tests/test_state_eval.py`: add RED coverage for `review exercises --json`, filter metadata, generated exercise rows, writer side effects, and corrupt JSON compatibility.
- Modify `socrates/cli.py`: add `--json` to `review exercises`, emit deterministic writer-result JSON, and keep prose mode unchanged.
- Modify docs after GREEN: `README.md`, `docs/README.md`, `docs/development_log.md`, `docs/development_roadmap.md`.
- Modify this plan as checklist state changes.
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`.

## Acceptance Criteria

- `python -m socrates review exercises --project <project> --due-by 2026-06-04 --json` exits 0, writes the same targeted review exercise draft as prose mode, and emits valid deterministic JSON.
- The JSON payload includes `schema_version: 1`, `quality_boundary: deterministic_review_exercise_writer`, `project`, `due_by`, `priority_filter`, `generated_count`, and `generated_exercises`.
- Each generated exercise row includes `id`, `type`, `difficulty`, and `path`.
- `--priority high --json` preserves the same filtering behavior as prose mode.
- Existing invalid `--due-by` and corrupt `learning_state.json` handling remains clean and non-traceback.
- The command boundary remains explicit: JSON output describes the existing exercise writer result; it is not a dry-run, read-only ledger, scheduler, planner, tutor, report refresh, LLM call, exercise validation, approval, grading, or learning-state mutation.

---

### Task 1: RED Review Exercises JSON Tests

**Files:**
- Modify: `tests/test_state_eval.py`

- [x] **Step 1: Add failing JSON writer-result test**

Create a project with two scheduled review items, run `review exercises --due-by 2026-06-04 --json`, assert deterministic payload metadata and one generated exercise row, and assert the matching draft file exists while the later item is not written.

- [x] **Step 2: Add failing JSON priority-filter test**

Run `review exercises --due-by 2026-06-07 --priority high --json`, assert only the high-priority exercise row appears and only that draft file exists.

- [x] **Step 3: Run RED**

Run:

```powershell
python -m unittest tests.test_state_eval
```

Expected: fail because `review exercises --json` is not registered yet.

---

### Task 2: Add Writer-Result JSON

**Files:**
- Modify: `socrates/cli.py`

- [x] **Step 1: Register `--json`**

Add `--json` to the `review exercises` parser. Keep existing `--due-by` and `--priority` behavior.

- [x] **Step 2: Serialize writer result**

After `generate_targeted_review_exercise_drafts(...)` returns, emit `quality_boundary: deterministic_review_exercise_writer` with filter metadata, generated count, and generated exercise rows when `args.json` is true.

- [x] **Step 3: Preserve prose behavior**

Keep the current prose output unchanged when `--json` is absent, including existing clean error handling.

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
- Modify: `docs/superpowers/plans/2026-06-04-v46-review-exercises-json.md`
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.46**

Document `review exercises --json` as a structured writer-result payload, not a dry-run or read-only exercise ledger.

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

Commit the v0.46 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.46 commit id, verification evidence, writer-result JSON boundary, and the reusable lesson that writer JSON payloads should expose returned artifact rows without changing side-effect semantics.
