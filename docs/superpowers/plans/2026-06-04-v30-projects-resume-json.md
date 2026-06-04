# v0.30 Multi-Project Resume JSON Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `projects resume --root <root> --json` so future TUI/Web/plugin wrappers can consume collection-level returning-learner readiness without parsing Markdown.

**Architecture:** Refactor `socrates.project_resume` to build one structured collection payload and render Markdown from that payload. Expose the same payload as deterministic JSON through the existing `projects resume` command. Each project row must still reuse `build_project_resume_payload(project_root)`.

**Tech Stack:** Python stdlib JSON, argparse, existing Socrates project-index and resume readers, `unittest`, deterministic filesystem fixtures.

---

## File Map

- Modify `socrates/project_resume.py`: add `build_project_resume_index_payload(root_path)` and render Markdown from the payload.
- Modify `socrates/cli.py`: add `--json` to `projects resume` and print deterministic JSON when requested.
- Modify `tests/test_project_index.py`: add RED/GREEN CLI coverage for collection JSON output and read-only behavior.
- Modify docs after GREEN: `README.md`, `docs/README.md`, `docs/development_log.md`, `docs/development_roadmap.md`.
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`.

## Acceptance Criteria

- `python -m socrates projects resume --root <root> --json` prints valid JSON.
- JSON output includes `schema_version: 1`, `quality_boundary: deterministic_project_resume_index`, `root`, `project_count`, and `projects`.
- Each `projects` entry includes project id, title, path, resume state, study brief status, study brief path, current next action, and recommended command.
- Markdown `projects resume --root <root>` is rendered from the same payload and preserves the v0.29 output contract.
- The command is read-only: it does not create study brief artifacts, write a project index, or append project-log entries.

---

### Task 1: RED Multi-Project Resume JSON Tests

**Files:**
- Modify: `tests/test_project_index.py`

- [x] **Step 1: Add failing JSON CLI test**

Add a test that:

1. Creates a `SocratesProjects` root with two projects.
2. Adds a draft note and generated current brief to one project.
3. Leaves the second project without a brief.
4. Runs `projects resume --root <root> --json`.
5. Parses stdout as JSON and asserts `schema_version`, `quality_boundary`, `root`, `project_count`, stable project order, and the ready/current vs refresh_brief/not_run row values.
6. Asserts the second project still has no `study_brief.md`, no `study_brief_manifest.json`, and no `Generated study brief.` project-log entry.
7. Asserts `socrates_projects.json` is not written by the resume command.

- [x] **Step 2: Run RED**

Run:

```powershell
python -m unittest tests.test_project_index
```

Expected: fail because `projects resume --json` is not registered yet.

---

### Task 2: Add Structured Collection Payload

**Files:**
- Modify: `socrates/project_resume.py`
- Modify: `socrates/cli.py`

- [x] **Step 1: Implement payload builder**

Add `build_project_resume_index_payload(root_path: Path | str) -> dict[str, object]` with:

```text
schema_version: 1
quality_boundary: deterministic_project_resume_index
root: <resolved root>
project_count: <count>
projects: [
  {
    id,
    title,
    path,
    resume_state,
    study_brief,
    study_brief_path,
    current_next_action,
    recommended_command,
  }
]
```

Use `list_projects(root)` for discovery and `build_project_resume_payload(root / project["path"])` for each row.

- [x] **Step 2: Render Markdown from payload**

Update `format_project_resume_index(root_path)` to call the payload builder and preserve the v0.29 Markdown output shape.

- [x] **Step 3: Wire CLI JSON output**

Add `--json` to `projects resume` and print `json.dumps(payload, indent=2, sort_keys=True)` when requested.

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
- Modify: `docs/superpowers/plans/2026-06-04-v30-projects-resume-json.md`
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.30**

Document `projects resume --json` as a read-only machine-readable collection state surface for project roots, not as a generator, scanner, report refresh, or child-project mutation.

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

Commit the v0.30 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.30 commit id, verification evidence, JSON collection boundary, and the structured collection payload lesson.
