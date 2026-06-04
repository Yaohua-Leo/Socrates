# v0.28 Resume JSON Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only `resume --json` output so future UI/plugin wrappers can consume the returning-learner resume state without parsing Markdown.

**Architecture:** Refactor `socrates.resume` to build one structured payload, render Markdown from that payload, and expose the same payload as deterministic JSON through the CLI. Keep the payload derived only from existing reader-owned evidence.

**Tech Stack:** Python stdlib JSON, argparse, existing Socrates CLI/readers, `unittest`, deterministic filesystem fixtures.

---

## File Map

- Modify `socrates/resume.py`: add `build_project_resume_payload`, render Markdown from the payload, and keep `format_project_resume` behavior stable.
- Modify `socrates/cli.py`: add `resume --json` and print deterministic JSON when requested.
- Modify `tests/test_resume.py`: add RED/GREEN coverage for JSON output and stable Markdown compatibility.
- Modify docs after GREEN: `README.md`, `docs/README.md`, `docs/development_log.md`, `docs/development_roadmap.md`.
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`.

## Acceptance Criteria

- `python -m socrates resume --project <project> --json` prints valid JSON.
- JSON output includes `schema_version: 1`, `quality_boundary: deterministic_project_resume`, `project`, `root`, `resume_state`, `study_brief`, `study_brief_path`, `current_next_action`, and `recommended_command`.
- JSON output is read-only and does not create `study_brief.md`, `study_brief_manifest.json`, or append project-log entries.
- Markdown `python -m socrates resume --project <project>` output remains stable.
- `resume_state` and `recommended_command` values match Markdown output for current and refresh-needed states.

---

### Task 1: RED Resume JSON Tests

**Files:**
- Modify: `tests/test_resume.py`

- [x] **Step 1: Add failing JSON tests**

Add tests that:

1. Run `resume --project <project> --json` on a fresh project, parse JSON, assert `resume_state: refresh_brief`, `study_brief: not_run`, the deterministic boundary fields, and no written brief artifacts or project-log entry.
2. Run `brief generate`, then `resume --json`, and assert `resume_state: ready`, `study_brief: current`, `recommended_command: none`, and the same current next action as Markdown output.

- [x] **Step 2: Run RED**

Run:

```powershell
python -m unittest tests.test_resume
```

Expected: fail because `resume --json` is not registered and no structured payload API exists yet.

---

### Task 2: Add Structured Resume Payload

**Files:**
- Modify: `socrates/resume.py`
- Modify: `socrates/cli.py`

- [x] **Step 1: Build payload**

Add `build_project_resume_payload(project_path: Path | str) -> dict[str, object]` with these keys:

```python
{
    "schema_version": 1,
    "quality_boundary": "deterministic_project_resume",
    "project": "<project title>",
    "root": "<project root>",
    "resume_state": "<ready|refresh_brief>",
    "study_brief": "<status>",
    "study_brief_path": "07_exports/briefs/study_brief.md",
    "current_next_action": "<current next action>",
    "recommended_command": "<none|python -m socrates brief generate --project \"<project root>\">",
}
```

- [x] **Step 2: Render Markdown from payload**

Keep `format_project_resume` output stable by rendering its rows from the payload instead of recomputing values.

- [x] **Step 3: Wire CLI JSON output**

Add `--json` to the `resume` parser. When set, `_handle_resume` prints `json.dumps(payload, indent=2, sort_keys=True)` plus a trailing newline; otherwise it prints Markdown.

- [x] **Step 4: Run GREEN**

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
- Modify: `docs/superpowers/plans/2026-06-04-v28-resume-json.md`
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.28**

Document `resume --json` as a read-only machine-readable resume surface for future UI/plugin consumers, not as a new writer or readiness gate.

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

Commit the v0.28 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.28 commit id, verification evidence, JSON boundary, and the wrapper-facing state lesson.
