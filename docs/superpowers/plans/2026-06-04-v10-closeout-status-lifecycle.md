# v10 Closeout Status And Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make deterministic session closeout visible in `status` and lifecycle audit so generated workflow evidence cannot sit outside product readiness checks.

**Architecture:** Add a small neutral closeout-manifest reader with no dependency on workflow execution. Reuse that reader from CLI status and lifecycle audit. Treat only a valid `ready` closeout manifest as passing; missing, corrupt, malformed, or `needs_attention` manifests remain conservative failures.

**Tech Stack:** Python stdlib, existing Socrates manifest patterns, `unittest`, existing `status` and lifecycle audit surfaces.

---

## File Structure

- Create `socrates/workflow_manifest.py`: closeout manifest path, boundary constant, conservative reader/validator.
- Modify `socrates/workflow.py`: reuse the shared closeout manifest constants.
- Modify `socrates/cli.py`: print closeout status, sessions, and score in `status`.
- Modify `socrates/quality.py`: add closeout manifest lifecycle check.
- Modify `tests/test_session_closeout.py`: assert `status` reports closeout after `session closeout`.
- Modify `tests/test_status_quality_summary.py`: assert corrupt closeout manifest reports invalid.
- Modify `tests/test_lifecycle_audit.py`: update lifecycle totals and add closeout pass/fail coverage.
- Modify docs and llmwiki after verification.

## Task 1: Failing Status And Lifecycle Tests

**Files:**
- Modify: `tests/test_session_closeout.py`
- Modify: `tests/test_status_quality_summary.py`
- Modify: `tests/test_lifecycle_audit.py`

- [ ] **Step 1: Assert status after a successful closeout**

Extend the closeout CLI test to run:

```powershell
python -m socrates status --project <project>
```

Expected output:

```text
Session closeout: needs_attention
Session closeout sessions: session_0001 -> session_0002
Session closeout score: 0/100 (fail)
```

- [ ] **Step 2: Assert status handles corrupt closeout manifests**

In `tests/test_status_quality_summary.py`, write invalid JSON to `08_evals/session_closeout_manifest.json` and assert:

```text
Session closeout: invalid
Session closeout sessions: invalid
Session closeout score: invalid
```

- [ ] **Step 3: Update lifecycle missing-artifact expectation**

The empty project lifecycle test should expect one additional required check:

```text
Lifecycle audit passed 2/22 checks
- Session closeout manifest: fail
```

- [ ] **Step 4: Update full lifecycle fixture**

Import and call:

```python
close_tutoring_session(project, session_id="session_0001", next_session_id="session_0002")
```

The full lifecycle test should expect:

```text
Lifecycle audit passed 24/24 checks
- Session closeout manifest: pass
```

- [ ] **Step 5: Run red tests**

Run:

```powershell
python -m unittest tests.test_session_closeout tests.test_status_quality_summary tests.test_lifecycle_audit
```

Expected: fail because status does not print closeout lines and lifecycle does not include the closeout check.

## Task 2: Implement Closeout Manifest Reader

**Files:**
- Create: `socrates/workflow_manifest.py`
- Modify: `socrates/workflow.py`

- [ ] **Step 1: Add shared constants**

Implement:

```python
SESSION_CLOSEOUT_BOUNDARY = "deterministic_session_closeout"
SESSION_CLOSEOUT_MANIFEST_PATH = Path("08_evals") / "session_closeout_manifest.json"
```

- [ ] **Step 2: Add conservative reader**

Implement:

```python
def read_session_closeout_status(project_path: Path | str) -> dict[str, object] | None:
```

Return `None` when missing. Return `{"status": "invalid"}` for corrupt/malformed manifests. Return a normalized dict only when:

- `schema_version == 1`
- `quality_boundary == "deterministic_session_closeout"`
- `status in {"ready", "needs_attention"}`
- `session_id` and `next_session_id` are non-empty strings
- `session_score_status in {"pass", "fail"}`
- `session_score` is an integer from 0 through 100
- recorded artifact paths are safe relative paths that exist

- [ ] **Step 3: Add lifecycle predicate**

Implement:

```python
def has_ready_session_closeout(project_path: Path | str) -> bool:
    status = read_session_closeout_status(project_path)
    return status is not None and status.get("status") == "ready"
```

- [ ] **Step 4: Use the shared constants in workflow writer**

Change `socrates/workflow.py` to import `SESSION_CLOSEOUT_BOUNDARY` and `SESSION_CLOSEOUT_MANIFEST_PATH`, then write the manifest at `context.root / SESSION_CLOSEOUT_MANIFEST_PATH`.

## Task 3: Wire Status And Lifecycle

**Files:**
- Modify: `socrates/cli.py`
- Modify: `socrates/quality.py`

- [ ] **Step 1: Add status reader output**

Import `read_session_closeout_status` into `cli.py`. In `_handle_status`, read it and print:

```python
print(f"Session closeout: {_session_closeout_status_text(session_closeout_status)}")
print(f"Session closeout sessions: {_session_closeout_sessions_text(session_closeout_status)}")
print(f"Session closeout score: {_session_closeout_score_text(session_closeout_status)}")
```

Use text helpers matching existing session score helpers.

- [ ] **Step 2: Add lifecycle check**

Import `has_ready_session_closeout` into `quality.py` and add:

```python
"Session closeout manifest": has_ready_session_closeout(context.root),
```

next to session score and next-session handoff checks.

- [ ] **Step 3: Run focused tests**

Run:

```powershell
python -m unittest tests.test_session_closeout tests.test_status_quality_summary tests.test_lifecycle_audit
```

Expected: pass.

## Task 4: Docs, Verification, Commit, Wiki

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/development_roadmap.md`
- Modify: `docs/development_log.md`
- Modify after commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`

- [ ] **Step 1: Update docs**

Advance to v0.10-alpha. State that closeout is visible in status and lifecycle audit, with `needs_attention` remaining a lifecycle failure.

- [ ] **Step 2: Run full gates**

```powershell
python -m unittest discover -s tests
python -m compileall socrates
git diff --check
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
bash scripts/check.sh
```

- [ ] **Step 3: Commit and update llmwiki**

Commit with Lore protocol and `Co-authored-by: OmX <omx@oh-my-codex.dev>`. Update llmwiki with the reusable rule: workflow evidence must be visible in status/lifecycle before it counts as product readiness.

## Self-Review

- Spec coverage: The plan covers status visibility, lifecycle gating, corrupt manifest handling, docs, verification, commit, and llmwiki.
- Placeholder scan: No TODO/TBD placeholders or unspecified validation remain.
- Type consistency: The manifest path, boundary, status text, and lifecycle check names are consistent across tasks.
