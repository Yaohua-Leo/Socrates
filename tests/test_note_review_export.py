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
                body=(
                    "A normal subgroup is stable under conjugation. See [[Subgroup]].\n\n"
                    "## Review Questions\n\n"
                    "- How is normality different from commutativity?\n"
                ),
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

    def test_review_atomic_note_rejects_failed_quality_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            draft = project / "04_atomic_notes" / "drafts" / "bad_note.md"
            draft.write_text(
                "---\n"
                "status: draft\n"
                "review_status: needs_review\n"
                "reviewed_by_user: false\n"
                "type: definition\n"
                "concept: Bad Note\n"
                "source_id: df\n"
                "tags:\n"
                "  - bad-note\n"
                "related:\n"
                "  []\n"
                "---\n\n"
                "# Bad Note\n\n"
                "This draft is missing review questions.\n",
                encoding="utf-8",
                newline="\n",
            )

            with self.assertRaisesRegex(ValueError, "failed quality gate"):
                review_atomic_note(project, "bad_note")

            reviewed = project / "04_atomic_notes" / "definitions" / "bad_note.md"
            self.assertFalse(reviewed.exists())

    def test_export_reviewed_notes_to_obsidian_copies_only_reviewed_notes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            generate_atomic_note_draft(
                project,
                concept="Normal Subgroup",
                note_type="definition",
                body=(
                    "A normal subgroup is stable under conjugation.\n\n"
                    "## Review Questions\n\n"
                    "- What conjugation condition must be checked?\n"
                ),
                source_id="df",
            )
            review_atomic_note(project, "normal_subgroup")

            exported = export_reviewed_notes_to_obsidian(project)

            self.assertEqual(exported, [project / "07_exports" / "obsidian" / "normal_subgroup.md"])
            export_text = exported[0].read_text(encoding="utf-8")
            self.assertIn('status: "reviewed"', export_text)
            self.assertIn("reviewed_by_user: true", export_text)
            self.assertIn("# Normal Subgroup", export_text)

    def test_export_reviewed_notes_rejects_failed_quality_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            reviewed = project / "04_atomic_notes" / "definitions" / "legacy_bad_note.md"
            reviewed.write_text(
                "---\n"
                "status: reviewed\n"
                "review_status: approved\n"
                "reviewed_by_user: true\n"
                "type: definition\n"
                "concept: Legacy Bad Note\n"
                "source_id: df\n"
                "tags:\n"
                "  - legacy-bad-note\n"
                "related:\n"
                "  []\n"
                "---\n\n"
                "# Legacy Bad Note\n\n"
                "This legacy reviewed note is missing review questions.\n",
                encoding="utf-8",
                newline="\n",
            )

            with self.assertRaisesRegex(ValueError, "failed quality gate"):
                export_reviewed_notes_to_obsidian(project)

            exported = project / "07_exports" / "obsidian" / "legacy_bad_note.md"
            self.assertFalse(exported.exists())
            report = project / "08_evals" / "note_quality_eval.md"
            self.assertIn("definitions/legacy_bad_note.md: fail", report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
