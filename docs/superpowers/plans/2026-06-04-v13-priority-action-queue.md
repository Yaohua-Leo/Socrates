# v0.13 Priority Action Queue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give long-running Socrates projects a concise first-action view by combining existing queue sections into one deterministic priority list.

**Architecture:** Extend `socrates.learning_queue.format_learning_queue` with a virtual `priority` section. The section does not collect new data; it orders existing queue items by operational priority so workflow blockers appear before content review and exercise work.

**Tech Stack:** Python stdlib, existing `LearningQueue` and `QueueItem`, `unittest`, no new dependencies.

---

### Task 1: Write Failing Priority Queue Test

**Files:**
- Modify: `tests/test_learning_queue.py`

- [x] **Step 1: Add a failing test for `queue --section priority`**

Use the ready-closeout fixture that creates both a missing multi-session regression action and an unreviewed draft note. Assert the priority section renders `Workflow Actions` before `Notes To Review`.

- [x] **Step 2: Add a failing test for empty priority output**

Create an empty project and assert `queue --section priority` renders `## Priority Actions` with `- none`.

### Task 2: Implement Priority Rendering

**Files:**
- Modify: `socrates/learning_queue.py`

- [x] **Step 1: Add `priority` to allowed queue sections**

Extend `QUEUE_SECTIONS` with `priority`.

- [x] **Step 2: Add `_priority_actions(queue)`**

Return `QueueItem` rows prefixed by source section, in this order: workflow, quality checks, tool verifications, obsidian exports, notes, misconceptions, reviews, exercise drafts, exercises, attempts.

- [x] **Step 3: Add `Priority Actions` section**

Render the priority section through the same `_section` helper as other queue sections.

### Task 3: Update Docs and Commit

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/development_roadmap.md`
- Modify: `docs/development_log.md`

- [x] **Step 1: Document v0.13**

Describe priority queue as deterministic ordering of existing actions, not new readiness evidence.

- [x] **Step 2: Run verification**

Run focused tests, full `unittest discover`, `compileall`, `git diff --check`, PowerShell check, and bash check.

- [x] **Step 3: Commit with Lore protocol**

Use a why-first commit message with final verification evidence and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.
