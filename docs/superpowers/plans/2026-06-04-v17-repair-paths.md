# v0.17 Repair Paths Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic blocker repair-path summaries so queue output and learning reports show which repair commands unblock the project.

**Architecture:** Reuse existing `LearningQueue` blocker buckets: workflow actions, artifact quality checks, and tool verification fixes. Add a render-only `Repair Paths` section that prefixes blocker items by source section, excludes study/review work, and is reused by reports.

**Tech Stack:** Python stdlib, existing queue/report helpers, `unittest`, no new dependencies.

---

### Task 1: Add Failing Queue Repair-Path Tests

**Files:**
- Modify: `tests/test_learning_queue.py`

- [x] **Step 1: Add a default queue repair-path test**

Add this test near the action summary tests:

```python
    def test_queue_cli_includes_repair_paths_for_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = _create_ready_closeout_fixture(Path(temp_dir))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "queue",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("## Repair Paths", result.stdout)
            self.assertLess(
                result.stdout.index("## Action Summary"),
                result.stdout.index("## Repair Paths"),
            )
            self.assertLess(
                result.stdout.index("## Repair Paths"),
                result.stdout.index("## Priority Actions"),
            )
            self.assertIn(
                (
                    "- workflow:multi_session_regression | "
                    "08_evals/session_closeout_manifest.json | "
                    "status: not_run; run with: socrates lifecycle regression --project <project>"
                ),
                result.stdout,
            )
            self.assertNotIn(
                "- notes:normal_subgroup | 04_atomic_notes/drafts/normal_subgroup.md",
                result.stdout.split("## Priority Actions", 1)[0],
            )
```

- [x] **Step 2: Add a selectable empty repair-path section test**

Add this test below the default repair-path test:

```python
    def test_queue_cli_repair_paths_section_is_empty_without_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "queue",
                    "--project",
                    str(project),
                    "--section",
                    "repairs",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("## Repair Paths", result.stdout)
            self.assertIn("- none", result.stdout)
            self.assertNotIn("## Priority Actions", result.stdout)
            self.assertNotIn("## Action Summary", result.stdout)
```

- [x] **Step 3: Run RED queue tests**

Run:

```powershell
python -m unittest tests.test_learning_queue
```

Expected: the new tests fail because `--section repairs` is unknown and full queue output does not yet include `## Repair Paths`.

### Task 2: Implement Queue Repair Paths

**Files:**
- Modify: `socrates/learning_queue.py`

- [x] **Step 1: Add `repairs` to queue sections**

Add `"repairs"` to `QUEUE_SECTIONS` so `socrates queue --section repairs` is accepted.

- [x] **Step 2: Add public `repair_path_items` helper**

Add:

```python
def repair_path_items(queue: LearningQueue) -> list[QueueItem]:
    """Return blocker queue items in deterministic repair order."""

    return _prefixed_queue_items(
        (
            ("workflow", queue.workflow_actions),
            ("quality-checks", queue.quality_checks_to_fix),
            ("tool-verifications", queue.tool_verifications_to_fix),
        )
    )
```

Extract the prefixing loop from `_priority_actions` into:

```python
def _prefixed_queue_items(
    ordered_sections: tuple[tuple[str, list[QueueItem]], ...],
) -> list[QueueItem]:
```

Use the helper from both `_priority_actions` and `repair_path_items`.

- [x] **Step 3: Render repair paths in queue CLI output**

In `format_learning_queue`, after `Action Summary` and before regular sections, add:

```python
    if section in {"all", "repairs"}:
        lines.extend(_section("Repair Paths", repair_path_items(queue)))
        if section == "repairs":
            return "\n".join(lines).rstrip() + "\n"
```

Keep `repairs` out of `_queue_sections` because it is a derived view, not a raw queue bucket.

- [x] **Step 4: Run GREEN queue tests**

Run:

```powershell
python -m unittest tests.test_learning_queue
```

Expected: all queue tests pass.

### Task 3: Add Repair Paths to Reports

**Files:**
- Modify: `tests/test_reports.py`
- Modify: `socrates/reports.py`

- [x] **Step 1: Add failing report tests**

Add these tests near the action summary report tests:

```python
    def test_project_summary_includes_repair_paths(self) -> None:
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
            self.assertIn("## Repair Paths", report_text)
            self.assertLess(
                report_text.index("## Action Summary"),
                report_text.index("## Repair Paths"),
            )
            self.assertIn(
                (
                    "- workflow:multi_session_regression | "
                    "08_evals/session_closeout_manifest.json | "
                    "status: not_run; run with: socrates lifecycle regression --project <project>"
                ),
                report_text,
            )
            self.assertNotIn(
                "- reviews:quotient_group | 02_learning_plan/review_schedule.md",
                report_text.split("## Repair Paths", 1)[1].split("## Benchmark Snapshot", 1)[0],
            )

    def test_weekly_report_repair_paths_uses_empty_fallback(self) -> None:
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
            self.assertIn("## Repair Paths", report_text)
            self.assertIn("## Action Summary", report_text)
            self.assertLess(
                report_text.index("## Action Summary"),
                report_text.index("## Repair Paths"),
            )
            self.assertIn("- none", report_text.split("## Repair Paths", 1)[1])
```

Run:

```powershell
python -m unittest tests.test_reports
```

Expected: the new report tests fail because reports do not yet render `## Repair Paths`.

- [x] **Step 2: Import and pass repair path items**

In `socrates/reports.py`, import `repair_path_items` from `socrates.learning_queue`.

In `generate_weekly_report`, `generate_monthly_report`, and `generate_project_summary`, compute:

```python
repair_paths = repair_path_items(queue)
```

Pass `repair_paths=repair_paths` into each report text helper.

- [x] **Step 3: Render repair paths after action summary**

Add `repair_paths: list[QueueItem]` parameters to all three report text helpers and insert:

```text
## Repair Paths
```

after `## Action Summary` in weekly, monthly, and project summary reports. Reuse `_priority_action_lines(repair_paths)` for compact rendering.

- [x] **Step 4: Run GREEN report tests**

Run:

```powershell
python -m unittest tests.test_reports
```

Expected: all report tests pass.

### Task 4: Update Docs, Verify, Commit, and Capture Wiki

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/development_roadmap.md`
- Modify: `docs/development_log.md`
- Modify after commit: `D:\llmwiki\wiki\projects\socrates.md`
- Modify after commit: `D:\llmwiki\wiki\index.md`
- Modify after commit: `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.17**

Describe repair paths as deterministic blocker-only queue/report UX over workflow, quality-check, and tool-verification queue buckets. State that it is not a fixer, command runner, readiness gate, score, planner, or learning-state mutation.

- [x] **Step 2: Run verification**

Run:

```powershell
python -m unittest tests.test_learning_queue tests.test_reports
python -m unittest discover -s tests
python -m compileall socrates
git diff --check
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
bash scripts/check.sh
```

- [x] **Step 3: Commit with Lore protocol**

Commit the v0.17 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.17 commit id, verification evidence, and the boundary that repair paths are render-only blocker summaries over existing queue evidence.
