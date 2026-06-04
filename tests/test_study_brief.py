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
