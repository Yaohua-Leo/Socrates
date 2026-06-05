# v0.34 Multi-Project Resume Commands Output Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `projects resume --commands` so users can print only the recommended child-project commands from the active read-only collection resume filter.

**Architecture:** Reuse `build_project_resume_index_payload(root_path, state_filter=...)` and its derived `recommended_commands` rows. Add a small commands-only formatter plus a mutually exclusive CLI output mode so Markdown, JSON, and commands-only output do not conflict.

**Tech Stack:** Python argparse mutually exclusive output flags, existing Socrates project resume payload, `unittest`, deterministic temporary project fixtures.

---

## File Map

- Modify `tests/test_project_index.py`: add RED coverage for commands-only output, empty ready-only command output, and JSON/commands mutual exclusion.
- Modify `socrates/project_resume.py`: add `format_project_resume_commands(root_path, *, state_filter="all")`.
- Modify `socrates/cli.py`: import the formatter, add `--commands` as a mutually exclusive output flag with `--json`, and route it in `_handle_projects_resume`.
- Modify docs after GREEN: `README.md`, `docs/README.md`, `docs/development_log.md`, `docs/development_roadmap.md`.
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`.

## Acceptance Criteria

- `python -m socrates projects resume --root <root> --state refresh_brief --commands` prints only command lines for returned projects with non-`none` recommended commands.
- Commands-only output contains no Markdown headings, project rows, counts, or boundary text.
- `python -m socrates projects resume --root <root> --state ready --commands` exits 0 with empty stdout when there are no returned recommended commands.
- `--commands` and `--json` are mutually exclusive.
- The command remains read-only: it does not create study brief artifacts, write a project index, or append project-log entries.

---

### Task 1: RED Commands Output Tests

**Files:**
- Modify: `tests/test_project_index.py`

- [x] **Step 1: Add failing commands-only output test**

Add a test that:

1. Creates a `SocratesProjects` root with one ready project and one refresh-needed project.
2. Generates a current study brief only for the ready project.
3. Runs `projects resume --root <root> --state refresh_brief --commands`.
4. Asserts stdout equals exactly one `python -m socrates brief generate --project "<fresh_project>"` line with a trailing newline.
5. Asserts stdout does not include `# Project Resume Index`, `Recommended commands`, `ring_theory |`, or boundary text.
6. Asserts no child brief artifacts are written for the refresh-needed project and no `socrates_projects.json` is written.

- [x] **Step 2: Add failing empty commands-only output test**

Add a test that:

1. Reuses a two-project shape with the ready project having a current brief.
2. Runs `projects resume --root <root> --state ready --commands`.
3. Asserts return code is 0.
4. Asserts stdout is an empty string.
5. Asserts the command remains read-only for the refresh-needed project.

- [x] **Step 3: Add failing output-mode conflict test**

Add a test that:

1. Creates a fresh project root with one project.
2. Runs `projects resume --root <root> --json --commands`.
3. Asserts the return code is non-zero.
4. Asserts stderr mentions that `--commands` is not allowed with `--json` or otherwise reports an argument conflict.
5. Asserts no `socrates_projects.json` is written.

- [x] **Step 4: Run RED**

Run:

```powershell
python -m unittest tests.test_project_index
```

Expected: fail because `--commands` is not registered yet.

---

### Task 2: Add Commands-Only Formatter and CLI Mode

**Files:**
- Modify: `socrates/project_resume.py`
- Modify: `socrates/cli.py`

- [x] **Step 1: Add commands-only formatter**

Add:

```python
def format_project_resume_commands(
    root_path: Path | str,
    *,
    state_filter: str = "all",
) -> str:
    payload = build_project_resume_index_payload(root_path, state_filter=state_filter)
    commands = [str(command["command"]) for command in payload["recommended_commands"]]
    if not commands:
        return ""
    return "\n".join(commands) + "\n"
```

- [x] **Step 2: Register mutually exclusive output flags**

In `socrates/cli.py`, import `format_project_resume_commands`, then replace the standalone `--json` argument with:

```python
projects_resume_output_group = projects_resume_parser.add_mutually_exclusive_group()
projects_resume_output_group.add_argument(
    "--json",
    action="store_true",
    help="Print the project resume index as deterministic JSON.",
)
projects_resume_output_group.add_argument(
    "--commands",
    action="store_true",
    help="Print only recommended child-project commands.",
)
```

- [x] **Step 3: Route commands output**

Update `_handle_projects_resume` so it handles output modes in this order:

```python
if args.json:
    ...
elif args.commands:
    print(format_project_resume_commands(args.root, state_filter=args.state), end="")
else:
    print(format_project_resume_index(args.root, state_filter=args.state), end="")
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
- Modify: `docs/superpowers/plans/2026-06-04-v34-projects-resume-commands-output.md`
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.34**

Document commands-only output as a read-only copy/output mode over derived recommended commands, not command execution, batch automation, scoring, readiness gating, scanner behavior, report generation, LLM calls, or child-project mutation.

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

Commit the v0.34 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.34 commit id, verification evidence, commands-only output boundary, and the reusable lesson that command-copy surfaces should stay output-only and reuse structured command rows.
