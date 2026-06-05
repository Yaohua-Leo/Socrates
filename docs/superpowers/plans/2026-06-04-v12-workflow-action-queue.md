# v0.12 Workflow Action Queue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make long-running Socrates projects easier to operate by surfacing deterministic workflow follow-up commands in the existing queue and status views.

**Architecture:** Extend `socrates.learning_queue` with a `workflow_actions` section that reuses persisted manifest readers and existing file scans. Add a status count so users can see workflow blockers without opening the full queue.

**Tech Stack:** Python stdlib, existing queue dataclasses, existing manifest readers, `unittest`, no new dependencies.

---

### Task 1: Write Failing Queue Tests

**Files:**
- Modify: `tests/test_learning_queue.py`
- Modify: `tests/test_status_quality_summary.py`

- [ ] **Step 1: Add a failing workflow queue test for missing regression**

Create a project with a ready closeout but no multi-session regression manifest. Assert `python -m socrates queue --section workflow` shows a `multi_session_regression` item with the command `socrates lifecycle regression --project <project>`.

- [ ] **Step 2: Add a failing workflow queue test for invalid regression**

Write a corrupt `08_evals/multi_session_regression_manifest.json`. Assert the workflow queue lists the invalid manifest and tells the user to rerun lifecycle regression.

- [ ] **Step 3: Add a failing status count test**

Assert `python -m socrates status --project <project>` prints `Workflow actions: 1` when the missing regression action is present.

### Task 2: Implement Workflow Action Collection

**Files:**
- Modify: `socrates/learning_queue.py`

- [ ] **Step 1: Add queue section and dataclass field**

Add `workflow` to `QUEUE_SECTIONS` and `workflow_actions: list[QueueItem]` to `LearningQueue`.

- [ ] **Step 2: Collect deterministic workflow actions**

Add `_workflow_actions(project_root)` that checks session score, closeout, multi-session regression, and benchmark manifest status. Reuse readers where available; do not parse the same manifest in CLI code.

- [ ] **Step 3: Render workflow actions first or near quality actions**

Include `("workflow", "Workflow Actions", queue.workflow_actions)` in `_queue_sections`.

### Task 3: Wire Status

**Files:**
- Modify: `socrates/cli.py`

- [ ] **Step 1: Count workflow actions**

Use `len(queue.workflow_actions)` inside `_handle_status`.

- [ ] **Step 2: Print status line**

Print `Workflow actions: <count>` near other queue/action counts.

### Task 4: Update Docs and Commit

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/development_roadmap.md`
- Modify: `docs/development_log.md`

- [ ] **Step 1: Document v0.12**

Describe workflow action queue as operational UX only, not a new readiness gate.

- [ ] **Step 2: Run verification**

Run focused tests, full `unittest discover`, `compileall`, `git diff --check`, PowerShell check, and bash check.

- [ ] **Step 3: Commit with Lore protocol**

Use a why-first commit message with final verification evidence and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.
