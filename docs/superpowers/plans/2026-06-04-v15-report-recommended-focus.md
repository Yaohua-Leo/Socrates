# v0.15 Report Recommended Focus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn existing report evidence into a compact deterministic `Recommended Focus` section so weekly, monthly, and project summary reports say what to do and review next.

**Architecture:** Keep recommendations render-only. Reports will derive one next action from priority queue items, one weakest concept from learning-state scores, one next scheduled review, and one active misconception from persisted learning-state evidence.

**Tech Stack:** Python stdlib, existing report/queue/state helpers, `unittest`, no new dependencies.

---

### Task 1: Add Failing Recommended Focus Tests

**Files:**
- Modify: `tests/test_reports.py`

- [x] **Step 1: Add a monthly focus test**

Use the existing report fixture, write a ready closeout manifest, run `python -m socrates report monthly --project <project>`, and assert the report contains:

```text
## Recommended Focus
- Next action: workflow:multi_session_regression | 08_evals/session_closeout_manifest.json | status: not_run; run with: socrates lifecycle regression --project <project>
- Weak concept: quotient_group: 0.42
- Next review: quotient_group | high | 2026-06-04
- Active misconception: none recorded
```

- [x] **Step 2: Add a project summary focus test with a misconception**

Use the existing report fixture, add one active misconception through `update_learning_state`, write a ready closeout manifest, run `python -m socrates report project-summary --project <project>`, and assert the focus section includes the same next action plus `- Active misconception: normal_equals_central | normal_subgroup | active x1`.

- [x] **Step 3: Add an empty weekly focus fallback test**

Create an empty project, run `python -m socrates report weekly --project <project>`, and assert the focus section renders `none` fallback rows for next action, weak concept, next review, and active misconception.

- [x] **Step 4: Run RED tests**

Run:

```powershell
python -m unittest tests.test_reports
```

Expected: the new tests fail because reports do not yet include `Recommended Focus`.

### Task 2: Implement Recommended Focus Rendering

**Files:**
- Modify: `socrates/reports.py`

- [x] **Step 1: Add `_recommended_focus_lines`**

Add a helper:

```python
def _recommended_focus_lines(
    *,
    priority_actions: list[QueueItem],
    state: dict[str, object],
) -> list[str]:
```

It should return four rows: next action, weak concept, next review, and active misconception.

- [x] **Step 2: Add deterministic sub-helpers**

Add helpers for:

```python
_next_action_focus(priority_actions: list[QueueItem]) -> str
_weakest_concept_focus(value: object) -> str
_next_review_focus(value: object) -> str
_active_misconception_focus(value: object) -> str
```

Use existing score/count coercion helpers for learning-state values. Sort ties deterministically by concept or misconception id.

- [x] **Step 3: Insert report sections**

Add:

```text
## Recommended Focus
```

after `## Priority Actions` in weekly, monthly, and project summary reports.

- [x] **Step 4: Run GREEN report tests**

Run:

```powershell
python -m unittest tests.test_reports
```

Expected: all report tests pass.

### Task 3: Update Docs, Verify, Commit, and Capture Wiki

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/development_roadmap.md`
- Modify: `docs/development_log.md`
- Modify after commit: `D:\llmwiki\wiki\projects\socrates.md`
- Modify after commit: `D:\llmwiki\wiki\index.md`
- Modify after commit: `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.15**

Describe recommended focus as deterministic report UX over existing state/queue evidence, not a tutor, score, planner, or learning-state mutation.

- [x] **Step 2: Run verification**

Run:

```powershell
python -m unittest tests.test_reports tests.test_learning_queue
python -m unittest discover -s tests
python -m compileall socrates
git diff --check
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
bash scripts/check.sh
```

- [x] **Step 3: Commit with Lore protocol**

Commit the v0.15 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with v0.15 commit id, verification evidence, and the boundary that recommended focus rows are render-only summaries of existing evidence.
