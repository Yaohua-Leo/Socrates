# v0.49 Review Adjust-Plan Dry-Run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development to lock the no-write preview contract before implementation. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `review adjust-plan --dry-run` so operators and wrappers can preview short-term-plan review adjustments before rewriting `02_learning_plan/short_term_plan.md`.

**Architecture:** Reuse the same persisted review-schedule rows that the writer uses for `review adjust-plan --json`, but route dry-run mode before the writer call. Dry-run mode supports prose and JSON output, reports the target short-term plan path, and must not rewrite plan files. Normal `review adjust-plan` and `review adjust-plan --json` writer semantics remain unchanged.

**Tech Stack:** Python argparse, existing review-schedule row serializer, existing learning-state readability guard, `json`, `unittest`, deterministic temporary project fixtures.

---

## File Map

- Modify `tests/test_learning_plan.py`: add RED coverage for `review adjust-plan --dry-run`, no-write behavior, preview rows, `--dry-run --json`, and corrupt JSON compatibility.
- Modify `socrates/cli.py`: add `--dry-run` to `review adjust-plan`, route preview mode before the writer, and support prose plus JSON output.
- Modify docs after GREEN: `README.md`, `docs/README.md`, `docs/development_log.md`, `docs/development_roadmap.md`.
- Modify this plan as checklist state changes.
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`.

## Acceptance Criteria

- `python -m socrates review adjust-plan --project <project> --dry-run` exits 0, reports the review adjustment rows that would be written, and leaves `02_learning_plan/short_term_plan.md` byte-for-byte unchanged.
- `python -m socrates review adjust-plan --project <project> --dry-run --json` emits valid deterministic JSON with `schema_version: 1`, `quality_boundary: deterministic_review_adjust_plan_preview`, `project`, `short_term_plan_path`, `dry_run: true`, `adjustment_count`, and `review_adjustments`.
- Each preview row includes `concept`, `scheduled_for`, `priority`, `due`, `reason`, and `repair`.
- Normal write mode, including `--json`, remains unchanged and still rewrites `short_term_plan.md`.
- Corrupt `learning_state.json` handling remains clean and non-traceback in dry-run mode without rewriting the plan.
- The command boundary remains explicit: dry-run is a no-write short-term-plan adjustment preview, not a writer, scheduler, exercise generator, tutor, report refresh, LLM call, plan approval, or learning-state mutation.

---

### Task 1: RED Review Adjust-Plan Dry-Run Tests

**Files:**
- Modify: `tests/test_learning_plan.py`

- [x] **Step 1: Add failing prose dry-run test**

Create a project with one scheduled review item, run `review adjust-plan --dry-run`, assert preview output and row text, and assert `short_term_plan.md` was not rewritten.

- [x] **Step 2: Add failing JSON dry-run test**

Run `review adjust-plan --dry-run --json`, assert preview metadata and rows, and assert `short_term_plan.md` was not rewritten.

- [x] **Step 3: Add failing corrupt-state dry-run test**

Run `review adjust-plan --dry-run --json` with invalid `learning_state.json`, assert exit 1, no stdout, clean stderr, and no short-term-plan rewrite.

- [x] **Step 4: Run RED**

Run:

```powershell
python -m unittest tests.test_learning_plan
```

Expected: fail because `review adjust-plan --dry-run` is not registered yet.

---

### Task 2: Add No-Write Preview

**Files:**
- Modify: `socrates/cli.py`

- [x] **Step 1: Register `--dry-run`**

Add `--dry-run` to the `review adjust-plan` parser. Keep existing `--project` and `--json` behavior.

- [x] **Step 2: Route preview before writer**

When `args.dry_run` is true, validate readable learning state, serialize persisted review adjustment rows, and return without calling `adjust_short_term_plan_from_review_schedule(...)`.

- [x] **Step 3: Emit prose and JSON preview output**

For JSON, print `quality_boundary: deterministic_review_adjust_plan_preview` with `dry_run: true`; for prose, print a no-write preview line and review-adjustment rows.

- [x] **Step 4: Preserve writer behavior**

Keep normal prose and JSON writer modes unchanged when `--dry-run` is absent.

- [x] **Step 5: Run GREEN**

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
- Modify: `docs/superpowers/plans/2026-06-04-v49-review-adjust-plan-dry-run.md`
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.49**

Document `review adjust-plan --dry-run` as a no-write short-term-plan adjustment preview, including `--dry-run --json` for wrappers.

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

Commit the v0.49 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.49 commit id, verification evidence, no-write dry-run boundary, and the reusable lesson that plan preview modes should expose persisted writer evidence while proving plan files were not rewritten.
