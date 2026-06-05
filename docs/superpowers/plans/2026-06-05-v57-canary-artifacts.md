# v0.57 Canary Artifacts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development before implementation. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an explicit `lifecycle canary --artifacts <dir>` option so operators can inspect the deterministic MVP canary project and report after the temporary run finishes.

**Architecture:** Keep the canary temporary-project-first and deterministic/offline. Only persist artifacts when the caller provides an output directory. Copy the generated canary project into that directory and write a JSON canary report there. Reject non-empty output directories to avoid overwriting user files.

**Tech Stack:** Python argparse, `tempfile.TemporaryDirectory`, `shutil.copytree`, existing `MvpLifecycleCanaryResult` payload, `unittest`, JSON output.

---

## File Map

- Modify `tests/test_lifecycle_canary.py`: add RED coverage for `lifecycle canary --artifacts <dir> --json`.
- Modify `socrates/lifecycle_canary.py`: persist the copied canary project plus `canary_report.json` when requested.
- Modify `socrates/cli.py`: register `--artifacts` and return a clear error for invalid artifact directories.
- Modify docs after GREEN: `README.md`, `docs/README.md`, `docs/development_log.md`, `docs/development_roadmap.md`.
- Modify this plan as checklist state changes.
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`.

## Acceptance Criteria

- `python -m socrates lifecycle canary --artifacts <dir> --json` exits 0 and emits JSON with `artifact_bundle.written: true`.
- The output directory contains `canary_report.json` and a copied `project/` tree with lifecycle evidence.
- The report JSON records the same canary payload and confirms `temporary_project.cleaned: true` after the temp project is removed.
- The command remains deterministic/offline and still does not accept or mutate a user project.
- Non-empty artifact output directories fail clearly instead of overwriting files.

---

### Task 1: RED Artifact Bundle Test

**Files:**
- Modify: `tests/test_lifecycle_canary.py`

- [x] **Step 1: Add failing artifact bundle JSON test**

Run `lifecycle canary --artifacts <dir> --json`, assert the JSON payload reports a written bundle, the output directory contains `canary_report.json`, the copied project includes lifecycle audit evidence, and the report records temp cleanup.

- [x] **Step 2: Run RED**

Run:

```powershell
python -m unittest tests.test_lifecycle_canary
```

Expected: fail because `--artifacts` is not registered yet.

---

### Task 2: Implement Artifact Persistence

**Files:**
- Modify: `socrates/lifecycle_canary.py`
- Modify: `socrates/cli.py`

- [x] **Step 1: Add artifact bundle metadata**

Extend the canary result payload with `artifact_bundle` metadata.

- [x] **Step 2: Copy the canary project and write report JSON**

When `--artifacts <dir>` is passed, copy the generated temporary project into `<dir>/project` and write `<dir>/canary_report.json` after temp cleanup has completed.

- [x] **Step 3: Protect existing user files**

Reject non-empty output directories with a clear CLI error.

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
- Modify `docs/superpowers/plans/2026-06-05-v57-canary-artifacts.md`
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.57**

Document `lifecycle canary --artifacts <dir>` as an explicit inspectability option, not a user-project runner or hidden artifact writer.

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

Commit the v0.57 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`, then push to `codex/v02-closure` so draft PR `https://github.com/Yaohua-Leo/Socrates/pull/5` includes the artifact bundle.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.57 commit id, verification evidence, artifact-bundle boundary, and the reusable lesson that product canaries should optionally preserve inspectable evidence without mutating real projects.
