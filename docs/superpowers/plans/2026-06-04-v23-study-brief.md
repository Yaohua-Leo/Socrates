# v0.23 Study Brief Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic `socrates brief --project <project>` command that writes a compact study-start Markdown brief from existing dashboard and queue evidence.

**Architecture:** Keep dashboard rendering as the read-only evidence source and add a small `socrates.study_brief` writer that creates one export artifact plus a project-log entry. The brief must not run repairs, refresh reports, call LLMs, approve artifacts, score learning, tutor, predict, or mutate learning-state truth.

**Tech Stack:** Python stdlib, existing Socrates CLI, `unittest`, deterministic filesystem fixtures.

---

## File Map

- Create `socrates/study_brief.py`: format and write the study brief artifact.
- Modify `socrates/dashboard.py`: expose the existing project-title helper for reuse.
- Modify `socrates/cli.py`: add the top-level `brief` command.
- Create `tests/test_study_brief.py`: CLI-level tests for non-empty and clear projects.
- Modify docs after GREEN: `README.md`, `docs/README.md`, `docs/development_log.md`, `docs/development_roadmap.md`.

## Acceptance Criteria

- `python -m socrates brief --project <project>` writes `07_exports/briefs/study_brief.md`.
- The brief starts with `# Study Brief` and has `## Start Here`, `## Dashboard Evidence`, and `## Boundary`.
- The brief surfaces the first priority action as the same item id/path shown by the queue and dashboard.
- Empty projects show `Next action: none` and do not invent commands.
- The brief embeds demoted dashboard evidence so the artifact contains snapshot, action summary, top priority actions, and report health.
- The boundary states the command only writes the brief artifact and project log entry; it does not run repairs, reports, LLM calls, approvals, scoring, tutoring, prediction, or learning-state truth mutation.

---

### Task 1: RED Study Brief CLI Tests

**Files:**
- Create: `tests/test_study_brief.py`

- [x] **Step 1: Add failing tests**

Create `tests/test_study_brief.py` with two CLI tests:

```python
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from socrates.project import ProjectSpec, create_project


REPO_ROOT = Path(__file__).resolve().parents[1]


class StudyBriefTests(unittest.TestCase):
    def test_brief_cli_writes_startup_brief_from_dashboard_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            draft = project / "04_atomic_notes" / "drafts" / "normal_subgroup.md"
            draft.write_text("# Normal Subgroup\n\nDraft note.\n", encoding="utf-8", newline="\n")

            result = subprocess.run(
                [sys.executable, "-m", "socrates", "brief", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Wrote study brief:", result.stdout)
            brief = project / "07_exports" / "briefs" / "study_brief.md"
            self.assertTrue(brief.exists())
            text = brief.read_text(encoding="utf-8")
            self.assertIn("# Study Brief", text)
            self.assertIn("## Start Here", text)
            self.assertIn("- Project: Group Theory", text)
            self.assertIn(
                "- Next action: notes:normal_subgroup | "
                "04_atomic_notes/drafts/normal_subgroup.md",
                text,
            )
            self.assertIn("- Action type: human_review", text)
            self.assertIn("## Dashboard Evidence", text)
            self.assertIn("## Study Dashboard", text)
            self.assertIn("### Action Summary", text)
            self.assertIn("### Top Priority Actions", text)
            self.assertIn("### Report Health", text)
            self.assertIn("## Boundary", text)
            self.assertIn("does not run repairs", text)
            project_log = project / "00_meta" / "project_log.md"
            self.assertIn("Generated study brief.", project_log.read_text(encoding="utf-8"))

    def test_brief_cli_handles_clear_project_without_fake_action(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))

            result = subprocess.run(
                [sys.executable, "-m", "socrates", "brief", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            brief = project / "07_exports" / "briefs" / "study_brief.md"
            text = brief.read_text(encoding="utf-8")
            self.assertIn("- Next action: none", text)
            self.assertIn("- Action type: none", text)
            self.assertIn("### Top Priority Actions", text)
            self.assertIn("- none", text)


if __name__ == "__main__":
    unittest.main()
```

- [x] **Step 2: Run RED**

Run:

```powershell
python -m unittest tests.test_study_brief
```

Expected: fail because `brief` is not a known command yet.

---

### Task 2: Implement Study Brief Writer and CLI

**Files:**
- Create: `socrates/study_brief.py`
- Modify: `socrates/dashboard.py`
- Modify: `socrates/cli.py`

- [x] **Step 1: Expose dashboard project-title helper**

Rename the private dashboard helper to `project_title(...)` and use it inside `format_study_dashboard`.

- [x] **Step 2: Add study brief formatter and writer**

Create `socrates/study_brief.py` with `format_study_brief(project_path)` and `generate_study_brief(project_path)`. Reuse `format_study_dashboard`, `collect_learning_queue`, and `priority_queue_items`.

- [x] **Step 3: Wire CLI**

Add top-level `brief --project <project>` parser and `_handle_brief`, printing `Wrote study brief: <path>`.

- [x] **Step 4: Run GREEN**

Run:

```powershell
python -m unittest tests.test_study_brief
```

Expected: 2 tests OK.

---

### Task 3: Docs, Verification, Commit, and Wiki

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/development_log.md`
- Modify: `docs/development_roadmap.md`
- Modify: `docs/superpowers/plans/2026-06-04-v23-study-brief.md`
- Update llmwiki after the repo commit: `D:\llmwiki\wiki\projects\socrates.md`, `D:\llmwiki\wiki\index.md`, `D:\llmwiki\wiki\log.md`

- [x] **Step 1: Document v0.23**

Document the new command, artifact path, and boundary in README, docs index, development log, and roadmap.

- [x] **Step 2: Run verification**

Run:

```powershell
python -m unittest tests.test_study_brief tests.test_dashboard tests.test_learning_queue tests.test_reports
python -m unittest discover -s tests
python -m compileall socrates
git diff --check
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
bash scripts/check.sh
```

- [x] **Step 3: Commit with Lore protocol**

Commit the v0.23 repo changes with a why-first Lore message and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

- [x] **Step 4: Update llmwiki**

Update the Socrates wiki page, wiki index, and wiki log with the v0.23 commit id, verification evidence, study brief artifact path, and boundary.
