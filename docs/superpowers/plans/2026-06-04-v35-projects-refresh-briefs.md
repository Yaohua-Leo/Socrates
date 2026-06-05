# v0.35 Multi-Project Brief Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `projects refresh-briefs --root <root>` to explicitly generate study briefs for child projects whose resume state is `refresh_brief`.

**Architecture:** Keep the batch writer separate from the read-only `projects resume` surfaces. Use existing per-project resume payloads to select only refresh-needed projects, then call the existing `generate_study_brief` writer for those child projects and render a deterministic summary of refreshed and skipped rows.

**Tech Stack:** Python argparse, existing Socrates project index/resume/study brief APIs, `unittest`, deterministic temporary project fixtures.

---

## File Map

- Modify `tests/test_project_index.py`: add RED coverage that the new command writes only refresh-needed child briefs and noops when all returned projects are ready.
- Create `socrates/project_brief_refresh.py`: collect child projects, select `resume_state == "refresh_brief"`, call `generate_study_brief`, and render a deterministic summary.
- Modify `socrates/cli.py`: register `projects refresh-briefs --root <root>` and route it to the new formatter.
- Modify docs after GREEN: `README.md`, `docs/README.md`, `docs/development_log.md`, `docs/development_roadmap.md`.
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`.

## Acceptance Criteria

- `python -m socrates projects refresh-briefs --root <root>` writes `07_exports/briefs/study_brief.md` and `study_brief_manifest.json` only for projects whose current resume state is `refresh_brief`.
- Ready projects are skipped and do not receive another project-log entry.
- The command prints refreshed and skipped counts plus deterministic rows for each bucket.
- The command does not write `socrates_projects.json`.
- The command boundary is explicit: this is a brief writer, not a scanner, report refresh, repair runner, LLM call, score, tutor, approval, readiness gate, or learning-state truth mutation.

---

### Task 1: RED Batch Brief Refresh Tests

**Files:**
- Modify: `tests/test_project_index.py`

- [x] **Step 1: Add failing mixed refresh test**

Add a test that:

1. Creates a `SocratesProjects` root with one ready project and one refresh-needed project.
2. Generates a current brief for the ready project before running the batch command.
3. Runs `projects refresh-briefs --root <root>`.
4. Asserts stdout includes `# Project Brief Refresh`, `Refreshed: 1`, and `Skipped: 1`.
5. Asserts stdout includes the refresh-needed project under refreshed rows and the ready project under skipped rows.
6. Asserts the refresh-needed project now has `study_brief.md`, `study_brief_manifest.json`, and a `Generated study brief.` project-log entry.
7. Asserts the ready project's project log still has exactly one `Generated study brief.` entry from setup.
8. Asserts no root `socrates_projects.json` is written.

- [x] **Step 2: Add failing no-op all-ready test**

Add a test that:

1. Creates one ready project under a `SocratesProjects` root.
2. Generates its current study brief before running the batch command.
3. Runs `projects refresh-briefs --root <root>`.
4. Asserts stdout includes `Refreshed: 0`, `Skipped: 1`, and `- none` in `## Refreshed Projects`.
5. Asserts the ready project's project log still has exactly one `Generated study brief.` entry.
6. Asserts no root `socrates_projects.json` is written.

- [x] **Step 3: Run RED**

Run:

```powershell
python -m unittest tests.test_project_index
```

Expected: fail because `projects refresh-briefs` is not registered yet.

---

### Task 2: Add Batch Brief Refresh Writer

**Files:**
- Create: `socrates/project_brief_refresh.py`
- Modify: `socrates/cli.py`

- [x] **Step 1: Create refresh payload and formatter**

Create `socrates/project_brief_refresh.py` with:

```python
"""Batch study-brief refresh for project collections."""

from __future__ import annotations

from pathlib import Path

from .project_index import list_projects
from .resume import build_project_resume_payload
from .study_brief import generate_study_brief


PROJECT_BRIEF_REFRESH_QUALITY_BOUNDARY = "deterministic_project_brief_refresh"


def refresh_project_briefs_payload(root_path: Path | str) -> dict[str, object]:
    root = Path(root_path).expanduser().resolve()
    refreshed: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    for project in list_projects(root):
        project_path = root / str(project["path"])
        resume_payload = build_project_resume_payload(project_path)
        row = {
            "id": str(project["id"]),
            "title": str(resume_payload["project"]),
            "path": str(project["path"]),
            "resume_state": str(resume_payload["resume_state"]),
        }
        if row["resume_state"] != "refresh_brief":
            skipped.append({**row, "reason": "resume_state_ready"})
            continue
        brief_path = generate_study_brief(project_path)
        refreshed.append(
            {
                **row,
                "brief_path": brief_path.relative_to(project_path).as_posix(),
            }
        )
    return {
        "schema_version": 1,
        "quality_boundary": PROJECT_BRIEF_REFRESH_QUALITY_BOUNDARY,
        "root": str(root),
        "refreshed_count": len(refreshed),
        "skipped_count": len(skipped),
        "refreshed": refreshed,
        "skipped": skipped,
    }


def format_project_brief_refresh(root_path: Path | str) -> str:
    payload = refresh_project_briefs_payload(root_path)
    lines = [
        "# Project Brief Refresh",
        "",
        "## Summary",
        "",
        f"- Root: {payload['root']}",
        f"- Refreshed: {payload['refreshed_count']}",
        f"- Skipped: {payload['skipped_count']}",
        "",
        "## Refreshed Projects",
        "",
    ]
    refreshed = payload["refreshed"]
    if not refreshed:
        lines.append("- none")
    else:
        for project in refreshed:
            lines.append(
                f"- {project['id']} | {project['title']} | {project['brief_path']}"
            )
    lines.extend(["", "## Skipped Projects", ""])
    skipped = payload["skipped"]
    if not skipped:
        lines.append("- none")
    else:
        for project in skipped:
            lines.append(
                f"- {project['id']} | {project['title']} | "
                f"{project['resume_state']} | {project['reason']}"
            )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            (
                "This command writes study briefs only for child projects whose "
                "current resume state is refresh_brief. It does not refresh ready "
                "projects, generate reports, run repairs, call an LLM, approve "
                "artifacts, score learning, tutor, predict, or mutate learning-state truth."
            ),
            "",
        ]
    )
    return "\n".join(lines)
```

- [x] **Step 2: Register CLI command**

In `socrates/cli.py`, import `format_project_brief_refresh`, add:

```python
projects_refresh_briefs_parser = projects_subparsers.add_parser(
    "refresh-briefs",
    help="Generate study briefs for projects that need brief refresh.",
)
projects_refresh_briefs_parser.add_argument("--root", required=True, help="SocratesProjects root directory.")
projects_refresh_briefs_parser.set_defaults(func=_handle_projects_refresh_briefs)
```

and add:

```python
def _handle_projects_refresh_briefs(args: argparse.Namespace) -> int:
    print(format_project_brief_refresh(args.root), end="")
    return 0
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
- Modify: `docs/superpowers/plans/2026-06-04-v35-projects-refresh-briefs.md`
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.35**

Document `projects refresh-briefs` as an explicit collection writer that may create study brief artifacts and child project-log entries only for `refresh_brief` projects, not for ready projects.

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

Commit the v0.35 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.35 commit id, verification evidence, explicit writer boundary, and the reusable lesson that collection writers should use reader state for selection and constrain side effects to selected child projects.
