# v0.16 Action Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic completion/blocker summaries to the queue and learning reports so long-running projects show whether the user is blocked, can keep studying, or needs human review.

**Architecture:** Reuse the existing `LearningQueue` buckets as the source of truth. Add one render-only `Action Summary` view that counts open actions, blockers, learning-continuation work, and human-review work; reports will import the same helper so queue and reports cannot drift.

**Tech Stack:** Python stdlib, existing queue/report helpers, `unittest`, no new dependencies.

---

### Task 1: Add Failing Queue Summary Tests

**Files:**
- Modify: `tests/test_learning_queue.py`

- [x] **Step 1: Add a full queue summary test**

Add this test near the existing priority queue tests:

```python
    def test_queue_cli_includes_action_summary_for_all_sections(self) -> None:
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
            self.assertIn("## Action Summary", result.stdout)
            self.assertLess(
                result.stdout.index("## Action Summary"),
                result.stdout.index("## Priority Actions"),
            )
            self.assertIn("- Completion: blocked", result.stdout)
            self.assertIn("- Open actions: 7", result.stdout)
            self.assertIn("- Blockers: 1", result.stdout)
            self.assertIn("- Can continue learning: 0", result.stdout)
            self.assertIn("- Needs human review: 6", result.stdout)
            self.assertIn(
                (
                    "- Next action: workflow:multi_session_regression | "
                    "08_evals/session_closeout_manifest.json | "
                    "status: not_run; run with: socrates lifecycle regression --project <project>"
                ),
                result.stdout,
            )
```

- [x] **Step 2: Add a selectable summary section test**

Add this test below the full queue summary test:

```python
    def test_queue_cli_action_summary_section_can_be_selected(self) -> None:
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
                    "summary",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("## Action Summary", result.stdout)
            self.assertNotIn("## Priority Actions", result.stdout)
            self.assertIn("- Completion: clear", result.stdout)
            self.assertIn("- Open actions: 0", result.stdout)
            self.assertIn("- Blockers: 0", result.stdout)
            self.assertIn("- Can continue learning: 0", result.stdout)
            self.assertIn("- Needs human review: 0", result.stdout)
            self.assertIn("- Next action: none", result.stdout)
```

- [x] **Step 2b: Add an in-progress summary test**

Add a queue summary test with one draft note and no blockers. It should assert `- Completion: in_progress`, `- Blockers: 0`, `- Needs human review: 1`, and a `notes:normal_subgroup` next action.

- [x] **Step 3: Run RED queue tests**

Run:

```powershell
python -m unittest tests.test_learning_queue
```

Expected: the new tests fail because `--section summary` is unknown and full queue output does not yet include `## Action Summary`.

### Task 2: Implement Queue Action Summary Rendering

**Files:**
- Modify: `socrates/learning_queue.py`

- [x] **Step 1: Add `summary` to queue sections**

Add `"summary"` to `QUEUE_SECTIONS` so `socrates queue --section summary` is accepted.

- [x] **Step 2: Add public `action_summary_lines` helper**

Add:

```python
def action_summary_lines(queue: LearningQueue) -> list[str]:
    blockers = (
        len(queue.workflow_actions)
        + len(queue.quality_checks_to_fix)
        + len(queue.tool_verifications_to_fix)
    )
    can_continue = len(queue.scheduled_reviews) + len(queue.exercises_to_attempt)
    human_review = (
        len(queue.obsidian_exports_to_run)
        + len(queue.notes_to_review)
        + len(queue.misconception_notes_to_draft)
        + len(queue.exercise_drafts_to_approve)
        + len(queue.attempts_to_grade)
    )
    open_actions = blockers + can_continue + human_review
    completion = "clear" if open_actions == 0 else "blocked" if blockers else "in_progress"
    next_actions = priority_queue_items(queue)
    next_action = "none"
    if next_actions:
        next_action = _queue_line(next_actions[0]).removeprefix("- ")
    return [
        f"- Completion: {completion}",
        f"- Open actions: {open_actions}",
        f"- Blockers: {blockers}",
        f"- Can continue learning: {can_continue}",
        f"- Needs human review: {human_review}",
        f"- Next action: {next_action}",
    ]
```

- [x] **Step 3: Render summary in queue CLI output**

In `format_learning_queue`, add the summary section before iterating regular queue sections:

```python
    if section in {"all", "summary"}:
        lines.extend(["## Action Summary", ""])
        lines.extend(action_summary_lines(queue))
        lines.append("")
        if section == "summary":
            return "\n".join(lines).rstrip() + "\n"
```

Keep `_queue_sections` unchanged except that `summary` should not appear there; the summary has custom rows, not `QueueItem` rows.

- [x] **Step 4: Run GREEN queue tests**

Run:

```powershell
python -m unittest tests.test_learning_queue
```

Expected: all queue tests pass.

### Task 3: Add Action Summary to Reports

**Files:**
- Modify: `tests/test_reports.py`
- Modify: `socrates/reports.py`

- [x] **Step 1: Add failing report tests**

Add these tests near the existing priority/focus report tests:

```python
    def test_project_summary_includes_action_summary(self) -> None:
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
            self.assertIn("## Action Summary", report_text)
            self.assertIn("- Completion: blocked", report_text)
            self.assertIn("- Open actions: 6", report_text)
            self.assertIn("- Blockers: 1", report_text)
            self.assertIn("- Can continue learning: 1", report_text)
            self.assertIn("- Needs human review: 4", report_text)
            self.assertLess(
                report_text.index("## Recommended Focus"),
                report_text.index("## Action Summary"),
            )

    def test_weekly_report_action_summary_uses_empty_fallbacks(self) -> None:
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
            self.assertIn("## Action Summary", report_text)
            self.assertIn("- Completion: clear", report_text)
            self.assertIn("- Open actions: 0", report_text)
            self.assertIn("- Blockers: 0", report_text)
            self.assertIn("- Can continue learning: 0", report_text)
            self.assertIn("- Needs human review: 0", report_text)
            self.assertIn("- Next action: none", report_text)
```

Run:

```powershell
python -m unittest tests.test_reports
```

Expected: the new report tests fail because reports do not yet render `## Action Summary`.

- [x] **Step 2: Import and pass action summary lines**

In `socrates/reports.py`, import `action_summary_lines` from `socrates.learning_queue`.

In `generate_weekly_report`, `generate_monthly_report`, and `generate_project_summary`, compute:

```python
action_summary = action_summary_lines(queue)
```

Pass `action_summary=action_summary` into each corresponding `_weekly_report_text`, `_monthly_report_text`, and `_project_summary_text` call.

- [x] **Step 3: Render action summary after recommended focus**

Add `action_summary: list[str]` parameters to all three report text helpers and insert:

```text
## Action Summary
```

after the `## Recommended Focus` section in weekly, monthly, and project summary reports.

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

- [x] **Step 1: Document v0.16**

Describe action summary as deterministic queue/report UX over existing queue buckets. State the boundary explicitly: it is not a new readiness gate, score, planner, tutor, or learning-state mutation.

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

Commit the v0.16 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.16 commit id, verification evidence, and the boundary that action summary rows are render-only summaries of existing queue evidence.
