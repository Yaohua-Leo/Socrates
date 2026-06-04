# v0.41 Review Mastery JSON Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development to lock the read-only JSON contract before implementation. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `review mastery --json` so wrappers, UI prototypes, and plugins can consume persisted concept mastery and proof-skill scores without parsing Markdown.

**Architecture:** Reuse `list_learning_scores(context, score_type=..., status=..., threshold=...)` as the single reader source. Add a CLI JSON output mode that serializes the same filtered rows with filter metadata and weak/ready counts. Keep the command read-only: it must not write `learning_state.json`, review schedules, reports, note drafts, or project logs.

**Tech Stack:** Python argparse, existing Socrates learning-state reader, `json`, `unittest`, deterministic temporary project fixtures.

---

## File Map

- Modify `tests/test_state_eval.py`: add RED coverage for `review mastery --json`, filter metadata, threshold-sensitive counts, row fields, and read-only behavior.
- Modify `socrates/cli.py`: add `--json` to `review mastery` and route it through a small payload helper derived from `LearningScoreSummary` rows.
- Modify docs after GREEN: `README.md`, `docs/README.md`, `docs/development_log.md`, `docs/development_roadmap.md`.
- Modify this plan as checklist state changes.
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`.

## Acceptance Criteria

- `python -m socrates review mastery --project <project> --json` emits valid deterministic JSON with `schema_version: 1`, `quality_boundary: deterministic_learning_mastery_review`, `project`, `kind_filter`, `status_filter`, `threshold`, `score_count`, `weak_count`, `ready_count`, and `scores`.
- Each score row includes `score_type`, `item_id`, `status`, and `score`.
- `--kind concept --status weak --threshold 0.8 --json` returns only weak concept rows under that threshold and counts the returned set without Markdown headings or bullet text.
- JSON output is read-only: it does not mutate `00_meta/learning_state.json`, review schedules, reports, note drafts, or project logs.
- Existing Markdown `review mastery` output remains compatible.
- Invalid thresholds keep the existing clean error behavior.
- The command boundary remains explicit: JSON output is a read-only mastery ledger view, not a scheduler, planner, tutor, score writer, report refresh, LLM call, or learning-state mutation.

---

### Task 1: RED Mastery JSON Tests

**Files:**
- Modify: `tests/test_state_eval.py`

- [x] **Step 1: Add failing JSON payload test**

Create a project with weak and ready concept/proof-skill scores, run `review mastery --project <project> --json`, parse stdout, and assert schema fields, counts, deterministic row ordering, row fields, and no Markdown text.

- [x] **Step 2: Add failing filter read-only test**

Snapshot `learning_state.json` and project log, run `review mastery --project <project> --kind concept --status weak --threshold 0.8 --json`, assert only weak concept rows are returned and snapshots are unchanged.

- [x] **Step 3: Run RED**

Run:

```powershell
python -m unittest tests.test_state_eval
```

Expected: fail because `review mastery --json` is not registered yet.

---

### Task 2: Add JSON Output

**Files:**
- Modify: `socrates/cli.py`

- [x] **Step 1: Register `--json`**

Add `--json` to the `review mastery` parser as an output mode flag. Keep existing `--kind`, `--status`, and `--threshold` behavior.

- [x] **Step 2: Add payload helper**

Add a small private helper that takes the loaded project context, filters, threshold, and `LearningScoreSummary` rows, then returns:

```python
{
    "schema_version": 1,
    "quality_boundary": "deterministic_learning_mastery_review",
    "project": str(context.root),
    "kind_filter": kind,
    "status_filter": status,
    "threshold": threshold,
    "score_count": len(rows),
    "weak_count": ...,
    "ready_count": ...,
    "scores": [...],
}
```

- [x] **Step 3: Route JSON output**

In `_handle_review_mastery`, print JSON with `indent=2` and a trailing newline when `args.json` is true; otherwise keep the existing Markdown renderer.

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
- Modify: `docs/superpowers/plans/2026-06-04-v41-review-mastery-json.md`
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.41**

Document `review mastery --json` as a read-only structured mastery ledger view, not a scheduler, planner, tutor, score writer, report refresh, LLM call, or learning-state mutation.

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

Commit the v0.41 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.41 commit id, verification evidence, read-only JSON boundary, and the reusable lesson that score-ledger JSON should preserve filter metadata and serialize the same reader rows used by Markdown.
