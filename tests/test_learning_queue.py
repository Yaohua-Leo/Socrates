from __future__ import annotations

from datetime import date
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from socrates.artifacts import generate_atomic_note_draft, generate_exercise_drafts
from socrates.context import load_project
from socrates.exercises import approve_exercise_draft, record_exercise_attempt
from socrates.notes import review_atomic_note
from socrates.project import ProjectSpec, create_project
from socrates.state import (
    LearningStatePatch,
    MistakeRecord,
    build_review_schedule,
    update_learning_state,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class LearningQueueTests(unittest.TestCase):
    def test_queue_cli_lists_actionable_notes_and_exercises(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "p"))
            generate_atomic_note_draft(
                project,
                concept="Normal Subgroup",
                note_type="definition",
                body=(
                    "A normal subgroup is stable under conjugation; compare [[Subgroup]].\n\n"
                    "## Review Questions\n\n"
                    "- What condition distinguishes normality from centrality?\n"
                ),
                source_id="df",
            )
            generate_atomic_note_draft(
                project,
                concept="Group Action",
                note_type="definition",
                body=(
                    "A group action is a compatible map from a group into permutations.\n\n"
                    "## Review Questions\n\n"
                    "- What compatibility axiom must be checked?\n"
                ),
                source_id="df",
            )
            review_atomic_note(project, "normal_subgroup")
            generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="df",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )
            answer = root / "answer.md"
            answer.write_text("Use conjugation invariance.\n", encoding="utf-8", newline="\n")
            approve_exercise_draft(project, "normal_subgroup_01")
            approve_exercise_draft(project, "normal_subgroup_02")
            record_exercise_attempt(project, "normal_subgroup_01", answer)

            result = subprocess.run(
                [sys.executable, "-m", "socrates", "queue", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("## Notes To Review", result.stdout)
            self.assertIn("- group_action | 04_atomic_notes/drafts/group_action.md", result.stdout)
            self.assertNotIn("- normal_subgroup | 04_atomic_notes/drafts/normal_subgroup.md", result.stdout)
            self.assertIn("## Exercise Drafts To Approve", result.stdout)
            self.assertIn(
                "- normal_subgroup_03 | 05_exercises/generated/normal_subgroup_03.md",
                result.stdout,
            )
            self.assertIn("## Exercises To Attempt", result.stdout)
            self.assertIn("- normal_subgroup_02 | 05_exercises/generated/normal_subgroup_02.md", result.stdout)
            self.assertIn("## Attempts To Grade", result.stdout)
            self.assertIn(
                (
                    "- normal_subgroup_01_attempt_001 | "
                    "05_exercises/attempted/normal_subgroup_01_attempt_001.md"
                ),
                result.stdout,
            )

    def test_queue_cli_lists_scheduled_reviews(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(concept_mastery={"normal_subgroup": 0.4}),
            )
            build_review_schedule(context, as_of=date(2026, 6, 4))

            result = subprocess.run(
                [sys.executable, "-m", "socrates", "queue", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("## Scheduled Reviews", result.stdout)
            self.assertIn(
                "- normal_subgroup | 02_learning_plan/review_schedule.md | scheduled for 2026-06-04",
                result.stdout,
            )

    def test_queue_cli_shows_scheduled_review_reason_and_repair_suggestion(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(
                    mistakes=[
                        MistakeRecord(
                            session_id="session-001",
                            concept="normal_subgroup",
                            misconception_id="normal_equals_central",
                            user_answer="Normal means central.",
                            analysis="Confuses normality with centrality.",
                            repair_suggestion="Compare gNg^-1=N with gn=ng.",
                        )
                    ],
                ),
            )
            build_review_schedule(context, as_of=date(2026, 6, 4))

            result = subprocess.run(
                [sys.executable, "-m", "socrates", "queue", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(
                (
                    "- normal_subgroup | 02_learning_plan/review_schedule.md | "
                    "scheduled for 2026-06-07; "
                    "reason: active misconception normal_equals_central x1; "
                    "repair: Compare gNg^-1=N with gn=ng."
                ),
                result.stdout,
            )

    def test_queue_cli_orders_scheduled_reviews_by_date(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(
                    concept_mastery={
                        "alpha_medium_review": 0.62,
                        "zeta_urgent_review": 0.4,
                    }
                ),
            )
            build_review_schedule(context, as_of=date(2026, 6, 4))

            result = subprocess.run(
                [sys.executable, "-m", "socrates", "queue", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            urgent = (
                "- zeta_urgent_review | 02_learning_plan/review_schedule.md | "
                "scheduled for 2026-06-04"
            )
            medium = (
                "- alpha_medium_review | 02_learning_plan/review_schedule.md | "
                "scheduled for 2026-06-07"
            )
            self.assertIn(urgent, result.stdout)
            self.assertIn(medium, result.stdout)
            self.assertLess(result.stdout.index(urgent), result.stdout.index(medium))


if __name__ == "__main__":
    unittest.main()
