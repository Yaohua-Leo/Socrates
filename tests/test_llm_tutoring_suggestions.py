from pathlib import Path
import tempfile
import unittest

from socrates.llm import FakeLlmClient
from socrates.project import ProjectSpec, create_project
from socrates.tutoring import run_scripted_tutoring_session, suggest_next_question_with_llm


class LlmTutoringSuggestionTests(unittest.TestCase):
    def test_next_question_suggestion_writes_draft_without_mutating_transcript(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "group_theory"
            create_project(ProjectSpec(topic="Group Theory", path=project))
            script = root / "session.script"
            script.write_text(
                "topic: Normal Subgroup\n"
                "question: What does normality require?\n"
                "attempt: It means abelian.\n"
                "misconception: normal_equals_abelian\n",
                encoding="utf-8",
                newline="\n",
            )
            run_scripted_tutoring_session(project, script, session_id="session_0001")
            transcript_path = project / "03_sessions" / "session_0001" / "transcript.md"
            transcript_before = transcript_path.read_text(encoding="utf-8")
            client = FakeLlmClient(
                [
                    "{"
                    '"question":"Can you test normality using conjugation by an arbitrary group element?",'
                    '"reason":"Targets the active normal_equals_abelian misconception.",'
                    '"expected_student_action":"Compare commutativity with conjugation invariance."'
                    "}"
                ]
            )

            artifact = suggest_next_question_with_llm(project, "session_0001", client=client)

            self.assertTrue(artifact.exists())
            text = artifact.read_text(encoding="utf-8")
            self.assertIn("status: draft", text)
            self.assertIn("conjugation", text)
            self.assertEqual(transcript_before, transcript_path.read_text(encoding="utf-8"))
            self.assertTrue((project / "08_evals" / "llm_suggestions_manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
