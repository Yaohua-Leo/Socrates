# v0.48 Review Adjust-Plan JSON Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development before implementation. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `review adjust-plan --json` so wrappers, UI prototypes, and plugins can consume short-term-plan adjustment writer results without parsing prose.

**Architecture:** Keep existing `review adjust-plan` writer semantics. JSON mode still calls `adjust_short_term_plan_from_review_schedule(...)`, rewrites `02_learning_plan/short_term_plan.md`, and then serializes the persisted review adjustment rows with the written plan path. The command remains a writer, not a dry-run, read-only plan ledger, scheduler, tutor, report refresh, or LLM call.

**Tech Stack:** Python argparse, existing learning-plan writer, `json`, `unittest`, deterministic temporary project fixtures.

---

## File Map

- Modify `tests/test_learning_plan.py`: add RED coverage for `review adjust-plan --json`, writer side effects, returned path, row serialization, and corrupt JSON compatibility.
- Modify `socrates/cli.py`: add `--json` to `review adjust-plan`, emit deterministic writer-result JSON, and keep prose mode unchanged.
- Modify docs after GREEN: `README.md`, `docs/README.md`, `docs/development_log.md`, `docs/development_roadmap.md`.
- Modify this plan as checklist state changes.
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`.

## Acceptance Criteria

- `python -m socrates review adjust-plan --project <project> --json` exits 0, writes the same short-term review-adjustment section as prose mode, and emits valid deterministic JSON.
- The JSON payload includes `schema_version: 1`, `quality_boundary: deterministic_review_adjust_plan_writer`, `project`, `short_term_plan_path`, `adjustment_count`, and `review_adjustments`.
- Each review-adjustment row includes `concept`, `scheduled_for`, `priority`, `due`, `reason`, and `repair`.
- Prose mode remains unchanged and still prints `Adjusted short-term plan: <path>`.
- Corrupt `learning_state.json` handling remains clean and non-traceback, including in `--json` mode.
- The command boundary remains explicit: JSON output describes the existing short-term-plan writer result; it is not a dry-run, scheduler, exercise generator, tutor, report refresh, LLM call, plan approval, or learning-state mutation.

---

### Task 1: RED Review Adjust-Plan JSON Tests

**Files:**
- Modify: `tests/test_learning_plan.py`

- [x] **Step 1: Add failing JSON writer-result test**

Create a project with a scheduled review item, run `review adjust-plan --json`, assert deterministic payload metadata and row fields, and assert the matching short-term plan section was written.

- [x] **Step 2: Add failing corrupt-state JSON compatibility test**

Run `review adjust-plan --json` with invalid `learning_state.json`, assert exit 1, no stdout, clean stderr, and no short-term-plan rewrite.

- [x] **Step 3: Run RED**

Run:

```powershell
python -m unittest tests.test_learning_plan
```

Expected: fail because `review adjust-plan --json` is not registered yet.

---

### Task 2: Add Writer-Result JSON

**Files:**
- Modify: `socrates/cli.py`

- [x] **Step 1: Register `--json`**

Add `--json` to the `review adjust-plan` parser. Keep existing `--project` behavior.

- [x] **Step 2: Serialize writer result**

After `adjust_short_term_plan_from_review_schedule(...)` returns, emit `quality_boundary: deterministic_review_adjust_plan_writer` with project path, short-term plan path, adjustment count, and persisted review adjustment rows when `args.json` is true.

- [x] **Step 3: Preserve prose behavior**

Keep the current prose output unchanged when `--json` is absent, including existing clean error handling.

- [x] **Step 4: Run GREEN**

Run:

```powershell
python -m unittest tests.test_learning_plan
```

Expected: tests OK.

---

### Task 3: Docs, Verification, Commit, and Wiki

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/development_log.md`
- Modify: `docs/development_roadmap.md`
- Modify: `docs/superpowers/plans/2026-06-04-v48-review-adjust-plan-json.md`
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.48**

Document `review adjust-plan --json` as a structured writer-result payload, not a dry-run or read-only plan ledger.

- [x] **Step 2: Run verification**

Run:

```powershell
python -m unittest tests.test_learning_plan
python -m unittest tests.test_learning_plan tests.test_state_eval tests.test_status_quality_summary tests.test_learning_queue tests.test_reports
python -m unittest discover -s tests
python -m compileall socrates
git diff --check
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
bash scripts/check.sh
```

- [x] **Step 3: Commit with Lore protocol**

Commit the v0.48 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.48 commit id, verification evidence, writer-result JSON boundary, and the reusable lesson that plan-writer JSON payloads should serialize persisted writer evidence rather than an uncommitted intent.
