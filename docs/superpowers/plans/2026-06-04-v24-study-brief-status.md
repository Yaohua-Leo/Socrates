# v0.24 Study Brief Status Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make generated study-start briefs auditable from dashboard and status output so stale next-action briefs are visible before a learner resumes work.

**Architecture:** Add a dependency-light `socrates.study_brief_status` reader that compares the next action recorded in `07_exports/briefs/study_brief.md` with the current first priority queue action. Dashboard and status import that reader; the brief writer imports only the shared artifact path constant to avoid a circular dependency with `socrates.dashboard`.

**Tech Stack:** Python stdlib, existing Socrates CLI, `unittest`, deterministic filesystem fixtures.

---

## File Map

- Create `socrates/study_brief_status.py`: read and summarize study brief status.
- Modify `socrates/study_brief.py`: reuse the shared brief artifact path constant.
- Modify `socrates/dashboard.py`: include study brief status rows.
- Modify `socrates/cli.py`: include study brief status rows in `status`.
- Modify `tests/test_study_brief.py`: add RED tests for not-run/current/stale visibility.
- Modify docs after GREEN: `README.md`, `docs/README.md`, `docs/development_log.md`, `docs/development_roadmap.md`.

## Acceptance Criteria

- Missing brief renders `Study brief: not_run` in both dashboard and status.
- Freshly generated brief renders `Study brief: current`.
- If the first priority queue action changes after brief generation, dashboard and status render `Study brief: stale`.
- Status output includes the recorded next action and the current next action.
- The status reader does not parse dashboard Markdown or call report/LLM/generation workflows.

---

### Task 1: RED Study Brief Status Tests

**Files:**
- Modify: `tests/test_study_brief.py`

- [x] **Step 1: Add failing tests**

Add tests that:

1. Create an empty project and assert dashboard/status show `Study brief: not_run`.
2. Create a draft note, generate a brief, and assert dashboard/status show `Study brief: current` with the same next action.
3. Generate a brief for an empty project, add a draft note, then assert dashboard/status show `Study brief: stale`, recorded next action `none`, and current next action matching the new queue item.

- [x] **Step 2: Run RED**

Run:

```powershell
python -m unittest tests.test_study_brief
```

Expected: fail because dashboard and status do not expose study brief status rows yet.

---

### Task 2: Implement Study Brief Status Reader

**Files:**
- Create: `socrates/study_brief_status.py`
- Modify: `socrates/study_brief.py`

- [x] **Step 1: Add reader module**

Create a frozen `StudyBriefStatus` dataclass with `status`, `path`, `recorded_next_action`, and `current_next_action`. Implement `summarize_study_brief(project_path)` with `not_run`, `current`, `stale`, and `invalid` statuses.

- [x] **Step 2: Share artifact path**

Move `STUDY_BRIEF_RELATIVE_PATH` into `study_brief_status.py` and import it from `study_brief.py`.

- [x] **Step 3: Run focused GREEN for reader behavior**

Run:

```powershell
python -m unittest tests.test_study_brief
```

Expected: still fail until dashboard/status are wired, but the failures should mention missing output rows rather than import errors.

---

### Task 3: Wire Dashboard and Status

**Files:**
- Modify: `socrates/dashboard.py`
- Modify: `socrates/cli.py`

- [x] **Step 1: Add dashboard rows**

Add snapshot rows for study brief status, recorded next action, and current next action.

- [x] **Step 2: Add status rows**

Add status output rows for study brief status, recorded next action, and current next action.

- [x] **Step 3: Run GREEN**

Run:

```powershell
python -m unittest tests.test_study_brief tests.test_dashboard tests.test_status_quality_summary
```

Expected: tests OK.

---

### Task 4: Docs, Verification, Commit, and Wiki

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/development_log.md`
- Modify: `docs/development_roadmap.md`
- Modify: `docs/superpowers/plans/2026-06-04-v24-study-brief-status.md`
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.24**

Document that study brief status is a next-action freshness check, not a report freshness system or readiness gate.

- [x] **Step 2: Run verification**

Run:

```powershell
python -m unittest tests.test_study_brief tests.test_dashboard tests.test_status_quality_summary tests.test_learning_queue
python -m unittest discover -s tests
python -m compileall socrates
git diff --check
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
bash scripts/check.sh
```

- [x] **Step 3: Commit with Lore protocol**

Commit the v0.24 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.24 commit id, verification evidence, next-action freshness boundary, and note that the reader avoids dashboard/report parsing.
