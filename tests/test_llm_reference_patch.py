from pathlib import Path
import tempfile
import unittest

from socrates.llm import FakeLlmClient
from socrates.project import ProjectSpec, create_project
from socrates.references import (
    curate_reference,
    import_reference,
    suggest_correction_patch_with_llm,
)


class LlmReferencePatchTests(unittest.TestCase):
    def test_llm_suggestion_creates_pending_patch_only_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "group_theory"
            create_project(ProjectSpec(topic="Group Theory", path=project))
            source = root / "normality.md"
            source.write_text(
                "### Definition: Normal Subgroup\n"
                "A normal subgroup is a subgroup where every element commutes.\n",
                encoding="utf-8",
                newline="\n",
            )
            import_reference(project, source, role="lecture_notes", title="Normality")
            curate_reference(project, "normality")
            client = FakeLlmClient(
                [
                    "{"
                    '"location":"Definition: Normal Subgroup",'
                    '"original":"A normal subgroup is a subgroup where every element commutes.",'
                    '"proposed_correction":"A normal subgroup is stable under conjugation by every group element.",'
                    '"reason":"Normality is about conjugation invariance, not commutativity.",'
                    '"risk_level":"medium"'
                    "}"
                ]
            )

            patch_path = suggest_correction_patch_with_llm(
                project,
                "normality",
                client=client,
                location_hint="Definition: Normal Subgroup",
            )

            text = patch_path.read_text(encoding="utf-8")
            curated = (project / "01_references" / "curated" / "normality.curated.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("review_status: pending", text)
            self.assertIn("stable under conjugation", text)
            self.assertIn("A normal subgroup is a subgroup where every element commutes.", curated)
            self.assertTrue((project / "08_evals" / "llm_suggestions_manifest.json").exists())

    def test_rejects_suggestion_when_original_text_is_not_in_curated_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "group_theory"
            create_project(ProjectSpec(topic="Group Theory", path=project))
            source = root / "normality.md"
            source.write_text("### Definition: Normal Subgroup\nCorrect text.\n", encoding="utf-8")
            import_reference(project, source, role="lecture_notes", title="Normality")
            curate_reference(project, "normality")
            client = FakeLlmClient(
                [
                    "{"
                    '"location":"Definition",'
                    '"original":"not present",'
                    '"proposed_correction":"replacement",'
                    '"reason":"bad span",'
                    '"risk_level":"low"'
                    "}"
                ]
            )

            with self.assertRaisesRegex(ValueError, "original text was not found"):
                suggest_correction_patch_with_llm(project, "normality", client=client)


if __name__ == "__main__":
    unittest.main()
