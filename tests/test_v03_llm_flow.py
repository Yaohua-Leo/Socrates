from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from socrates.llm import FakeLlmClient
from socrates.project import ProjectSpec, create_project
from socrates.references import curate_reference, import_reference, suggest_correction_patch_with_llm
from socrates.tutoring import run_scripted_tutoring_session, suggest_next_question_with_llm


REPO_ROOT = Path(__file__).resolve().parents[1]


class V03LlmFlowTests(unittest.TestCase):
    def test_fake_llm_reference_and_tutoring_suggestions_are_visible_in_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "group_theory"
            create_project(ProjectSpec(topic="Group Theory", path=project))
            reference = root / "normality.md"
            reference.write_text(
                "### Definition: Normal Subgroup\n"
                "A normal subgroup is a subgroup where every element commutes.\n",
                encoding="utf-8",
                newline="\n",
            )
            import_reference(project, reference, role="lecture_notes", title="Normality")
            curate_reference(project, "normality")
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
            client = FakeLlmClient(
                [
                    "{"
                    '"location":"Definition",'
                    '"original":"A normal subgroup is a subgroup where every element commutes.",'
                    '"proposed_correction":"A normal subgroup is stable under conjugation by every group element.",'
                    '"reason":"Normality is about conjugation invariance.",'
                    '"risk_level":"medium"'
                    "}",
                    "{"
                    '"question":"How would you test gng^-1 for arbitrary g?",'
                    '"reason":"Targets normal_equals_abelian.",'
                    '"expected_student_action":"Use conjugation invariance."'
                    "}",
                ]
            )

            suggest_correction_patch_with_llm(project, "normality", client=client)
            suggest_next_question_with_llm(project, "session_0001", client=client)
            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("LLM suggestion drafts: 2", status.stdout)
            self.assertTrue((project / "08_evals" / "llm_suggestions_manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
