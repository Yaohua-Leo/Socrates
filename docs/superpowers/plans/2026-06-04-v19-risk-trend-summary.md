# v0.19 Risk Trend Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic report trend summaries by persisting bounded risk snapshots and comparing each report run with the previous snapshot of the same report type.

**Architecture:** Keep trend evidence project-local under `07_exports/reports/risk_history.json`. Report generation will compute current risk metrics, render current `Risk Summary`, render `Trend Summary` from the previous same-type snapshot, then append the current snapshot after the report is written. This is historical comparison over generated report snapshots, not prediction, scoring, grading, or learning-state mutation.

**Tech Stack:** Python stdlib, existing report/queue/state helpers, `unittest`, no new dependencies.

---

### Task 1: Add Failing Trend Summary Report Tests

**Files:**
- Modify: `tests/test_reports.py`

- [x] **Step 1: Add a weekly trend comparison test**

Add this test near the risk summary report tests:

```python
    def test_weekly_report_trend_summary_compares_previous_snapshot(self) -> None:
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
            report_text = (
                project / "07_exports" / "reports" / "weekly_report.md"
            ).read_text(encoding="utf-8")
            self.assertIn("## Trend Summary", report_text)
            self.assertLess(
                report_text.index("## Risk Summary"),
                report_text.index("## Trend Summary"),
            )
            self.assertIn("- Previous snapshot: 1", report_text)
            self.assertIn("- Risk level change: clear -> attention", report_text)
            self.assertIn("- Weak concepts change: +1", report_text)

            history = json.loads(
                (project / "07_exports" / "reports" / "risk_history.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(history["schema_version"], "v0.19")
            self.assertEqual([item["snapshot_id"] for item in history["snapshots"]], [1, 2])
            self.assertEqual(history["snapshots"][0]["report_type"], "weekly")
            self.assertEqual(history["snapshots"][1]["weak_concepts"], 1)
```

- [x] **Step 2: Add a project summary baseline trend test**

Add this test below the weekly trend comparison test:

```python
    def test_project_summary_trend_summary_uses_empty_baseline(self) -> None:
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
            self.assertIn("## Trend Summary", report_text)
            self.assertIn("- Previous snapshot: none", report_text)
            self.assertIn("- Risk level change: baseline", report_text)

            history = json.loads(
                (project / "07_exports" / "reports" / "risk_history.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(history["snapshots"][0]["report_type"], "project-summary")
            self.assertEqual(history["snapshots"][0]["risk_level"], "blocked")
```

- [x] **Step 3: Run RED report tests**

Run:

```powershell
python -m unittest tests.test_reports
```

Expected: the new tests fail because reports do not yet render `## Trend Summary` or write `risk_history.json`.

### Task 2: Implement Risk History and Trend Rendering

**Files:**
- Modify: `socrates/reports.py`

- [x] **Step 1: Add a risk metrics dataclass and history constants**

Add a frozen `RiskMetrics` dataclass with fields `risk_level`, `blocker_pressure`, `review_pressure`, `human_review_backlog`, `weak_concepts`, and `active_misconceptions`. Add `_RISK_HISTORY_FILE = "risk_history.json"` and `_RISK_HISTORY_SCHEMA_VERSION = "v0.19"` near the report constants.

- [x] **Step 2: Split risk metric computation from rendering**

Replace direct `_risk_summary_lines(queue=queue, state=state)` calls with:

```python
risk_metrics = _risk_metrics(queue=queue, state=state)
risk_summary = _risk_summary_lines(risk_metrics)
```

Keep the row labels from v0.18 unchanged.

- [x] **Step 3: Add risk history helpers**

Add helpers:

```python
def _risk_history_path(project_root: Path) -> Path:
    return project_root / "07_exports" / "reports" / _RISK_HISTORY_FILE


def _read_risk_history(project_root: Path) -> list[dict[str, object]]:
    ...


def _latest_risk_snapshot(
    project_root: Path,
    *,
    report_type: str,
) -> dict[str, object] | None:
    ...


def _append_risk_history_snapshot(
    project_root: Path,
    *,
    report_type: str,
    metrics: RiskMetrics,
) -> None:
    ...
```

`_read_risk_history` should return `[]` for missing, invalid JSON, wrong schema, or malformed `snapshots`. `_append_risk_history_snapshot` should assign `snapshot_id` as the previous maximum integer id plus 1, append the current metrics, keep only the latest 50 snapshots, and write JSON with `indent=2` plus trailing newline.

- [x] **Step 4: Add trend summary rendering**

Add:

```python
def _trend_summary_lines(
    *,
    previous: dict[str, object] | None,
    current: RiskMetrics,
) -> list[str]:
```

For no previous snapshot, return:

```text
- Previous snapshot: none
- Risk level change: baseline
- Blocker pressure change: baseline
- Review pressure change: baseline
- Human review backlog change: baseline
- Weak concepts change: baseline
- Active misconceptions change: baseline
```

For a previous snapshot, render `Previous snapshot: <snapshot_id>`, `Risk level change: <old> -> <new>`, and signed integer deltas such as `+1`, `0`, or `-2` for the five numeric metrics.

- [x] **Step 5: Wire weekly, monthly, and project-summary generators**

In each generator, compute:

```python
risk_metrics = _risk_metrics(queue=queue, state=state)
risk_summary = _risk_summary_lines(risk_metrics)
trend_summary = _trend_summary_lines(
    previous=_latest_risk_snapshot(context.root, report_type="<report-type>"),
    current=risk_metrics,
)
```

Pass `trend_summary` into the text helper, write the report, then call `_append_risk_history_snapshot(...)` before appending the project log.

- [x] **Step 6: Render trend summary after risk summary**

Add `trend_summary: list[str]` parameters to `_weekly_report_text`, `_monthly_report_text`, and `_project_summary_text`. Insert:

```text
## Trend Summary
```

after the `## Risk Summary` rows in all three reports.

- [x] **Step 7: Run GREEN report tests**

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

- [x] **Step 1: Document v0.19**

Describe trend summary as deterministic historical comparison over bounded report risk snapshots. State that it is not prediction, scoring, grading, tutoring, planning, readiness gating, or learning-state mutation.

- [x] **Step 2: Run verification**

Run:

```powershell
python -m unittest tests.test_reports
python -m unittest discover -s tests
python -m compileall socrates
git diff --check
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
bash scripts/check.sh
```

- [x] **Step 3: Commit with Lore protocol**

Commit the v0.19 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.19 commit id, verification evidence, the new `risk_history.json` artifact, and the boundary that trend summaries compare bounded report snapshots rather than predicting learning outcomes.
