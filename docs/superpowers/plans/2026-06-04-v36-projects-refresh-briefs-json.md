# v0.36 Multi-Project Brief Refresh JSON Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `projects refresh-briefs --json` so wrappers can consume the explicit collection writer result without parsing Markdown.

**Architecture:** Reuse `refresh_project_briefs_payload(root_path)` as the single structured writer source. Add a CLI `--json` output flag that dumps that payload after performing the same selected child-project writes as Markdown output.

**Tech Stack:** Python argparse, existing Socrates project brief refresh payload, `json`, `unittest`, deterministic temporary project fixtures.

---

## File Map

- Modify `tests/test_project_index.py`: add RED coverage that `projects refresh-briefs --json` writes selected refresh-needed child briefs and returns structured refreshed/skipped rows.
- Modify `socrates/cli.py`: import no new modules; add `--json` to `projects refresh-briefs` and route JSON output through `refresh_project_briefs_payload`.
- Modify docs after GREEN: `README.md`, `docs/README.md`, `docs/development_log.md`, `docs/development_roadmap.md`.
- Modify `docs/superpowers/plans/2026-06-04-v36-projects-refresh-briefs-json.md` as checklist state changes.
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`.

## Acceptance Criteria

- `python -m socrates projects refresh-briefs --root <root> --json` emits JSON with `schema_version: 1`, `quality_boundary: deterministic_project_brief_refresh`, `root`, `refreshed_count`, `skipped_count`, `refreshed`, and `skipped`.
- JSON output writes the same selected child study brief artifacts as Markdown output.
- Ready projects are represented in `skipped` and do not receive another `Generated study brief.` project-log entry.
- The command still does not write `socrates_projects.json`.
- The command boundary remains explicit: JSON changes output format only, not selection semantics or writer side effects.

---

### Task 1: RED JSON Writer Test

**Files:**
- Modify: `tests/test_project_index.py`

- [x] **Step 1: Add failing JSON refresh test**

Add a test that:

1. Creates a `SocratesProjects` root with one ready project and one refresh-needed project.
2. Generates a current brief for the ready project before running the batch command.
3. Runs `projects refresh-briefs --root <root> --json`.
4. Parses stdout as JSON and asserts `schema_version: 1`, `quality_boundary: deterministic_project_brief_refresh`, `refreshed_count: 1`, and `skipped_count: 1`.
5. Asserts `refreshed` contains the refresh-needed project id, title, path, `resume_state: refresh_brief`, and `brief_path: 07_exports/briefs/study_brief.md`.
6. Asserts `skipped` contains the ready project id, title, path, `resume_state: ready`, and `reason: resume_state_ready`.
7. Asserts the refresh-needed project now has `study_brief.md`, `study_brief_manifest.json`, and a project-log entry.
8. Asserts the ready project's project log still has exactly one `Generated study brief.` entry.
9. Asserts no root `socrates_projects.json` is written.

- [x] **Step 2: Run RED**

Run:

```powershell
python -m unittest tests.test_project_index
```

Expected: fail because `projects refresh-briefs --json` is not registered yet.

---

### Task 2: Add JSON Output Mode

**Files:**
- Modify: `socrates/cli.py`

- [x] **Step 1: Import payload helper**

Change the existing import to:

```python
from .project_brief_refresh import (
    format_project_brief_refresh,
    refresh_project_briefs_payload,
)
```

- [x] **Step 2: Register `--json`**

Add to `projects_refresh_briefs_parser`:

```python
projects_refresh_briefs_parser.add_argument(
    "--json",
    action="store_true",
    help="Print the project brief refresh result as deterministic JSON.",
)
```

- [x] **Step 3: Route JSON output**

Update `_handle_projects_refresh_briefs`:

```python
def _handle_projects_refresh_briefs(args: argparse.Namespace) -> int:
    if args.json:
        print(
            json.dumps(
                refresh_project_briefs_payload(args.root),
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(format_project_brief_refresh(args.root), end="")
    return 0
```

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
- Modify: `docs/superpowers/plans/2026-06-04-v36-projects-refresh-briefs-json.md`
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.36**

Document `projects refresh-briefs --json` as the same explicit collection writer result in structured output form, not a dry-run, new selection policy, or read-only command.

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

Commit the v0.36 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.36 commit id, verification evidence, writer JSON boundary, and the reusable lesson that writer commands can expose structured results without changing side-effect semantics.
