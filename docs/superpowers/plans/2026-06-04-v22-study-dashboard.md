# v0.22 Study Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only `socrates dashboard --project <project>` command that summarizes the operator-facing state of a learning project without making users mentally merge `status`, `queue`, and `report list` output.

**Architecture:** Add a small `socrates.dashboard` formatter that composes existing readers only: `collect_learning_queue`, `action_summary_lines`, `priority_queue_items`, `list_learning_reports`, `summarize_report_history`, `read_session_closeout_status`, and `read_multi_session_regression_status`. The dashboard is render-only and must not run audits, generate reports, repair artifacts, call LLMs, or mutate project state.

**Tech Stack:** Python stdlib, existing CLI/API helpers, `unittest`, no new dependencies.

---

### Task 1: Add Failing Dashboard Tests

**Files:**
- Add: `tests/test_dashboard.py`

- [x] **Step 1: Add empty-project dashboard CLI test**

Create a project and run:

```powershell
python -m socrates dashboard --project <project>
```

Assert output includes:

- `# Study Dashboard`
- `- Project: Group Theory`
- `- Workflow actions: 0`
- `- Session closeout: not_run`
- `- Multi-session regression: not_run`
- `- Report history: not_run`
- `## Action Summary`
- `- Completion: clear`
- `## Top Priority Actions`
- `- none`
- `## Report Health`
- `- weekly | missing | Weekly Learning Report | 07_exports/reports/weekly_report.md`
- `## Boundary`

- [x] **Step 2: Add dashboard priority-action test**

Create a project with one draft note at `04_atomic_notes/drafts/normal_subgroup.md`, run dashboard, and assert:

- `- Completion: in_progress`
- `- Open actions: 1`
- `- Needs human review: 1`
- `- Next action: notes:normal_subgroup | 04_atomic_notes/drafts/normal_subgroup.md`
- `- notes:normal_subgroup | 04_atomic_notes/drafts/normal_subgroup.md`

- [x] **Step 3: Run RED tests**

Run:

```powershell
python -m unittest tests.test_dashboard
```

Expected: tests fail because `dashboard` is not yet a known command.

### Task 2: Implement Read-Only Dashboard

**Files:**
- Add: `socrates/dashboard.py`
- Modify: `socrates/cli.py`

- [x] **Step 1: Add `format_study_dashboard`**

Implement:

```python
def format_study_dashboard(project_path: Path | str) -> str:
```

Render sections:

- `# Study Dashboard`
- `## Snapshot`
- `## Action Summary`
- `## Top Priority Actions`
- `## Report Health`
- `## Boundary`

- [x] **Step 2: Compose existing readers only**

Use existing readers and formatters; do not inspect generated JSON directly except for conservatively reading the project title from `project.yaml`.

- [x] **Step 3: Wire CLI command**

Add top-level:

```text
socrates dashboard --project <project>
```

and print the formatter output unchanged.

- [x] **Step 4: Run GREEN tests**

Run:

```powershell
python -m unittest tests.test_dashboard
```

Expected: dashboard tests pass.

### Task 3: Update Docs, Verify, Commit, and Capture Wiki

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/development_roadmap.md`
- Modify: `docs/development_log.md`
- Modify after commit: `D:\llmwiki\wiki\projects\socrates.md`
- Modify after commit: `D:\llmwiki\wiki\index.md`
- Modify after commit: `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.22**

Describe the dashboard as a read-only operator view over existing status/queue/report evidence. State that it does not create new truth, readiness gates, scores, predictions, plans, tutors, repairs, LLM calls, or project mutations.

- [x] **Step 2: Run verification**

Run:

```powershell
python -m unittest tests.test_dashboard
python -m unittest tests.test_dashboard tests.test_status_quality_summary tests.test_learning_queue tests.test_reports
python -m unittest discover -s tests
python -m compileall socrates
git diff --check
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
bash scripts/check.sh
```

- [x] **Step 3: Commit with Lore protocol**

Commit the v0.22 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.22 commit id, verification evidence, and the boundary that the dashboard is read-only composition over existing deterministic evidence.
