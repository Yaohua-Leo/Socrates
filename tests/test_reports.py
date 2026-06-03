from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from socrates.artifacts import generate_atomic_note_draft, generate_exercise_drafts
from socrates.context import load_project
from socrates.exercises import approve_exercise_draft, grade_exercise_attempt, record_exercise_attempt
from socrates.notes import export_reviewed_notes_to_obsidian, review_atomic_note
from socrates.project import ProjectSpec, create_project
from socrates.state import (
    LearningStatePatch,
    MistakeRecord,
    build_review_schedule,
    update_learning_state,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class ReportTests(unittest.TestCase):
    def test_weekly_report_cli_summarizes_learning_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = self._create_report_fixture(root)

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
            self.assertIn("Wrote weekly report", result.stdout)
            report = project / "07_exports" / "reports" / "weekly_report.md"
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("# Weekly Learning Report", report_text)
            self.assertIn("- Sessions completed: 1", report_text)
            self.assertIn("- Reviewed notes: 1", report_text)
            self.assertIn("- Generated exercises: 5", report_text)
            self.assertIn("- Graded exercises: 1", report_text)
            self.assertIn("## Learning State", report_text)
            self.assertIn("- normal_subgroup: 0.8", report_text)
            self.assertIn("## Scheduled Review", report_text)
            self.assertIn("- quotient_group: high, next_session", report_text)

    def test_project_summary_cli_writes_lifecycle_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = self._create_report_fixture(root)

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
            self.assertIn("Wrote project summary", result.stdout)
            report = project / "07_exports" / "reports" / "project_summary.md"
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("# Project Summary", report_text)
            self.assertIn("- Title: Group Theory", report_text)
            self.assertIn("## Artifact Inventory", report_text)
            self.assertIn("- Sessions completed: 1", report_text)
            self.assertIn("- Reviewed notes: 1", report_text)
            self.assertIn("- Obsidian exports: 1", report_text)
            self.assertIn("- Generated exercises: 5", report_text)
            self.assertIn("- Approved exercises: 1", report_text)
            self.assertIn("- Attempted exercises: 1", report_text)
            self.assertIn("- Graded exercises: 1", report_text)
            self.assertIn("## Current Learning State", report_text)
            self.assertIn("- normal_subgroup: 0.8", report_text)
            self.assertIn("## Next Review Items", report_text)
            self.assertIn("- quotient_group: high, next_session", report_text)

    def test_monthly_report_cli_highlights_weaknesses_and_next_steps(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = self._create_report_fixture(root)
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(
                    mistakes=[
                        MistakeRecord(
                            session_id="session_0001",
                            concept="normal_subgroup",
                            misconception_id="normal_equals_central",
                            user_answer="Normal subgroups are central.",
                            analysis="Confuses invariance under conjugation with centrality.",
                            repair_suggestion="Compare N normal with N contained in Z(G).",
                        )
                    ],
                ),
            )
            build_review_schedule(context)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "report",
                    "monthly",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Wrote monthly report", result.stdout)
            report = project / "07_exports" / "reports" / "monthly_report.md"
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("# Monthly Learning Report", report_text)
            self.assertIn("## Concepts Studied", report_text)
            self.assertIn("- normal_subgroup: 0.8", report_text)
            self.assertIn("- quotient_group: 0.42", report_text)
            self.assertIn("## Notes And Exercises", report_text)
            self.assertIn("- Reviewed notes: 1", report_text)
            self.assertIn("- Obsidian exports: 1", report_text)
            self.assertIn("- Generated exercises: 5", report_text)
            self.assertIn("- Graded exercises: 1", report_text)
            self.assertIn("## Misconceptions", report_text)
            self.assertIn("- normal_equals_central: normal_subgroup, active x1", report_text)
            self.assertIn("## Weak Concepts", report_text)
            self.assertIn("- quotient_group: 0.42", report_text)
            self.assertIn("## Recommended Next Steps", report_text)
            self.assertIn("- quotient_group: high, next_session", report_text)

    def _create_report_fixture(self, root: Path) -> Path:
        project = create_project(ProjectSpec(topic="Group Theory", path=root / "p"))
        session = project / "03_sessions" / "session_0001"
        session.mkdir()
        (session / "summary.md").write_text(
            "# Summary\n\nNormal subgroups were practiced through conjugation.\n",
            encoding="utf-8",
            newline="\n",
        )
        generate_atomic_note_draft(
            project,
            concept="Normal Subgroup",
            note_type="definition",
            body=(
                "A normal subgroup is stable under conjugation.\n\n"
                "## Review Questions\n\n"
                "- What condition distinguishes normality from centrality?\n"
            ),
            source_id="df-1",
        )
        review_atomic_note(project, "normal_subgroup")
        export_reviewed_notes_to_obsidian(project)
        generate_exercise_drafts(
            project,
            concept="Normal Subgroup",
            source_id="df-1",
            prerequisites=["subgroup", "conjugation"],
            count=5,
        )
        answer = root / "answer.md"
        feedback = root / "feedback.md"
        answer.write_text("Use conjugation invariance.\n", encoding="utf-8", newline="\n")
        feedback.write_text("Good core idea.\n", encoding="utf-8", newline="\n")
        approve_exercise_draft(project, "normal_subgroup_01")
        record_exercise_attempt(project, "normal_subgroup_01", answer)
        grade_exercise_attempt(project, "normal_subgroup_01_attempt_001", 0.8, feedback)
        context = load_project(project)
        update_learning_state(
            context=context,
            patch=LearningStatePatch(concept_mastery={"quotient_group": 0.42}),
        )
        build_review_schedule(context)
        return project


if __name__ == "__main__":
    unittest.main()
