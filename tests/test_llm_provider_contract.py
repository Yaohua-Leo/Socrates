from pathlib import Path
import json
import tempfile
import unittest

from socrates.llm import FakeLlmClient, LlmMessage, LlmRequest
from socrates.llm_artifacts import list_llm_suggestions, record_llm_suggestion


class LlmProviderContractTests(unittest.TestCase):
    def test_fake_client_returns_scripted_response_and_records_request(self) -> None:
        client = FakeLlmClient(['{"answer": "ok"}'])
        response = client.complete(
            LlmRequest(
                purpose="smoke",
                messages=(LlmMessage(role="user", content="Say ok"),),
                temperature=0.0,
            )
        )

        self.assertEqual(response.content, '{"answer": "ok"}')
        self.assertEqual(response.provider, "fake")
        self.assertEqual(response.model, "fake-model")
        self.assertEqual(len(client.requests), 1)

    def test_manifest_records_redacted_llm_suggestion_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            (project / "project.yaml").write_text("project: {}\n", encoding="utf-8")
            artifact = project / "03_sessions" / "s1" / "llm_next_question.md"
            artifact.parent.mkdir(parents=True)
            artifact.write_text("# Draft\n", encoding="utf-8", newline="\n")

            record_llm_suggestion(
                project,
                artifact_path=artifact,
                suggestion_type="tutoring_next_question",
                provider="deepseek",
                model="deepseek-v4-pro",
                source_paths=["03_sessions/s1/transcript.md"],
                prompt_hash="abc123",
            )

            records = list_llm_suggestions(project)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].suggestion_type, "tutoring_next_question")
            manifest = json.loads(
                (project / "08_evals" / "llm_suggestions_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertNotIn("DEEPSEEK_API_KEY", json.dumps(manifest))
            self.assertNotIn("real-secret", json.dumps(manifest))


if __name__ == "__main__":
    unittest.main()
