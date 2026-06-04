from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
