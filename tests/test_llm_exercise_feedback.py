from pathlib import Path
import tempfile
import unittest

from socrates.artifacts import generate_exercise_drafts
from socrates.exercises import (
    approve_exercise_draft,
    list_exercises,
    record_exercise_attempt,
    suggest_exercise_feedback_with_llm,
)
from socrates.llm import FakeLlmClient
from socrates.project import ProjectSpec, create_project


class LlmExerciseFeedbackTests(unittest.TestCase):
    def test_feedback_suggestion_does_not_grade_or_update_learning_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "group_theory"
            create_project(ProjectSpec(topic="Group Theory", path=project))
            draft = generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="manual",
                count=5,
            )[0]
            approve_exercise_draft(project, draft.id)
            answer = root / "answer.md"
            answer.write_text("I think normal just means abelian.", encoding="utf-8")
            attempt_path = record_exercise_attempt(project, draft.id, answer)
            learning_state_path = project / "00_meta" / "learning_state.json"
            learning_state_before = learning_state_path.read_text(encoding="utf-8")
            client = FakeLlmClient(
                [
                    "{"
                    '"score_suggestion":0.2,'
                    '"misconception_id":"normal_equals_abelian",'
                    '"analysis":"The answer confuses normality with commutativity.",'
                    '"repair_suggestion":"Ask for conjugation invariance.",'
                    '"follow_up_prompt":"Test gng^-1 for an arbitrary g."'
                    "}"
                ]
            )

            artifact = suggest_exercise_feedback_with_llm(
                project,
                attempt_path.stem,
                client=client,
            )

            self.assertTrue(artifact.exists())
            text = artifact.read_text(encoding="utf-8")
            self.assertIn("status: draft", text)
            self.assertIn("normal_equals_abelian", text)
            exercise = next(item for item in list_exercises(project) if item.exercise_id == draft.id)
            self.assertEqual(exercise.detail, f"attempt {attempt_path.stem}")
            self.assertEqual(learning_state_before, learning_state_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
