# v0.42 Review Due JSON Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development to lock the read-only JSON contract before implementation. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `review due --json` so wrappers, UI prototypes, and plugins can consume due review items and invalid schedule rows without parsing Markdown.

**Architecture:** Reuse `_due_review_rows(learning_state, as_of, priority=...)` as the single reader source. Add a CLI JSON output mode that serializes the same due rows plus invalid schedule rows with cutoff/filter metadata. Keep the command read-only: it must not write `learning_state.json`, repair schedules, reports, note drafts, or project logs.

**Tech Stack:** Python argparse, existing Socrates due-review reader, `json`, `unittest`, deterministic temporary project fixtures.

---

## File Map

- Modify `tests/test_state_eval.py`: add RED coverage for `review due --json`, due/invalid row fields, cutoff/filter metadata, priority filtering, and read-only behavior.
- Modify `socrates/cli.py`: add `--json` to `review due` and route it through a small payload helper derived from `_due_review_rows`.
- Modify docs after GREEN: `README.md`, `docs/README.md`, `docs/development_log.md`, `docs/development_roadmap.md`.
- Modify this plan as checklist state changes.
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`.

## Acceptance Criteria

- `python -m socrates review due --project <project> --as-of 2026-06-07 --json` emits valid deterministic JSON with `schema_version: 1`, `quality_boundary: deterministic_due_review`, `project`, `as_of`, `priority_filter`, `due_count`, `invalid_count`, `due_reviews`, and `invalid_reviews`.
- Each due row includes `concept`, `scheduled_for`, `priority`, `reason`, and `repair`.
- Each invalid row includes `concept`, `scheduled_for`, and `status: invalid_scheduled_for`.
- `--priority high --json` returns only high-priority due rows while still reporting invalid persisted schedule rows.
- JSON output is read-only: it does not mutate `00_meta/learning_state.json`, repair schedules, reports, note drafts, or project logs.
- Existing Markdown `review due` output and clean error handling for invalid dates or corrupt learning state remain compatible.
- The command boundary remains explicit: JSON output is a read-only due-review ledger view, not a scheduler, repair command, exercise generator, planner, tutor, report refresh, LLM call, or learning-state mutation.

---

### Task 1: RED Due-Review JSON Tests

**Files:**
- Modify: `tests/test_state_eval.py`

- [x] **Step 1: Add failing JSON payload test**

Create a project with one high due item, one medium due item, and one invalid persisted schedule row. Run `review due --project <project> --as-of 2026-06-07 --json`, parse stdout, and assert schema fields, row counts, row fields, invalid rows, deterministic ordering, and no Markdown text.

- [x] **Step 2: Add failing priority-filter read-only test**

Snapshot `learning_state.json` and project log, run `review due --project <project> --as-of 2026-06-07 --priority high --json`, assert only high due rows are returned, invalid rows remain visible, and snapshots are unchanged.

- [x] **Step 3: Run RED**

Run:

```powershell
python -m unittest tests.test_state_eval
```

Expected: fail because `review due --json` is not registered yet.

---

### Task 2: Add JSON Output

**Files:**
- Modify: `socrates/cli.py`

- [x] **Step 1: Register `--json`**

Add `--json` to the `review due` parser as an output mode flag. Keep existing `--as-of` and `--priority` behavior.

- [x] **Step 2: Add payload helper**

Add a small private helper that takes the loaded project context, cutoff date, priority filter, due rows, and invalid rows, then returns:

```python
{
    "schema_version": 1,
    "quality_boundary": "deterministic_due_review",
    "project": str(context.root),
    "as_of": as_of.isoformat(),
    "priority_filter": priority,
    "due_count": len(rows),
    "invalid_count": len(invalid_rows),
    "due_reviews": [...],
    "invalid_reviews": [...],
}
```

- [x] **Step 3: Route JSON output**

In `_handle_review_due`, call `_due_review_rows` once, print JSON with `indent=2` and a trailing newline when `args.json` is true; otherwise keep the existing Markdown renderer.

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
- Modify: `docs/superpowers/plans/2026-06-04-v42-review-due-json.md`
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.42**

Document `review due --json` as a read-only structured due-review ledger view, not a scheduler, repair command, exercise generator, planner, tutor, report refresh, LLM call, or learning-state mutation.

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

Commit the v0.42 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.42 commit id, verification evidence, read-only JSON boundary, and the reusable lesson that due-review JSON should expose invalid persisted rows alongside filtered due rows.
