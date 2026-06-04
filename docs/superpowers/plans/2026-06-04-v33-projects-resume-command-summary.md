# v0.33 Multi-Project Resume Command Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only recommended-command summary to `projects resume` so filtered collection views immediately show which child-project commands should be run next.

**Architecture:** Extend `socrates.project_resume.build_project_resume_index_payload` to derive `recommended_commands` and `recommended_command_count` from the already filtered project rows. Render the same derived command list in Markdown after the project rows so JSON and Markdown stay aligned and no child project is mutated.

**Tech Stack:** Python stdlib, argparse surface already in place, existing Socrates project resume payload, `unittest`, deterministic temporary project fixtures.

---

## File Map

- Modify `tests/test_project_index.py`: add RED coverage for Markdown and JSON recommended-command summaries, including state-filter behavior and read-only assertions.
- Modify `socrates/project_resume.py`: derive command rows from filtered project rows, expose `recommended_command_count` and `recommended_commands`, and render a Markdown `## Recommended Commands` section.
- Modify docs after GREEN: `README.md`, `docs/README.md`, `docs/development_log.md`, `docs/development_roadmap.md`.
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`.

## Acceptance Criteria

- `python -m socrates projects resume --root <root>` renders `Recommended commands: <n>` in the snapshot.
- Markdown output includes a `## Recommended Commands` section with one row per returned project whose `recommended_command` is not `none`.
- `python -m socrates projects resume --root <root> --state refresh_brief` shows command rows only for the filtered refresh-needed projects.
- `python -m socrates projects resume --root <root> --state ready` renders `Recommended commands: 0` and `- none`.
- `--json` output includes `recommended_command_count` and `recommended_commands` derived from the returned filtered rows.
- The command remains read-only: it does not create study brief artifacts, write a project index, or append project-log entries.

---

### Task 1: RED Recommended Command Summary Tests

**Files:**
- Modify: `tests/test_project_index.py`

- [x] **Step 1: Add failing Markdown command-summary test**

Add a test that:

1. Creates a `SocratesProjects` root with one ready project and one refresh-needed project.
2. Generates a current study brief only for the ready project.
3. Runs `projects resume --root <root> --state refresh_brief`.
4. Asserts the snapshot includes `Recommended commands: 1`.
5. Asserts `## Recommended Commands` contains the refresh-needed project command row.
6. Asserts the ready project command row is absent.
7. Asserts no child brief artifacts are written for the refresh-needed project and no `socrates_projects.json` is written.

- [x] **Step 2: Add failing JSON command-summary test**

Add a test that:

1. Reuses the same two-project shape.
2. Runs `projects resume --root <root> --state ready --json`.
3. Parses stdout as JSON and asserts `recommended_command_count: 0`.
4. Asserts `recommended_commands: []`.
5. Runs `projects resume --root <root> --state refresh_brief --json`.
6. Parses stdout as JSON and asserts `recommended_command_count: 1`.
7. Asserts the single command row contains `project_id`, `project_title`, `resume_state`, and `command` for the refresh-needed project.
8. Asserts no child brief artifacts are written for the refresh-needed project and no `socrates_projects.json` is written.

- [x] **Step 3: Run RED**

Run:

```powershell
python -m unittest tests.test_project_index
```

Expected: fail because `recommended_command_count` and `recommended_commands` are not in the collection payload and Markdown has no recommended-command summary section yet.

---

### Task 2: Add Derived Recommended Commands

**Files:**
- Modify: `socrates/project_resume.py`

- [x] **Step 1: Derive command rows after filtering**

Add a helper with this behavior:

```python
def _recommended_commands(projects: list[dict[str, object]]) -> list[dict[str, str]]:
    commands: list[dict[str, str]] = []
    for project in projects:
        command = str(project.get("recommended_command", "")).strip()
        if not command or command == "none":
            continue
        commands.append(
            {
                "project_id": str(project["id"]),
                "project_title": str(project["title"]),
                "resume_state": str(project["resume_state"]),
                "command": command,
            }
        )
    return commands
```

- [x] **Step 2: Add JSON payload fields**

After filtering project rows and computing readiness counts, call `_recommended_commands(projects)` and add:

```python
"recommended_command_count": len(recommended_commands),
"recommended_commands": recommended_commands,
```

to the payload.

- [x] **Step 3: Render Markdown command summary**

Render this snapshot row:

```python
f"- Recommended commands: {payload['recommended_command_count']}",
```

Then render a section after `## Projects`:

```python
"## Recommended Commands",
"",
```

with `- none` when the list is empty, or one row per command:

```python
f"- {command['project_id']} | {command['project_title']} | {command['resume_state']} | {command['command']}"
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
- Modify: `docs/superpowers/plans/2026-06-04-v33-projects-resume-command-summary.md`
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.33**

Document recommended-command summaries as derived read-only collection navigation, not command execution, batch automation, scoring, readiness gating, scanner behavior, report generation, LLM calls, or child-project mutation.

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

Commit the v0.33 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.33 commit id, verification evidence, read-only command-summary boundary, and the reusable lesson that actionable collection summaries should be derived from filtered rows rather than executed by the collection command.
