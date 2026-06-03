from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from socrates.artifacts import generate_atomic_note_draft
from socrates.notes import export_reviewed_notes_to_obsidian, review_atomic_note
from socrates.project import ProjectSpec, create_project


class NoteReviewExportTests(unittest.TestCase):
    def test_review_atomic_note_promotes_draft_without_deleting_original(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            generate_atomic_note_draft(
                project,
                concept="Normal Subgroup",
                note_type="definition",
                body="A normal subgroup is stable under conjugation. See [[Subgroup]].",
                source_id="df",
                source_title="Dummit and Foote",
            )

            reviewed = review_atomic_note(project, "normal_subgroup")

            draft = project / "04_atomic_notes" / "drafts" / "normal_subgroup.md"
            self.assertTrue(draft.exists())
            self.assertEqual(reviewed, project / "04_atomic_notes" / "definitions" / "normal_subgroup.md")
            text = reviewed.read_text(encoding="utf-8")
            self.assertIn('status: "reviewed"', text)
            self.assertIn("reviewed_by_user: true", text)
            self.assertIn("[[Subgroup]]", text)

    def test_export_reviewed_notes_to_obsidian_copies_only_reviewed_notes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            generate_atomic_note_draft(
                project,
                concept="Normal Subgroup",
                note_type="definition",
                body="A normal subgroup is stable under conjugation.",
                source_id="df",
            )
            review_atomic_note(project, "normal_subgroup")

            exported = export_reviewed_notes_to_obsidian(project)

            self.assertEqual(exported, [project / "07_exports" / "obsidian" / "normal_subgroup.md"])
            export_text = exported[0].read_text(encoding="utf-8")
            self.assertIn('status: "reviewed"', export_text)
            self.assertIn("reviewed_by_user: true", export_text)
            self.assertIn("# Normal Subgroup", export_text)


if __name__ == "__main__":
    unittest.main()
