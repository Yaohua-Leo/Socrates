from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from socrates.artifacts import generate_atomic_note_draft, generate_exercise_drafts
from socrates.context import load_project
from socrates.exercises import (
    approve_exercise_draft,
    grade_exercise_attempt,
    record_exercise_attempt,
)
from socrates.kb import build_reference_kb
from socrates.notes import export_reviewed_notes_to_obsidian, review_atomic_note
from socrates.planning import create_learning_plan
from socrates.project import ProjectSpec, create_project
from socrates.reports import (
    generate_monthly_report,
    generate_project_summary,
    generate_weekly_report,
)
from socrates.state import LearningStatePatch, build_review_schedule, update_learning_state
from socrates.tutoring import run_scripted_tutoring_session


REPO_ROOT = Path(__file__).resolve().parents[1]


class LifecycleAuditTests(unittest.TestCase):
    def test_lifecycle_audit_cli_fails_when_required_artifacts_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "lifecycle",
                    "audit",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("Lifecycle audit passed 1/12 checks", result.stdout)
            report = project / "08_evals" / "lifecycle_eval.md"
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("- Project metadata: pass", report_text)
            self.assertIn("- Learning plans: fail", report_text)
            self.assertIn("- Obsidian export: fail", report_text)

    def test_lifecycle_audit_cli_reports_complete_learning_loop(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "p"))
            curated = project / "01_references" / "curated" / "normal_subgroups.curated.md"
            curated.write_text(
                "### Definition: Normal Subgroup\n"
                "A normal subgroup is stable under conjugation.\n"
                "Depends: subgroup, conjugation\n",
                encoding="utf-8",
                newline="\n",
            )
            build_reference_kb(project)
            create_learning_plan(project)
            script = root / "session.script"
            script.write_text(
                "topic: Normal Subgroup\n"
                "question: What must you check to prove normality?\n"
                "hint: Track conjugation invariance.\n"
                "attempt: Show gNg^-1=N.\n"
                "next: Prove kernels are normal.\n",
                encoding="utf-8",
                newline="\n",
            )
            run_scripted_tutoring_session(project, script, session_id="session_0001")
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
                context,
                LearningStatePatch(concept_mastery={"quotient_group": 0.42}),
            )
            build_review_schedule(context)
            generate_weekly_report(project)
            generate_monthly_report(project)
            generate_project_summary(project)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "lifecycle",
                    "audit",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Lifecycle audit passed 12/12 checks", result.stdout)
            report = project / "08_evals" / "lifecycle_eval.md"
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("# Lifecycle Eval", report_text)
            self.assertIn("- Reference KB: pass", report_text)
            self.assertIn("- Tutoring session artifacts: pass", report_text)
            self.assertIn("- Obsidian export: pass", report_text)
            self.assertIn("- Learning reports: pass", report_text)

    def test_lifecycle_audit_accepts_completed_empty_review_schedule(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(concept_mastery={"normal_subgroup": 0.82}),
            )
            build_review_schedule(context)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "lifecycle",
                    "audit",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            report_text = (project / "08_evals" / "lifecycle_eval.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("- Review schedule: pass", report_text)


if __name__ == "__main__":
    unittest.main()
