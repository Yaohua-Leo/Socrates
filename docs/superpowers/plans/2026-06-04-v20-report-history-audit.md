# v0.20 Report History Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make report risk history auditable from status and project-summary output without requiring users to open `risk_history.json`.

**Architecture:** Keep `risk_history.json` owned by `socrates.reports`; expose a small public summary reader from that module. `status` will print health/count/latest snapshot lines. Project-summary reports will render a `Report History Snapshot` section using a preview that includes the current report snapshot before the snapshot is persisted.

**Tech Stack:** Python stdlib, existing report/status helpers, `unittest`, no new dependencies.

---

### Task 1: Add Failing Report-History Audit Tests

**Files:**
- Modify: `tests/test_status_quality_summary.py`
- Modify: `tests/test_reports.py`

- [x] **Step 1: Add a status report-history test**

Add this import to `tests/test_status_quality_summary.py`:

```python
from socrates.state import LearningStatePatch, update_learning_state
from socrates.context import load_project
```

Add this test near other status summary tests:

```python
    def test_status_cli_summarizes_report_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))

            first = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "report",
                    "weekly",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(first.returncode, 0, first.stderr)

            update_learning_state(
                load_project(project),
                LearningStatePatch(concept_mastery={"quotient_group": 0.42}),
            )
            second = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "report",
                    "weekly",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(second.returncode, 0, second.stderr)

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Report history: current", status.stdout)
            self.assertIn("Report history snapshots: 2", status.stdout)
            self.assertIn("Latest report history: #2 weekly attention", status.stdout)
```

- [x] **Step 2: Add a project-summary report-history section test**

Add this test near the trend summary report tests:

```python
    def test_project_summary_includes_report_history_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = self._create_report_fixture(root)
            self._write_ready_closeout_manifest(project)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "report",
                    "project-summary",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report_text = (
                project / "07_exports" / "reports" / "project_summary.md"
            ).read_text(encoding="utf-8")
            self.assertIn("## Report History Snapshot", report_text)
            self.assertLess(
                report_text.index("## Trend Summary"),
                report_text.index("## Report History Snapshot"),
            )
            self.assertIn("- Report history: current", report_text)
            self.assertIn("- Report history snapshots: 1", report_text)
            self.assertIn("- Latest report history: #1 project-summary blocked", report_text)
```

- [x] **Step 3: Run RED tests**

Run:

```powershell
python -m unittest tests.test_status_quality_summary tests.test_reports
```

Expected: the new tests fail because status and project-summary reports do not yet expose report-history audit rows.

### Task 2: Implement Report History Audit Surface

**Files:**
- Modify: `socrates/reports.py`
- Modify: `socrates/cli.py`

- [x] **Step 1: Add a public `ReportHistorySummary` dataclass**

In `socrates/reports.py`, add:

```python
@dataclass(frozen=True)
class ReportHistorySummary:
    status: str
    total_snapshots: int
    latest_snapshot_id: int | None
    latest_report_type: str
    latest_risk_level: str
```

- [x] **Step 2: Add report history summary helpers**

Add public:

```python
def summarize_report_history(project_path: Path | str) -> ReportHistorySummary:
```

Use the existing risk history reader. Return:

- `status="not_run"` when no history file exists.
- `status="invalid"` when the history file exists but has invalid JSON, wrong schema, or malformed snapshots.
- `status="current"` when valid snapshots exist.

Add private `_report_history_summary_from_snapshots(...)` and `_report_history_lines(...)` helpers so project-summary can preview the current snapshot before writing it.

- [x] **Step 3: Render project-summary report history snapshot**

In `generate_project_summary`, compute the current snapshot id and report-history lines using existing snapshots plus the current project-summary snapshot. Pass `report_history` to `_project_summary_text`, and render:

```text
## Report History Snapshot
```

after `## Trend Summary`.

- [x] **Step 4: Print report history in status**

In `socrates/cli.py`, import `summarize_report_history`, then print:

```text
Report history: <status>
Report history snapshots: <count>
Latest report history: #<id> <report_type> <risk_level>
```

For `not_run` or `invalid`, render `Report history snapshots: 0` and `Latest report history: none`.

- [x] **Step 5: Run GREEN tests**

Run:

```powershell
python -m unittest tests.test_status_quality_summary tests.test_reports
```

Expected: all selected tests pass.

### Task 3: Update Docs, Verify, Commit, and Capture Wiki

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/development_roadmap.md`
- Modify: `docs/development_log.md`
- Modify after commit: `D:\llmwiki\wiki\projects\socrates.md`
- Modify after commit: `D:\llmwiki\wiki\index.md`
- Modify after commit: `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.20**

Describe report-history audit as deterministic visibility over the v0.19 trend artifact. State that it is not a new readiness gate, score, prediction, planner, tutor, or learning-state mutation.

- [x] **Step 2: Run verification**

Run:

```powershell
python -m unittest tests.test_status_quality_summary tests.test_reports
python -m unittest discover -s tests
python -m compileall socrates
git diff --check
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
bash scripts/check.sh
```

- [x] **Step 3: Commit with Lore protocol**

Commit the v0.20 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.20 commit id, verification evidence, and the boundary that report-history audit rows expose existing trend artifacts without becoming readiness gates or learner-state truth.
