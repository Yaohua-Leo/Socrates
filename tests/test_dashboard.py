from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from socrates.project import ProjectSpec, create_project


REPO_ROOT = Path(__file__).resolve().parents[1]


class DashboardTests(unittest.TestCase):
    def test_dashboard_cli_summarizes_empty_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))

            result = subprocess.run(
                [sys.executable, "-m", "socrates", "dashboard", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("# Study Dashboard", result.stdout)
            self.assertIn("- Project: Group Theory", result.stdout)
            self.assertIn("- Workflow actions: 0", result.stdout)
            self.assertIn("- Session closeout: not_run", result.stdout)
            self.assertIn("- Multi-session regression: not_run", result.stdout)
            self.assertIn("- Report history: not_run", result.stdout)
            self.assertIn("## Action Summary", result.stdout)
            self.assertIn("- Completion: clear", result.stdout)
            self.assertIn("## Top Priority Actions", result.stdout)
            self.assertIn("- none", result.stdout)
            self.assertIn("## Report Health", result.stdout)
            self.assertIn(
                "- weekly | missing | Weekly Learning Report | 07_exports/reports/weekly_report.md",
                result.stdout,
            )
            self.assertIn("## Boundary", result.stdout)

    def test_dashboard_cli_json_summarizes_empty_project_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            project_files_before = _project_file_snapshot(project)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "dashboard",
                    "--project",
                    str(project),
                    "--json",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("# Study Dashboard", result.stdout)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["quality_boundary"], "deterministic_study_dashboard")
            self.assertEqual(payload["project"], "Group Theory")
            self.assertEqual(payload["root"], str(project))
            self.assertEqual(
                payload["snapshot"],
                {
                    "workflow_actions": 0,
                    "session_closeout": "not_run",
                    "multi_session_regression": "not_run",
                    "report_history": "not_run",
                    "report_history_snapshots": 0,
                    "study_brief": "not_run",
                    "study_brief_recorded_next_action": "none",
                    "study_brief_current_next_action": "none",
                    "reports_generated": 0,
                    "reports_stale": 0,
                    "reports_missing": 3,
                },
            )
            self.assertEqual(
                payload["action_summary"],
                {
                    "completion": "clear",
                    "open_actions": 0,
                    "blockers": 0,
                    "can_continue_learning": 0,
                    "needs_human_review": 0,
                    "next_action": "none",
                },
            )
            self.assertEqual(payload["top_priority_actions"], [])
            self.assertEqual(
                payload["report_health"],
                [
                    {
                        "report_id": "weekly",
                        "status": "missing",
                        "title": "Weekly Learning Report",
                        "path": "07_exports/reports/weekly_report.md",
                    },
                    {
                        "report_id": "monthly",
                        "status": "missing",
                        "title": "Monthly Learning Report",
                        "path": "07_exports/reports/monthly_report.md",
                    },
                    {
                        "report_id": "project-summary",
                        "status": "missing",
                        "title": "Project Summary",
                        "path": "07_exports/reports/project_summary.md",
                    },
                ],
            )
            self.assertEqual(
                _project_file_snapshot(project),
                project_files_before,
            )

    def test_dashboard_cli_surfaces_first_priority_action(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            draft = project / "04_atomic_notes" / "drafts" / "normal_subgroup.md"
            draft.write_text("# Normal Subgroup\n\nDraft note.\n", encoding="utf-8", newline="\n")

            result = subprocess.run(
                [sys.executable, "-m", "socrates", "dashboard", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("- Completion: in_progress", result.stdout)
            self.assertIn("- Open actions: 1", result.stdout)
            self.assertIn("- Needs human review: 1", result.stdout)
            self.assertIn(
                "- Next action: notes:normal_subgroup | "
                "04_atomic_notes/drafts/normal_subgroup.md",
                result.stdout,
            )
            self.assertIn(
                "- notes:normal_subgroup | 04_atomic_notes/drafts/normal_subgroup.md",
                result.stdout,
            )

    def test_dashboard_cli_json_surfaces_first_priority_action(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            draft = project / "04_atomic_notes" / "drafts" / "normal_subgroup.md"
            draft.write_text("# Normal Subgroup\n\nDraft note.\n", encoding="utf-8", newline="\n")
            project_files_before = _project_file_snapshot(project)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "dashboard",
                    "--project",
                    str(project),
                    "--json",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["action_summary"]["completion"], "in_progress")
            self.assertEqual(payload["action_summary"]["open_actions"], 1)
            self.assertEqual(payload["action_summary"]["needs_human_review"], 1)
            self.assertEqual(
                payload["action_summary"]["next_action"],
                "notes:normal_subgroup | 04_atomic_notes/drafts/normal_subgroup.md",
            )
            self.assertEqual(
                payload["top_priority_actions"],
                [
                    {
                        "item_id": "notes:normal_subgroup",
                        "path": "04_atomic_notes/drafts/normal_subgroup.md",
                        "detail": "",
                    }
                ],
            )
            self.assertEqual(
                _project_file_snapshot(project),
                project_files_before,
            )


def _project_file_snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


if __name__ == "__main__":
    unittest.main()
