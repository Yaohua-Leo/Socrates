# v0.32 Multi-Project Resume State Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `projects resume --state all|ready|refresh_brief` so users can act on the v0.31 readiness counts by filtering the collection view to projects that are ready or need brief refresh work.

**Architecture:** Extend `build_project_resume_index_payload` and `format_project_resume_index` with a `state_filter` parameter. Build rows from existing per-project resume payloads, filter rows by `resume_state`, then compute counts from the returned rows. Wire the filter into the `projects resume` CLI for both Markdown and JSON output.

**Tech Stack:** Python argparse choices, existing Socrates project resume payload, `unittest`, deterministic filesystem fixtures.

---

## File Map

- Modify `socrates/project_resume.py`: accept a state filter, filter collection rows, add `state_filter` to JSON payload, and render filter in Markdown snapshot.
- Modify `socrates/cli.py`: add `--state` to `projects resume` with choices `all`, `ready`, and `refresh_brief`.
- Modify `tests/test_project_index.py`: add RED/GREEN coverage for filtered Markdown and JSON output plus read-only behavior.
- Modify docs after GREEN: `README.md`, `docs/README.md`, `docs/development_log.md`, `docs/development_roadmap.md`.
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`.

## Acceptance Criteria

- `python -m socrates projects resume --root <root> --state refresh_brief` returns only refresh-needed projects.
- `python -m socrates projects resume --root <root> --state ready` returns only ready projects.
- `--json` output includes `state_filter` and the filtered `projects` rows.
- `project_count`, `ready_count`, and `refresh_brief_count` are computed from the returned rows after filtering.
- Default behavior remains equivalent to `--state all`.
- The command remains read-only: it does not create study brief artifacts, write a project index, or append project-log entries.

---

### Task 1: RED State Filter Tests

**Files:**
- Modify: `tests/test_project_index.py`

- [x] **Step 1: Add failing Markdown filter test**

Add a test that:

1. Creates a `SocratesProjects` root with one ready project and one refresh-needed project.
2. Runs `projects resume --root <root> --state refresh_brief`.
3. Asserts the output includes `State filter: refresh_brief`, `Projects: 1`, `Ready: 0`, `Refresh brief: 1`.
4. Asserts the refresh-needed project row is present and the ready project row is absent.
5. Asserts no child brief artifacts are written for the refresh-needed project and no `socrates_projects.json` is written.

- [x] **Step 2: Add failing JSON filter test**

Add a test that:

1. Reuses the same two-project shape.
2. Runs `projects resume --root <root> --state ready --json`.
3. Parses stdout as JSON and asserts `state_filter: ready`, `project_count: 1`, `ready_count: 1`, `refresh_brief_count: 0`.
4. Asserts only the ready project appears.
5. Asserts no child brief artifacts are written for the refresh-needed project and no `socrates_projects.json` is written.

- [x] **Step 3: Run RED**

Run:

```powershell
python -m unittest tests.test_project_index
```

Expected: fail because `projects resume --state` is not registered yet.

---

### Task 2: Add State Filtering

**Files:**
- Modify: `socrates/project_resume.py`
- Modify: `socrates/cli.py`

- [x] **Step 1: Add filter parameter**

Update `build_project_resume_index_payload(root_path, *, state_filter="all")` and `format_project_resume_index(root_path, *, state_filter="all")`.

- [x] **Step 2: Filter rows before counts**

Filter rows where:

```text
all: keep every project
ready: keep rows with resume_state == "ready"
refresh_brief: keep rows with resume_state == "refresh_brief"
```

Then compute `project_count`, `ready_count`, and `refresh_brief_count` from the filtered rows.

- [x] **Step 3: Wire CLI option**

Add:

```text
--state {all,ready,refresh_brief}
```

to `projects resume`, defaulting to `all`, and pass the value to both Markdown and JSON paths.

- [x] **Step 4: Run GREEN**

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
- Modify: `docs/superpowers/plans/2026-06-04-v32-projects-resume-filter.md`
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.32**

Document state filtering as a read-only collection navigation aid, not a score, readiness gate, scanner, report generator, or child-project mutation.

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

Commit the v0.32 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.32 commit id, verification evidence, state-filter boundary, and the filtered-collection lesson.
