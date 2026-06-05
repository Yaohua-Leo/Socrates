# v0.11 Multi-Session Regression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic multi-session regression surface that proves a project can carry one completed session into the next visible session without trusting LLM output.

**Architecture:** Create a small `socrates.multi_session` module that reads persisted session, closeout, handoff, score, and report artifacts, writes a regression report plus manifest, and exposes a normalized status reader. Wire it into `lifecycle regression`, `status`, and lifecycle audit so the evidence is not isolated from product readiness checks.

**Tech Stack:** Python stdlib, existing Socrates context/write helpers, `unittest`, no new dependencies.

---

### Task 1: Write Regression Behavior Tests

**Files:**
- Create: `tests/test_multi_session_regression.py`

- [ ] **Step 1: Write the failing API/CLI pass test**

Add a fixture with `session_0001`, `session_0002`, a ready closeout from the first to the second, then assert `python -m socrates lifecycle regression --project <project>` writes `08_evals/multi_session_regression.md` and `08_evals/multi_session_regression_manifest.json` with status `pass`.

- [ ] **Step 2: Write the failing conservative failure test**

Delete or omit `03_sessions/session_0002` while the closeout manifest points to it, then assert the regression status is `fail`, the issue names the missing next session directory, and the CLI exits non-zero.

- [ ] **Step 3: Write status and lifecycle visibility tests**

Assert `status` prints `Multi-session regression: pass` after a passing run, invalid manifests print `invalid`, and lifecycle audit includes `Multi-session regression`.

### Task 2: Implement Regression Module

**Files:**
- Create: `socrates/multi_session.py`

- [ ] **Step 1: Add result dataclass and constants**

Define `MULTI_SESSION_REGRESSION_BOUNDARY`, `MULTI_SESSION_REGRESSION_REPORT_PATH`, and `MULTI_SESSION_REGRESSION_MANIFEST_PATH`.

- [ ] **Step 2: Implement `run_multi_session_regression(project_path)`**

Read the ready closeout status, verify both session directories exist, verify the next-session handoff manifest targets the next session, verify session score/report artifacts exist through the closeout reader, and write a report plus manifest. Status is `pass` only when all deterministic checks pass.

- [ ] **Step 3: Implement `read_multi_session_regression_status(project_path)` and `has_passing_multi_session_regression(project_path)`**

Return `None` for not run, `{"status": "invalid"}` for corrupt/malformed manifests, and normalized pass/fail data for valid manifests.

### Task 3: Wire CLI, Status, and Lifecycle

**Files:**
- Modify: `socrates/cli.py`
- Modify: `socrates/quality.py`

- [ ] **Step 1: Add `lifecycle regression --project <project>`**

Print status, passed/total checks, issue summary, report path, and manifest path. Return zero only for pass.

- [ ] **Step 2: Add status summary lines**

Print `Multi-session regression: <not run|invalid|pass|fail>`, `Multi-session regression checks: <none|invalid|passed/total>`, and `Multi-session regression issues: <none|invalid|...>`.

- [ ] **Step 3: Add lifecycle gate**

Add `Multi-session regression` to lifecycle audit using the passing reader.

### Task 4: Update Docs and Commit

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/development_roadmap.md`
- Modify: `docs/development_log.md`

- [ ] **Step 1: Update v0.11 product status**

Document the command, deterministic boundary, and status/lifecycle visibility.

- [ ] **Step 2: Run verification**

Run focused tests, full `unittest discover`, `compileall`, `git diff --check`, PowerShell check, and bash check.

- [ ] **Step 3: Commit with Lore protocol**

Use a why-first commit message with `Tested:` evidence and the required `Co-authored-by: OmX <omx@oh-my-codex.dev>` trailer.
