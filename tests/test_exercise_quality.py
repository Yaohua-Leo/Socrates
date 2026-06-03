from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from socrates.artifacts import generate_exercise_drafts
from socrates.project import ProjectSpec, create_project


REPO_ROOT = Path(__file__).resolve().parents[1]


class ExerciseQualityTests(unittest.TestCase):
    def test_exercise_check_cli_writes_quality_report_for_generated_exercises(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="df-1",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "exercise",
                    "check",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Checked 5 exercise drafts: 5 passed, 0 failed", result.stdout)
            report = project / "08_evals" / "exercise_quality_eval.md"
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("# Exercise Quality Eval", report_text)
            self.assertIn("## Summary", report_text)
            self.assertIn("- Drafts checked: 5", report_text)
            self.assertIn("- Passed: 5", report_text)
            self.assertIn("- Failed: 0", report_text)
            self.assertIn("normal_subgroup_01.md: pass", report_text)


if __name__ == "__main__":
    unittest.main()
