# v0.31 Multi-Project Resume Summary Counts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add collection-level readiness counts to `projects resume` and `projects resume --json` so users and wrappers can see whether a project root is mostly ready or needs brief refresh work without scanning every row.

**Architecture:** Extend the v0.30 collection payload with aggregate counts derived from the already-built project rows. Render the same counts in the Markdown snapshot. Keep all values read-only and derived from `build_project_resume_index_payload(root_path)`.

**Tech Stack:** Python stdlib, existing Socrates project resume payload, `unittest`, deterministic filesystem fixtures.

---

## File Map

- Modify `socrates/project_resume.py`: add `ready_count` and `refresh_brief_count` to the collection payload and Markdown snapshot.
- Modify `tests/test_project_index.py`: add RED/GREEN coverage for Markdown and JSON summary counts plus read-only behavior.
- Modify docs after GREEN: `README.md`, `docs/README.md`, `docs/development_log.md`, `docs/development_roadmap.md`.
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`.

## Acceptance Criteria

- `python -m socrates projects resume --root <root>` includes `- Ready: <count>` and `- Refresh brief: <count>` in the snapshot.
- `python -m socrates projects resume --root <root> --json` includes `ready_count` and `refresh_brief_count`.
- Counts are derived from `resume_state` values in the collection payload.
- Existing project rows and JSON project entries remain unchanged.
- The command remains read-only: it does not create study brief artifacts, write a project index, or append project-log entries.

---

### Task 1: RED Summary Count Tests

**Files:**
- Modify: `tests/test_project_index.py`

- [x] **Step 1: Add failing Markdown count assertions**

Update the existing Markdown `projects resume` test to assert:

```text
- Ready: 1
- Refresh brief: 1
```

Keep the existing read-only assertions for the fresh child project.

- [x] **Step 2: Add failing JSON count assertions**

Update the existing JSON `projects resume --json` test to assert:

```text
ready_count == 1
refresh_brief_count == 1
```

Keep the existing read-only assertions for the fresh child project and missing `socrates_projects.json`.

- [x] **Step 3: Run RED**

Run:

```powershell
python -m unittest tests.test_project_index
```

Expected: fail because the summary count fields/rows do not exist yet.

---

### Task 2: Add Collection Summary Counts

**Files:**
- Modify: `socrates/project_resume.py`

- [x] **Step 1: Add payload counts**

After building project rows, compute:

```text
ready_count = number of rows with resume_state == "ready"
refresh_brief_count = number of rows with resume_state == "refresh_brief"
```

Add both fields to the payload.

- [x] **Step 2: Render Markdown counts**

Add these rows to the `## Snapshot` section after project count:

```text
- Ready: <ready_count>
- Refresh brief: <refresh_brief_count>
```

- [x] **Step 3: Run GREEN**

Run:

```powershell
python -m unittest tests.test_project_index tests.test_resume tests.test_study_brief
```

Expected: tests OK.

---

### Task 3: Docs, Verification, Commit, and Wiki

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/development_log.md`
- Modify: `docs/development_roadmap.md`
- Modify: `docs/superpowers/plans/2026-06-04-v31-projects-resume-summary.md`
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.31**

Document readiness counts as a read-only collection-level scan aid, not a new score, readiness gate, project mutation, scanner, or report generator.

- [x] **Step 2: Run verification**

Run:

```powershell
python -m unittest tests.test_project_index tests.test_resume tests.test_study_brief tests.test_dashboard tests.test_status_quality_summary tests.test_learning_queue
python -m unittest discover -s tests
python -m compileall socrates
git diff --check
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
bash scripts/check.sh
```

- [x] **Step 3: Commit with Lore protocol**

Commit the v0.31 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.31 commit id, verification evidence, readiness-count boundary, and the collection-summary lesson.
