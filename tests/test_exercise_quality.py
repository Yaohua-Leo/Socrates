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
    def test_exercise_approve_cli_marks_draft_as_approved(self) -> None:
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
                    "approve",
                    "--project",
                    str(project),
                    "--exercise",
                    "normal_subgroup_01",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Approved exercise normal_subgroup_01", result.stdout)
            approved = project / "05_exercises" / "generated" / "normal_subgroup_01.md"
            approved_text = approved.read_text(encoding="utf-8")
            self.assertIn('status: "approved"', approved_text)
            self.assertIn('review_status: "approved"', approved_text)
            self.assertIn("reviewed_by_user: true", approved_text)

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Approved exercises: 1", status.stdout)

    def test_approve_exercise_draft_rejects_failed_quality_gate(self) -> None:
        from socrates.exercises import approve_exercise_draft

        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            malformed = project / "05_exercises" / "generated" / "bad_exercise.md"
            malformed.write_text(
                "---\n"
                "status: draft\n"
                "review_status: needs_review\n"
                "type: generated_exercise\n"
                "concept: Bad Exercise\n"
                "---\n\n"
                "# Bad Exercise\n\n"
                "This exercise is missing required sections.\n",
                encoding="utf-8",
                newline="\n",
            )

            with self.assertRaisesRegex(ValueError, "failed quality gate"):
                approve_exercise_draft(project, "bad_exercise")

            text = malformed.read_text(encoding="utf-8")
            self.assertIn("status: draft", text)
            self.assertNotIn('status: "approved"', text)
            report = project / "08_evals" / "exercise_quality_eval.md"
            self.assertIn("bad_exercise.md: fail", report.read_text(encoding="utf-8"))

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
