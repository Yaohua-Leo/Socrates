# v0.14 Report Priority Actions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make weekly, monthly, and project summary reports show the same deterministic next-action priority view that operators see in `queue --section priority`.

**Architecture:** Reuse the existing `LearningQueue` collector and expose a public priority-item helper from `socrates.learning_queue`. Reports render a bounded `Priority Actions` section from existing queue items only, and report staleness includes workflow/regression artifacts that can change the priority snapshot.

**Tech Stack:** Python stdlib, existing report/queue modules, `unittest`, no new dependencies.

---

### Task 1: Add Failing Report Priority Tests

**Files:**
- Modify: `tests/test_reports.py`

- [x] **Step 1: Add a helper that writes a ready closeout fixture**

Add `_write_ready_closeout_manifest(project: Path) -> None` near the existing report fixture helpers. It should create the artifact paths required by `read_session_closeout_status` and then write `08_evals/session_closeout_manifest.json` with `status: "ready"`, `session_score_status: "pass"`, `session_score: 100`, and `quality_boundary: "deterministic_session_closeout"`.

- [x] **Step 2: Add a failing weekly report snapshot test**

Create a report fixture, add one extra draft note, write the ready closeout manifest, run `python -m socrates report weekly --project <project>`, and assert the report contains:

```text
## Priority Actions
- workflow:multi_session_regression | 08_evals/session_closeout_manifest.json | status: not_run; run with: socrates lifecycle regression --project <project>
```

Also assert that the workflow action appears before a `notes:` priority action.

- [x] **Step 3: Add a failing project summary snapshot test**

Create the same ready-closeout fixture, run `python -m socrates report project-summary --project <project>`, and assert the project summary contains `## Priority Actions` and the workflow priority row.

- [x] **Step 4: Add a failing stale-report test**

Generate a weekly report, then write the ready closeout manifest with a newer mtime. Run `python -m socrates report list --project <project> --status stale` and assert the weekly report is stale.

- [x] **Step 5: Run RED tests**

Run:

```powershell
python -m unittest tests.test_reports
```

Expected: the new tests fail because reports do not render priority actions and weekly staleness does not yet include workflow action inputs.

### Task 2: Implement Report Priority Snapshots

**Files:**
- Modify: `socrates/learning_queue.py`
- Modify: `socrates/reports.py`

- [x] **Step 1: Expose priority queue items**

Add a public helper in `socrates.learning_queue`:

```python
def priority_queue_items(queue: LearningQueue) -> list[QueueItem]:
    """Return existing queue items in deterministic operator priority order."""

    return _priority_actions(queue)
```

Update `_queue_sections` to call `priority_queue_items(queue)` instead of `_priority_actions(queue)`.

- [x] **Step 2: Pass priority actions into reports**

Import `QueueItem` and `priority_queue_items` in `socrates.reports`. In `generate_weekly_report`, `generate_monthly_report`, and `generate_project_summary`, collect `priority_actions=priority_queue_items(queue)` and pass that list into the corresponding report text builder.

- [x] **Step 3: Render report priority section**

Add `_priority_action_lines(items: list[QueueItem], *, limit: int = 5) -> list[str]`. It should render `- none` when empty, otherwise render `- {item_id} | {path}` plus ` | {detail}` when detail exists. If more than `limit` items exist, append `- ... {remaining} more`.

Add this section to weekly, monthly, and project summary text:

```text
## Priority Actions
```

- [x] **Step 4: Track priority inputs for report staleness**

Add `_priority_action_input_paths(project_root: Path) -> tuple[Path, ...]` covering:

```python
project_root / "08_evals" / "session_closeout_manifest.json"
project_root / "08_evals" / "multi_session_regression_manifest.json"
project_root / "08_evals" / "ingestion_quality_manifest.json"
project_root / "08_evals" / "note_quality_manifest.json"
project_root / "08_evals" / "exercise_quality_manifest.json"
project_root / "08_evals" / "tutoring_quality_manifest.json"
project_root / "08_evals" / "tool_verification_quality_manifest.json"
```

Include that tuple in weekly, monthly, and project-summary `_report_input_paths`.

- [x] **Step 5: Run GREEN focused tests**

Run:

```powershell
python -m unittest tests.test_reports
```

Expected: all report tests pass.

### Task 3: Update Docs, Verify, Commit, and Capture Wiki

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/development_roadmap.md`
- Modify: `docs/development_log.md`
- Modify after commit: `D:\llmwiki\wiki\projects\socrates.md`
- Modify after commit: `D:\llmwiki\wiki\index.md`
- Modify after commit: `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.14**

Describe priority action snapshots in reports as operator UX over existing queue evidence, not a new readiness gate or score.

- [x] **Step 2: Run full verification**

Run:

```powershell
python -m unittest tests.test_reports tests.test_learning_queue
python -m unittest discover -s tests
python -m compileall socrates
git diff --check
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
bash scripts/check.sh
```

- [x] **Step 3: Commit with Lore protocol**

Commit the v0.14 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with v0.14 commit id, verification evidence, and the boundary that report priority snapshots are renderings of existing queue evidence.
