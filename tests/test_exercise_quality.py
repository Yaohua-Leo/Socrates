from __future__ import annotations

import json
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

    def test_exercise_attempt_cli_records_answer_for_approved_exercise(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "p"))
            answer = root / "answer.md"
            answer.write_text(
                "I would prove normality by checking gng^-1 remains in N.\n",
                encoding="utf-8",
                newline="\n",
            )
            generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="df-1",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )
            from socrates.exercises import approve_exercise_draft

            approve_exercise_draft(project, "normal_subgroup_01")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "exercise",
                    "attempt",
                    "--project",
                    str(project),
                    "--exercise",
                    "normal_subgroup_01",
                    "--answer",
                    str(answer),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Recorded attempt for exercise normal_subgroup_01", result.stdout)
            attempted = project / "05_exercises" / "attempted" / "normal_subgroup_01_attempt_001.md"
            attempt_text = attempted.read_text(encoding="utf-8")
            self.assertIn('exercise_id: "normal_subgroup_01"', attempt_text)
            self.assertIn('status: "attempted"', attempt_text)
            self.assertIn("I would prove normality", attempt_text)

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Attempted exercises: 1", status.stdout)

    def test_record_exercise_attempt_rejects_unapproved_exercise(self) -> None:
        from socrates.exercises import record_exercise_attempt

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "p"))
            answer = root / "answer.md"
            answer.write_text("A first attempt.\n", encoding="utf-8", newline="\n")
            generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="df-1",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )

            with self.assertRaisesRegex(ValueError, "not approved"):
                record_exercise_attempt(project, "normal_subgroup_01", answer)

            attempted = project / "05_exercises" / "attempted" / "normal_subgroup_01_attempt_001.md"
            self.assertFalse(attempted.exists())

    def test_record_exercise_attempt_keeps_multiple_attempts(self) -> None:
        from socrates.exercises import approve_exercise_draft, record_exercise_attempt

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "p"))
            first_answer = root / "first_answer.md"
            second_answer = root / "second_answer.md"
            first_answer.write_text("First attempt.\n", encoding="utf-8", newline="\n")
            second_answer.write_text("Second attempt.\n", encoding="utf-8", newline="\n")
            generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="df-1",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )
            approve_exercise_draft(project, "normal_subgroup_01")

            first = record_exercise_attempt(project, "normal_subgroup_01", first_answer)
            second = record_exercise_attempt(project, "normal_subgroup_01", second_answer)

            self.assertEqual(first.name, "normal_subgroup_01_attempt_001.md")
            self.assertEqual(second.name, "normal_subgroup_01_attempt_002.md")
            self.assertIn("First attempt.", first.read_text(encoding="utf-8"))
            self.assertIn("Second attempt.", second.read_text(encoding="utf-8"))

    def test_exercise_grade_cli_writes_grade_and_updates_learning_state(self) -> None:
        from socrates.exercises import approve_exercise_draft, record_exercise_attempt

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "p"))
            answer = root / "answer.md"
            feedback = root / "feedback.md"
            answer.write_text(
                "I would prove normality by checking gng^-1 remains in N.\n",
                encoding="utf-8",
                newline="\n",
            )
            feedback.write_text(
                "Good use of conjugation invariance; subgroup closure still needs detail.\n",
                encoding="utf-8",
                newline="\n",
            )
            generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="df-1",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )
            approve_exercise_draft(project, "normal_subgroup_01")
            record_exercise_attempt(project, "normal_subgroup_01", answer)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "exercise",
                    "grade",
                    "--project",
                    str(project),
                    "--attempt",
                    "normal_subgroup_01_attempt_001",
                    "--score",
                    "0.8",
                    "--feedback",
                    str(feedback),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Graded attempt normal_subgroup_01_attempt_001", result.stdout)
            graded = project / "05_exercises" / "graded" / "normal_subgroup_01_attempt_001_grade.md"
            grade_text = graded.read_text(encoding="utf-8")
            self.assertIn('attempt_id: "normal_subgroup_01_attempt_001"', grade_text)
            self.assertIn('exercise_id: "normal_subgroup_01"', grade_text)
            self.assertIn("score: 0.8", grade_text)
            self.assertIn("Good use of conjugation invariance", grade_text)

            learning_state = json.loads(
                (project / "00_meta" / "learning_state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(learning_state["concept_mastery"]["normal_subgroup"], 0.8)
            self.assertEqual(learning_state["proof_skills"]["exercise_solving"], 0.8)

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Graded exercises: 1", status.stdout)

    def test_grade_exercise_attempt_rejects_missing_attempt(self) -> None:
        from socrates.exercises import grade_exercise_attempt

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "p"))
            feedback = root / "feedback.md"
            feedback.write_text("No attempt exists.\n", encoding="utf-8", newline="\n")

            with self.assertRaisesRegex(FileNotFoundError, "Attempt does not exist"):
                grade_exercise_attempt(project, "missing_attempt", 0.4, feedback)

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
