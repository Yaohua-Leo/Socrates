# v0.29 Multi-Project Resume Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `projects resume --root <root>` so users can inspect returning-learner readiness across a collection of Socrates projects without opening each project individually.

**Architecture:** Create a small read-only collection formatter that uses `list_projects(root)` to discover project paths and `build_project_resume_payload(project_root)` to compute each project's resume state. Wire it into the existing `projects` command group.

**Tech Stack:** Python argparse, existing Socrates project-index and resume readers, `unittest`, deterministic filesystem fixtures.

---

## File Map

- Create `socrates/project_resume.py`: render a read-only multi-project resume index.
- Modify `socrates/cli.py`: add `projects resume --root <root>` and call the formatter.
- Modify `tests/test_project_index.py`: add RED/GREEN CLI coverage for multi-project resume output and read-only behavior.
- Modify docs after GREEN: `README.md`, `docs/README.md`, `docs/development_log.md`, `docs/development_roadmap.md`.
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`.

## Acceptance Criteria

- `python -m socrates projects resume --root <root>` prints `# Project Resume Index`.
- Output includes root path, project count, and one row per discovered project.
- Each row includes project id, project title, resume state, study brief status, current next action, and recommended command.
- Projects with current saved briefs show `ready`, `current`, and `none`.
- Projects with no saved brief show `refresh_brief`, `not_run`, and a `brief generate` recommended command.
- The command is read-only: it does not create study brief artifacts or append project-log entries.

---

### Task 1: RED Multi-Project Resume Tests

**Files:**
- Modify: `tests/test_project_index.py`

- [x] **Step 1: Add failing CLI test**

Add a test that:

1. Creates a `SocratesProjects` root with two projects.
2. Adds a draft note and generated current brief to one project.
3. Leaves the second project without a brief.
4. Runs `projects resume --root <root>`.
5. Asserts output contains `# Project Resume Index`, `- Projects: 2`, one ready/current row for the first project, and one refresh/not_run row plus a `brief generate` command for the second project.
6. Asserts the second project still has no `study_brief.md`, no `study_brief_manifest.json`, and no `Generated study brief.` project-log entry.

- [x] **Step 2: Run RED**

Run:

```powershell
python -m unittest tests.test_project_index
```

Expected: fail because `projects resume` is not registered yet.

---

### Task 2: Add Read-Only Multi-Project Resume

**Files:**
- Create: `socrates/project_resume.py`
- Modify: `socrates/cli.py`

- [x] **Step 1: Implement formatter**

Create `format_project_resume_index(root_path: Path | str) -> str` with this shape:

```text
# Project Resume Index

- Root: <root>
- Projects: <count>

## Projects

- <id> | <title> | <resume_state> | <study_brief> | <current_next_action> | <recommended_command>
```

Use `list_projects(root)` for discovery and `build_project_resume_payload(root / project["path"])` for each row.

- [x] **Step 2: Register CLI command**

Add `projects resume --root <root>` to `socrates/cli.py` and map it to `_handle_projects_resume`.

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
- Modify: `docs/superpowers/plans/2026-06-04-v29-projects-resume.md`
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.29**

Document `projects resume` as a read-only collection-level resume index for project roots, not a generator or project-state mutation.

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

Commit the v0.29 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.29 commit id, verification evidence, collection-resume boundary, and the multi-project navigation lesson.
