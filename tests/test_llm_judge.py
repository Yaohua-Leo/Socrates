from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from socrates.llm import FakeLlmClient
from socrates.llm_artifacts import list_llm_suggestions
from socrates.llm_judge import suggest_session_judge_with_llm
from socrates.project import ProjectSpec, create_project
from socrates.session_score import score_teaching_session
from socrates.tutoring import run_scripted_tutoring_session


class LlmJudgeTests(unittest.TestCase):
    def test_session_judge_draft_records_manifest_without_mutating_trusted_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "p"))
            script = root / "session.script"
            script.write_text(
                "topic: Normal Subgroup\n"
                "goal: Separate normality from commutativity.\n"
                "question: What does normality require?\n"
                "hint: Check conjugation invariance.\n"
                "attempt: It means abelian.\n"
                "misconception: normal_equals_abelian\n"
                "next: Compare gNg^-1=N with elementwise commutativity.\n",
                encoding="utf-8",
                newline="\n",
            )
            run_scripted_tutoring_session(project, script, session_id="session_0001")
            score_teaching_session(project, session_id="session_0001")
            transcript_path = project / "03_sessions" / "session_0001" / "transcript.md"
            learning_state_path = project / "00_meta" / "learning_state.json"
            score_manifest_path = project / "08_evals" / "session_score_manifest.json"
            transcript_before = transcript_path.read_text(encoding="utf-8")
            learning_state_before = learning_state_path.read_text(encoding="utf-8")
            score_manifest_before = score_manifest_path.read_text(encoding="utf-8")
            client = FakeLlmClient(
                [
                    json.dumps(
                        {
                            "summary": "The session is usable but needs human review.",
                            "rubric_findings": [
                                "The tutor asked a follow-up question before stating a solution."
                            ],
                            "risks": ["The misconception may be under-specified."],
                            "recommended_human_checks": [
                                "Confirm normality versus commutativity was addressed."
                            ],
                            "confidence": "medium",
                        }
                    )
                ]
            )

            artifact = suggest_session_judge_with_llm(project, "session_0001", client=client)

            self.assertTrue(artifact.exists())
            text = artifact.read_text(encoding="utf-8")
            self.assertIn("status: draft", text)
            self.assertIn("quality_boundary: review_only_llm_judge_draft", text)
            self.assertIn("# LLM Session Judge Draft", text)
            self.assertIn("not a deterministic score", text)
            self.assertIn("The misconception may be under-specified.", text)
            self.assertEqual(transcript_before, transcript_path.read_text(encoding="utf-8"))
            self.assertEqual(learning_state_before, learning_state_path.read_text(encoding="utf-8"))
            self.assertEqual(score_manifest_before, score_manifest_path.read_text(encoding="utf-8"))
            records = list_llm_suggestions(project)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].suggestion_type, "session_quality_judge")
            self.assertEqual(records[0].status, "draft")
            self.assertEqual(records[0].artifact_path, "03_sessions/session_0001/llm_session_judge.md")
            manifest_text = (project / "08_evals" / "llm_suggestions_manifest.json").read_text(
                encoding="utf-8"
            )
            self.assertIn("03_sessions/session_0001/transcript.md", manifest_text)
            self.assertIn("08_evals/session_score_manifest.json", manifest_text)

    def test_session_judge_rejects_missing_required_fields_without_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "p"))
            script = root / "session.script"
            script.write_text(
                "topic: Normal Subgroup\n"
                "question: What does normality require?\n"
                "attempt: It requires conjugation invariance.\n",
                encoding="utf-8",
                newline="\n",
            )
            run_scripted_tutoring_session(project, script, session_id="session_0001")
            client = FakeLlmClient(
                [
                    json.dumps(
                        {
                            "summary": "Needs review.",
                            "rubric_findings": ["Question was Socratic."],
                            "risks": ["No deterministic score context was present."],
                            "confidence": "low",
                        }
                    )
                ]
            )

            with self.assertRaises(ValueError):
                suggest_session_judge_with_llm(project, "session_0001", client=client)

            self.assertFalse(
                (project / "03_sessions" / "session_0001" / "llm_session_judge.md").exists()
            )

    def test_session_judge_rejects_non_string_list_items(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "p"))
            script = root / "session.script"
            script.write_text(
                "topic: Normal Subgroup\n"
                "question: What does normality require?\n"
                "attempt: It requires conjugation invariance.\n",
                encoding="utf-8",
                newline="\n",
            )
            run_scripted_tutoring_session(project, script, session_id="session_0001")
            client = FakeLlmClient(
                [
                    json.dumps(
                        {
                            "summary": "Needs review.",
                            "rubric_findings": [42],
                            "risks": ["No deterministic score context was present."],
                            "recommended_human_checks": ["Review the transcript."],
                            "confidence": "low",
                        }
                    )
                ]
            )

            with self.assertRaises(ValueError):
                suggest_session_judge_with_llm(project, "session_0001", client=client)

            self.assertFalse(
                (project / "03_sessions" / "session_0001" / "llm_session_judge.md").exists()
            )


if __name__ == "__main__":
    unittest.main()
