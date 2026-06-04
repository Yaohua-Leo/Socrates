# v0.21 Long-Term Multi-Session Regression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `lifecycle regression` exercise the realistic long-session product loop instead of stopping at artifact existence. After a regression run, project-summary/status/report-history surfaces should reflect the latest regression manifest.

**Architecture:** Keep `socrates.multi_session` as the lifecycle-regression owner. It should write the regression manifest, refresh the project summary through a delayed `socrates.reports.generate_project_summary` import to avoid top-level cycles, then write the final regression report/manifest with long-term surface checks. Report-history parsing remains owned by `socrates.reports`.

**Tech Stack:** Python stdlib, existing CLI/API helpers, `unittest`, no new dependencies.

---

### Task 1: Add Failing Long-Term Regression Tests

**Files:**
- Modify: `tests/test_multi_session_regression.py`

- [x] **Step 1: Extend the passing regression CLI test**

Update `test_lifecycle_regression_cli_records_passing_multi_session_loop` to expect the realistic long-chain regression:

- `Regression checks: 7/7`
- manifest `passed_checks == 7`
- manifest `total_checks == 7`
- CLI output includes `Project summary:`
- regression report contains:
  - `- Project summary refresh: pass`
  - `- Project summary long-term surfaces: pass`
  - `- Report history artifact: pass`

- [x] **Step 2: Assert refreshed project summary and status consistency**

In the same passing test, after `lifecycle regression`:

- read `07_exports/reports/project_summary.md`
- assert it includes `## Report History Snapshot`
- assert it does not include `workflow:multi_session_regression`
- run `python -m socrates status --project <project>`
- assert status includes:
  - `Workflow actions: 0`
  - `Report history: current`
  - `Latest report history: #3 project-summary attention`

- [x] **Step 3: Update the missing-next-session regression expectation**

Update `test_lifecycle_regression_cli_fails_when_next_session_is_missing` for the larger check set:

- `Regression checks: 6/7`
- manifest `passed_checks == 6`
- manifest `total_checks == 7`
- issue remains exactly `missing next session artifacts: session_0002`

- [x] **Step 4: Run RED tests**

Run:

```powershell
python -m unittest tests.test_multi_session_regression
```

Expected: the updated tests fail because regression still reports 5 checks, does not refresh project summary after the regression manifest, and does not print a project-summary path.

### Task 2: Refresh Project Summary and Add Surface Checks

**Files:**
- Modify: `socrates/multi_session.py`
- Modify: `socrates/cli.py`

- [x] **Step 1: Add project-summary path to regression result/manifest**

Add `project_summary_path: Path` to `MultiSessionRegressionResult` and persist `project_summary_path` in the regression manifest as `07_exports/reports/project_summary.md`.

- [x] **Step 2: Write manifest before refresh, then write final manifest**

In `run_multi_session_regression`:

1. Compute the core checks.
2. Write a preliminary regression report/manifest from the core checks.
3. Refresh the project summary through a function-local import of `generate_project_summary`.
4. Add long-term checks over the refreshed project summary and report history.
5. Write the final report/manifest and return the final result.

- [x] **Step 3: Add long-term checks**

Add:

- `_check_project_summary_surfaces(project_root)` requiring these sections:
  - `## Priority Actions`
  - `## Recommended Focus`
  - `## Action Summary`
  - `## Repair Paths`
  - `## Risk Summary`
  - `## Trend Summary`
  - `## Report History Snapshot`
  - `## Session Score Snapshot`
  - `## Next Session Handoff Snapshot`
- `_check_report_history_artifact(project_root)` using `summarize_report_history` from `socrates.reports` and requiring `status == "current"` with at least one snapshot.

- [x] **Step 4: Print refreshed project summary path**

In `_handle_lifecycle_regression`, print:

```text
Project summary: <path>
```

- [x] **Step 5: Run GREEN tests**

Run:

```powershell
python -m unittest tests.test_multi_session_regression
```

Expected: all multi-session regression tests pass.

### Task 3: Update Docs, Verify, Commit, and Capture Wiki

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/development_roadmap.md`
- Modify: `docs/development_log.md`
- Modify after commit: `D:\llmwiki\wiki\projects\socrates.md`
- Modify after commit: `D:\llmwiki\wiki\index.md`
- Modify after commit: `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.21**

Describe lifecycle regression as a realistic long-chain check that refreshes project-summary/status/report-history surfaces after writing the regression manifest. State that it is deterministic regression evidence, not autonomous tutoring, scoring, prediction, proof, or learning-state truth.

- [x] **Step 2: Run verification**

Run:

```powershell
python -m unittest tests.test_multi_session_regression
python -m unittest tests.test_multi_session_regression tests.test_reports tests.test_status_quality_summary tests.test_learning_queue tests.test_session_closeout tests.test_lifecycle_audit
python -m unittest discover -s tests
python -m compileall socrates
git diff --check
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
bash scripts/check.sh
```

- [x] **Step 3: Commit with Lore protocol**

Commit the v0.21 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.21 commit id, verification evidence, and the boundary that long-term regression refreshes and audits deterministic surfaces without becoming a tutor, score, prediction, proof, readiness shortcut, or learning-state truth.
