# v0.40 Review Misconceptions JSON Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development to lock the read-only JSON contract before implementation. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `review misconceptions --json` so wrappers, UI prototypes, and plugins can consume the persisted misconception ledger without parsing Markdown.

**Architecture:** Reuse `list_misconceptions(context, status=...)` as the single reader source. Add a CLI JSON output mode that serializes the same filtered rows with counts and a clear deterministic quality boundary. Keep the command read-only: it must not write `learning_state.json`, `mistake_bank.md`, note drafts, reports, or project logs.

**Tech Stack:** Python argparse, existing Socrates learning-state reader, `json`, `unittest`, deterministic temporary project fixtures.

---

## File Map

- Modify `tests/test_state_eval.py`: add RED coverage for `review misconceptions --json`, status filtering, row fields, and read-only behavior.
- Modify `socrates/cli.py`: add `--json` to `review misconceptions` and route it through a small payload helper derived from `MisconceptionSummary` rows.
- Modify docs after GREEN: `README.md`, `docs/README.md`, `docs/development_log.md`, `docs/development_roadmap.md`.
- Modify this plan as checklist state changes.
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`.

## Acceptance Criteria

- `python -m socrates review misconceptions --project <project> --json` emits valid deterministic JSON with `schema_version: 1`, `quality_boundary: deterministic_misconception_review`, `project`, `status_filter`, `misconception_count`, `active_count`, `resolved_count`, and `misconceptions`.
- Each misconception row includes `misconception_id`, `status`, `concept`, `count`, `last_session_id`, `analysis`, `repair_suggestion`, and `follow_up_exercises`.
- `--status active --json` returns only active rows and counts the returned set without Markdown headings or bullet text.
- JSON output is read-only: it does not mutate `00_meta/learning_state.json`, `05_exercises/mistake_bank.md`, note drafts, reports, or project logs.
- Existing Markdown `review misconceptions` output remains compatible.
- The command boundary remains explicit: JSON output is a read-only misconception ledger view, not a resolver, note generator, tutor, score, report refresh, LLM call, or learning-state mutation.

---

### Task 1: RED Misconception JSON Tests

**Files:**
- Modify: `tests/test_state_eval.py`

- [x] **Step 1: Add failing JSON payload test**

Create a project with one active and one resolved misconception, run `review misconceptions --project <project> --json`, parse stdout, and assert the schema fields, counts, deterministic row ordering, row fields, and no Markdown text.

- [x] **Step 2: Add failing status-filter read-only test**

Snapshot `learning_state.json` and `mistake_bank.md`, run `review misconceptions --project <project> --status active --json`, assert only the active row is returned and the snapshots are unchanged.

- [x] **Step 3: Run RED**

Run:

```powershell
python -m unittest tests.test_state_eval
```

Expected: fail because `review misconceptions --json` is not registered yet.

---

### Task 2: Add JSON Output

**Files:**
- Modify: `socrates/cli.py`

- [x] **Step 1: Register `--json`**

Add `--json` to the `review misconceptions` parser as an output mode flag. Keep existing `--status` behavior.

- [x] **Step 2: Add payload helper**

Add a small private helper that takes the loaded project context, status filter, and `MisconceptionSummary` rows, then returns:

```python
{
    "schema_version": 1,
    "quality_boundary": "deterministic_misconception_review",
    "project": str(context.root),
    "status_filter": status,
    "misconception_count": len(rows),
    "active_count": ...,
    "resolved_count": ...,
    "misconceptions": [...],
}
```

- [x] **Step 3: Route JSON output**

In `_handle_review_misconceptions`, print JSON with `indent=2` and a trailing newline when `args.json` is true; otherwise keep the existing Markdown renderer.

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
- Modify: `docs/superpowers/plans/2026-06-04-v40-review-misconceptions-json.md`
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.40**

Document `review misconceptions --json` as a read-only structured misconception ledger view, not a resolver, note generator, tutor, score, report refresh, LLM call, or learning-state mutation.

- [x] **Step 2: Run verification**

Run:

```powershell
python -m unittest tests.test_state_eval tests.test_note_review_export tests.test_status_quality_summary tests.test_learning_queue tests.test_reports
python -m unittest discover -s tests
python -m compileall socrates
git diff --check
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
bash scripts/check.sh
```

- [x] **Step 3: Commit with Lore protocol**

Commit the v0.40 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.40 commit id, verification evidence, read-only JSON boundary, and the reusable lesson that wrapper-facing ledger views should serialize the same reader rows instead of parsing Markdown.
