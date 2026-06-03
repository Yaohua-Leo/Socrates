from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from socrates.project import ProjectSpec, create_project
from socrates.tutoring import run_scripted_tutoring_session


class TutoringSessionTests(unittest.TestCase):
    def test_scripted_session_writes_expected_session_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(
                ProjectSpec(
                    topic="Linear Algebra",
                    path=Path(temp_dir) / "linear_algebra",
                    goal="Understand eigenvectors.",
                )
            )
            script = Path(temp_dir) / "session_script.md"
            script.write_text(
                "\n".join(
                    [
                        "topic: eigenvectors",
                        "goal: Explain what an eigenvector is.",
                        "question: What does Av = lambda v mean geometrically?",
                        "hint: Compare Av with the direction of v.",
                        "hint: Ask whether Av points along the same line as v.",
                        "attempt: It means Av stays on the span of v.",
                        "misconception: Eigenvectors must have eigenvalue 1.",
                        "next: Try one 2x2 diagonal matrix example.",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            result = run_scripted_tutoring_session(project, script, session_id="session_001")

            session_dir = project / "03_sessions" / "session_001"
            self.assertEqual(result.session_dir, session_dir)
            for file_name in [
                "transcript.md",
                "tutor_notes.md",
                "detected_misconceptions.md",
                "summary.md",
                "next_actions.md",
            ]:
                self.assertTrue((session_dir / file_name).exists(), file_name)

            transcript = (session_dir / "transcript.md").read_text(encoding="utf-8")
            self.assertIn("# Tutoring Session: session_001", transcript)
            self.assertIn("## Topic\n\nEigenvectors", transcript)
            self.assertIn("Tutor: What does Av = lambda v mean geometrically?", transcript)
            self.assertIn("Hint 1: Compare Av with the direction of v.", transcript)
            self.assertIn("Student attempt: It means Av stays on the span of v.", transcript)

            notes = (session_dir / "tutor_notes.md").read_text(encoding="utf-8")
            self.assertIn("Goal: Explain what an eigenvector is.", notes)
            misconceptions = (session_dir / "detected_misconceptions.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("- Eigenvectors must have eigenvalue 1.", misconceptions)
            next_actions = (session_dir / "next_actions.md").read_text(encoding="utf-8")
            self.assertIn("- Try one 2x2 diagonal matrix example.", next_actions)

    def test_hint_ladder_does_not_reveal_solution_before_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            script = Path(temp_dir) / "script.md"
            script.write_text(
                "\n".join(
                    [
                        "topic: kernels",
                        "question: Why is the kernel a normal subgroup?",
                        "hint: Start from f(gkg^-1).",
                        "solution: f(gkg^-1)=f(g)ef(g)^-1=e, so gkg^-1 is in the kernel.",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            run_scripted_tutoring_session(project, script, session_id="session_002")

            transcript = (
                project / "03_sessions" / "session_002" / "transcript.md"
            ).read_text(encoding="utf-8")
            self.assertIn("Hint 1: Start from f(gkg^-1).", transcript)
            self.assertNotIn("f(g)ef(g)^-1=e", transcript)
            summary = (project / "03_sessions" / "session_002" / "summary.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("No student attempt recorded.", summary)


if __name__ == "__main__":
    unittest.main()
