# v0.18 Risk Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic report risk summaries so weekly, monthly, and project-summary reports show whether risk is accumulating in blockers, reviews, human-review backlog, weak concepts, or active misconceptions.

**Architecture:** Keep this as a current-state report snapshot, not historical analytics. Reports will derive risk rows from existing `LearningQueue` buckets and persisted learning-state evidence, then render one shared `Risk Summary` section after `Repair Paths`.

**Tech Stack:** Python stdlib, existing report/queue/state helpers, `unittest`, no new dependencies.

---

### Task 1: Add Failing Risk Summary Report Tests

**Files:**
- Modify: `tests/test_reports.py`

- [x] **Step 1: Add a project summary risk test**

Add this test near the repair path report tests:

```python
    def test_project_summary_includes_risk_summary(self) -> None:
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
            self.assertIn("## Risk Summary", report_text)
            self.assertLess(
                report_text.index("## Repair Paths"),
                report_text.index("## Risk Summary"),
            )
            self.assertIn("- Risk level: blocked", report_text)
            self.assertIn("- Blocker pressure: 1", report_text)
            self.assertIn("- Review pressure: 1", report_text)
            self.assertIn("- Human review backlog: 4", report_text)
            self.assertIn("- Weak concepts: 1", report_text)
            self.assertIn("- Active misconceptions: 0", report_text)
```

- [x] **Step 2: Add an empty weekly risk fallback test**

Add this test below the project summary risk test:

```python
    def test_weekly_report_risk_summary_uses_empty_fallbacks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))

            result = subprocess.run(
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

            self.assertEqual(result.returncode, 0, result.stderr)
            report_text = (
                project / "07_exports" / "reports" / "weekly_report.md"
            ).read_text(encoding="utf-8")
            self.assertIn("## Risk Summary", report_text)
            self.assertIn("- Risk level: clear", report_text)
            self.assertIn("- Blocker pressure: 0", report_text)
            self.assertIn("- Review pressure: 0", report_text)
            self.assertIn("- Human review backlog: 0", report_text)
            self.assertIn("- Weak concepts: 0", report_text)
            self.assertIn("- Active misconceptions: 0", report_text)
```

- [x] **Step 3: Run RED report tests**

Run:

```powershell
python -m unittest tests.test_reports
```

Expected: the new tests fail because reports do not yet render `## Risk Summary`.

### Task 2: Implement Risk Summary Rendering

**Files:**
- Modify: `socrates/reports.py`

- [x] **Step 1: Import `LearningQueue`**

In `socrates/reports.py`, import `LearningQueue` from `socrates.learning_queue` for the risk helper annotation.

- [x] **Step 2: Add `_risk_summary_lines` helper**

Add:

```python
def _risk_summary_lines(
    *,
    queue: LearningQueue,
    state: dict[str, object],
) -> list[str]:
```

It should render:

```text
- Risk level: clear|attention|blocked
- Blocker pressure: <workflow + quality + tool fix count>
- Review pressure: <scheduled review count>
- Human review backlog: <exports + notes + misconception notes + exercise drafts + attempts>
- Weak concepts: <concept_mastery scores below 0.7>
- Active misconceptions: <active misconception records>
```

Use `coerce_learning_score` and `coerce_occurrence_count` where learning-state values are malformed or non-numeric. Risk level is `blocked` when blocker pressure is nonzero, `attention` when any other risk count is nonzero, and `clear` when all risk counts are zero.

- [x] **Step 3: Pass risk summary lines to report text helpers**

In `generate_weekly_report`, `generate_monthly_report`, and `generate_project_summary`, compute:

```python
risk_summary = _risk_summary_lines(queue=queue, state=state)
```

Pass `risk_summary=risk_summary` into each corresponding report text helper.

- [x] **Step 4: Render risk summary after repair paths**

Add `risk_summary: list[str]` parameters to all three report text helpers and insert:

```text
## Risk Summary
```

after `## Repair Paths` in weekly, monthly, and project summary reports.

- [x] **Step 5: Run GREEN report tests**

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

- [x] **Step 1: Document v0.18**

Describe risk summary as a deterministic current-state report snapshot over existing queue/state evidence. State that it is not historical analytics, prediction, scoring, grading, tutoring, planning, or learning-state mutation.

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

Commit the v0.18 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.18 commit id, verification evidence, and the boundary that risk summaries are current-state deterministic report snapshots over existing queue/state evidence.
