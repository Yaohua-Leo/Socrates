# v0.56 MVP Lifecycle Canary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development before implementation. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic `lifecycle canary` command that runs the minimum v1.0 learning-project scenario in a temporary project and reports whether the core Socrates lifecycle still works end to end.

**Architecture:** Keep the canary as a QA/readiness command over a temporary project. It should reuse existing project, reference, KB, tutoring, note, exercise, state, report, closeout, regression, benchmark, and audit APIs. It must not mutate a caller-supplied project or introduce live LLM/provider/tool dependencies.

**Tech Stack:** Python argparse, `tempfile.TemporaryDirectory`, existing Socrates APIs, deterministic fixtures, `unittest`, JSON output for wrapper/plugin consumption.

---

## File Map

- Add `tests/test_lifecycle_canary.py`: RED coverage for prose and JSON canary CLI behavior.
- Add `socrates/lifecycle_canary.py`: build and run the deterministic temporary MVP scenario.
- Modify `socrates/cli.py`: register `lifecycle canary` and render prose/JSON output.
- Modify docs after GREEN: `README.md`, `docs/README.md`, `docs/development_log.md`, `docs/development_roadmap.md`.
- Modify this plan as checklist state changes.
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`.

## Acceptance Criteria

- `python -m socrates lifecycle canary` exits 0 and reports a passing deterministic MVP lifecycle canary.
- `python -m socrates lifecycle canary --json` exits 0 and emits valid deterministic JSON with `schema_version: 1`, `quality_boundary: deterministic_mvp_lifecycle_canary`, scenario metadata, lifecycle audit counts, artifact counts, and pass/fail status.
- The canary exercises the minimum product scenario: initialize a project, create/import/curate/build reference knowledge, generate a learning plan, run two scripted sessions, generate/review/export notes, generate/validate/bank exercises, record/grade an exercise attempt, update learning state and review schedule, generate reports, close out a session, run multi-session regression, run benchmark, and audit lifecycle readiness.
- The canary uses only temporary project state and cleans it by default.
- The canary stays deterministic and offline. It is not a live LLM call, UI, plugin, OCR/PDF backend, proof assistant, user-project writer, or substitute for real learner validation.

---

### Task 1: RED Canary CLI Tests

**Files:**
- Add: `tests/test_lifecycle_canary.py`

- [x] **Step 1: Add failing prose canary test**

Run `lifecycle canary` and assert a passing human-facing summary, lifecycle audit counts, cleaned temporary project boundary, and no stderr.

- [x] **Step 2: Add failing JSON canary test**

Run `lifecycle canary --json`, parse the payload, and assert deterministic schema, quality boundary, pass status, lifecycle counts, artifact counts, and no prose marker.

- [x] **Step 3: Run RED**

Run:

```powershell
python -m unittest tests.test_lifecycle_canary
```

Expected: fail because `lifecycle canary` is not registered yet.

---

### Task 2: Add MVP Lifecycle Canary

**Files:**
- Add: `socrates/lifecycle_canary.py`
- Modify: `socrates/cli.py`

- [x] **Step 1: Implement deterministic canary scenario**

Create a helper that runs the minimum Socrates learning scenario inside a temporary directory and returns structured pass/fail evidence.

- [x] **Step 2: Register CLI command**

Add `lifecycle canary` with optional `--json`, using the helper payload for both prose and JSON.

- [x] **Step 3: Preserve safety boundary**

Do not accept `--project`; do not write outside the temporary project; do not call LLMs or external tools.

- [x] **Step 4: Run GREEN**

Run:

```powershell
python -m unittest tests.test_lifecycle_canary
```

Expected: tests OK.

---

### Task 3: Docs, Verification, Commit, and Wiki

**Files:**
- Modify `README.md`
- Modify `docs/README.md`
- Modify `docs/development_log.md`
- Modify `docs/development_roadmap.md`
- Modify `docs/superpowers/plans/2026-06-05-v56-mvp-lifecycle-canary.md`
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.56**

Document `lifecycle canary` as a deterministic temporary-project MVP regression, not a user-project writer, live LLM, UI/plugin, OCR backend, proof assistant, or real learner validation.

- [x] **Step 2: Run verification**

Run:

```powershell
python -m unittest tests.test_lifecycle_canary
python -m unittest tests.test_lifecycle_canary tests.test_lifecycle_audit tests.test_v02_cli_flow tests.test_v04_exercise_flow tests.test_status_quality_summary
python -m unittest discover -s tests
python -m compileall socrates
git diff --check
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
bash scripts/check.sh
```

- [x] **Step 3: Commit and publish to the existing draft PR**

Commit the v0.56 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`, then push to `codex/v02-closure` so draft PR `https://github.com/Yaohua-Leo/Socrates/pull/5` includes the canary.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.56 commit id, verification evidence, canary boundary, and the reusable lesson that long-product goals need deterministic canaries for full workflow drift, not only unit-level command checks.
