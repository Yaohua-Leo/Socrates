# v0.27 Project Resume Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only `resume` command that tells a returning learner whether their saved study brief is ready to use or should be regenerated before continuing.

**Architecture:** Create a small `socrates.resume` formatter over existing reader APIs: `summarize_study_brief` for saved brief freshness and `project_title` for display. Wire a top-level CLI command that prints a compact Markdown resume card without writing artifacts or changing project logs.

**Tech Stack:** Python argparse, existing Socrates CLI/readers, `unittest`, deterministic filesystem fixtures.

---

## File Map

- Create `socrates/resume.py`: render the read-only resume card and compute a stable resume state from study brief status.
- Modify `socrates/cli.py`: register top-level `resume --project <project>` and call the formatter.
- Create `tests/test_resume.py`: add RED/GREEN CLI tests for missing, current, and stale brief states.
- Modify docs after GREEN: `README.md`, `docs/README.md`, `docs/development_log.md`, `docs/development_roadmap.md`.
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`.

## Acceptance Criteria

- `python -m socrates resume --project <project>` prints `# Resume Project`.
- When no study brief exists, output includes `- Resume state: refresh_brief`, `- Study brief: not_run`, and a `brief generate` recommended command.
- When the saved study brief is current, output includes `- Resume state: ready`, `- Study brief: current`, `- Recommended command: none`, and the current next action.
- When the saved study brief is stale, output includes `- Resume state: refresh_brief`, `- Study brief: stale`, the current next action, and a `brief generate` recommended command.
- `resume` is read-only: it does not create `study_brief.md`, `study_brief_manifest.json`, or append `Generated study brief.` to the project log.

---

### Task 1: RED Resume Tests

**Files:**
- Create: `tests/test_resume.py`

- [x] **Step 1: Add failing CLI tests**

Add tests that:

1. Run `resume --project <project>` on a fresh project and assert missing-brief `refresh_brief` output plus no written brief artifacts or `Generated study brief.` log entry.
2. Run `brief generate`, then `resume`, and assert `Resume state: ready`, `Study brief: current`, `Recommended command: none`, and the first next action.
3. Run `brief generate` on an empty project, add a draft note, then `resume`, and assert `Resume state: refresh_brief`, `Study brief: stale`, and the `brief generate` recommended command.

- [x] **Step 2: Run RED**

Run:

```powershell
python -m unittest tests.test_resume
```

Expected: fail because `resume` is not registered yet.

---

### Task 2: Add Read-Only Resume Formatter and CLI

**Files:**
- Create: `socrates/resume.py`
- Modify: `socrates/cli.py`

- [x] **Step 1: Implement `format_project_resume`**

Create `format_project_resume(project_path: Path | str) -> str`. It should load the project, summarize the study brief, derive `ready` only when `study_brief.status == "current"`, otherwise derive `refresh_brief`, and print these rows:

```text
# Resume Project

## Snapshot

- Project: <project title>
- Root: <project root>
- Resume state: <ready|refresh_brief>
- Study brief: <status>
- Study brief path: <path>
- Current next action: <current_next_action>
- Recommended command: <none|python -m socrates brief generate --project "<project root>">
```

Add a short `## Boundary` section that states this command reads existing deterministic evidence and does not write artifacts.

- [x] **Step 2: Register CLI command**

Add top-level `resume --project <project>` to `socrates/cli.py` and map it to `_handle_resume`, which prints `format_project_resume(args.project)`.

- [x] **Step 3: Run GREEN**

Run:

```powershell
python -m unittest tests.test_resume tests.test_study_brief tests.test_dashboard tests.test_status_quality_summary
```

Expected: tests OK.

---

### Task 3: Docs, Verification, Commit, and Wiki

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/development_log.md`
- Modify: `docs/development_roadmap.md`
- Modify: `docs/superpowers/plans/2026-06-04-v27-resume-command.md`
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.27**

Document `resume` as a read-only returning-learner command and explicitly state that it recommends `brief generate` when the saved brief is missing, stale, or invalid but does not run that command.

- [x] **Step 2: Run verification**

Run:

```powershell
python -m unittest tests.test_resume tests.test_study_brief tests.test_dashboard tests.test_status_quality_summary tests.test_learning_queue
python -m unittest discover -s tests
python -m compileall socrates
git diff --check
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
bash scripts/check.sh
```

- [x] **Step 3: Commit with Lore protocol**

Commit the v0.27 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.27 commit id, verification evidence, resume command boundary, and the returning-learner UX lesson.
