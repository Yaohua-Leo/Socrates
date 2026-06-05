# v0.26 Study Brief Status Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only `brief status` command so users can inspect study brief freshness without regenerating the brief or running full project status.

**Architecture:** Convert the top-level `brief` parser into a command group with `brief generate` and `brief status`, while preserving the existing `brief --project <project>` write behavior for compatibility. Reuse `socrates.study_brief_status.summarize_study_brief` and add a small CLI formatter that prints the same manifest-backed fields without writing artifacts.

**Tech Stack:** Python argparse, existing Socrates CLI/status reader, `unittest`, deterministic filesystem fixtures.

---

## File Map

- Modify `socrates/cli.py`: add `brief generate` and `brief status` parsing, preserve legacy `brief --project`, and add a read-only status handler.
- Modify `tests/test_study_brief.py`: add RED/GREEN coverage for the new command and compatibility behavior.
- Modify docs after GREEN: `README.md`, `docs/README.md`, `docs/development_log.md`, `docs/development_roadmap.md`.
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`.

## Acceptance Criteria

- `python -m socrates brief status --project <project>` prints study brief status, path, recorded next action, and current next action.
- `brief status` is read-only: it does not create `study_brief.md`, `study_brief_manifest.json`, or append `Generated study brief.` to the project log.
- `python -m socrates brief generate --project <project>` writes the same artifacts as the current `brief` command.
- Existing `python -m socrates brief --project <project>` remains supported.
- Malformed manifests still surface as `invalid` through `brief status`.

---

### Task 1: RED CLI Tests

**Files:**
- Modify: `tests/test_study_brief.py`

- [x] **Step 1: Add failing `brief status` tests**

Add tests that:

1. Run `brief status --project <project>` on a project with no brief and assert the command exits 0, prints `Study brief: not_run`, `Study brief path: 07_exports/briefs/study_brief.md`, `Study brief recorded next action: none`, and `Study brief current next action: none`, while leaving `07_exports/briefs/study_brief.md` absent and not appending `Generated study brief.` to `00_meta/project_log.md`.
2. Run `brief generate --project <project>`, then run `brief status --project <project>` and assert it prints `Study brief: current` plus the recorded/current next action.
3. Corrupt `07_exports/briefs/study_brief_manifest.json`, then run `brief status --project <project>` and assert it prints `Study brief: invalid`.

- [x] **Step 2: Run RED**

Run:

```powershell
python -m unittest tests.test_study_brief
```

Expected: fail because `brief status` and `brief generate` are not registered yet.

---

### Task 2: Add Read-Only Brief Status Command

**Files:**
- Modify: `socrates/cli.py`

- [x] **Step 1: Preserve legacy `brief --project`**

Keep `python -m socrates brief --project <project>` mapped to the existing write handler.

- [x] **Step 2: Add `brief generate`**

Register `brief generate --project <project>` and map it to the existing write handler that calls `generate_study_brief`.

- [x] **Step 3: Add `brief status`**

Register `brief status --project <project>` and map it to a new read-only handler that calls `summarize_study_brief` and prints:

```text
Study brief: <status>
Study brief path: <path>
Study brief recorded next action: <recorded_next_action>
Study brief current next action: <current_next_action>
```

- [x] **Step 4: Run GREEN**

Run:

```powershell
python -m unittest tests.test_study_brief tests.test_dashboard tests.test_status_quality_summary
```

Expected: tests OK.

---

### Task 3: Docs, Verification, Commit, and Wiki

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/development_log.md`
- Modify: `docs/development_roadmap.md`
- Modify: `docs/superpowers/plans/2026-06-04-v26-brief-status-command.md`
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.26**

Document `brief status` as a read-only manifest-backed freshness command, `brief generate` as the explicit write command, and legacy `brief --project` compatibility.

- [x] **Step 2: Run verification**

Run:

```powershell
python -m unittest tests.test_study_brief tests.test_dashboard tests.test_status_quality_summary tests.test_learning_queue
python -m unittest discover -s tests
python -m compileall socrates
git diff --check
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
bash scripts/check.sh
```

- [x] **Step 3: Commit with Lore protocol**

Commit the v0.26 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.26 commit id, verification evidence, command boundary, and the reader/write-command separation lesson.
