from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from socrates.artifacts import generate_atomic_note_draft
from socrates.kb import build_reference_kb
from socrates.notes import export_reviewed_notes_to_obsidian, review_atomic_note
from socrates.project import ProjectSpec, create_project


REPO_ROOT = Path(__file__).resolve().parents[1]


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

    def test_status_excludes_reviewed_notes_from_pending_drafts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            generate_atomic_note_draft(
                project,
                concept="Normal Subgroup",
                note_type="definition",
                body=(
                    "A normal subgroup is stable under conjugation.\n\n"
                    "## Review Questions\n\n"
                    "- How is normality different from commutativity?\n"
                ),
                source_id="df",
            )
            review_atomic_note(project, "normal_subgroup")

            result = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Pending draft notes: 0", result.stdout)
            self.assertIn("Reviewed notes: 1", result.stdout)

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
            curated = project / "01_references" / "curated" / "normal_subgroups.curated.md"
            curated.write_text(
                "### Definition: Normal Subgroup\n"
                "A normal subgroup is stable under conjugation.\n"
                "Depends: subgroup, conjugation\n",
                encoding="utf-8",
                newline="\n",
            )
            build_reference_kb(project)
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
                source_title="Dummit and Foote",
                source_location="Section 3.1",
            )
            review_atomic_note(project, "normal_subgroup")

            exported = export_reviewed_notes_to_obsidian(project)

            self.assertEqual(exported, [project / "07_exports" / "obsidian" / "normal_subgroup.md"])
            export_text = exported[0].read_text(encoding="utf-8")
            self.assertIn('status: "reviewed"', export_text)
            self.assertIn("reviewed_by_user: true", export_text)
            self.assertIn("# Normal Subgroup", export_text)
            export_index = project / "07_exports" / "obsidian" / "_socrates_index.md"
            self.assertTrue(export_index.exists())
            export_index_text = export_index.read_text(encoding="utf-8")
            self.assertIn("# Socrates Obsidian Export", export_index_text)
            self.assertIn("## Definition", export_index_text)
            self.assertIn("- [[normal_subgroup|Normal Subgroup]]", export_index_text)
            self.assertIn("  - Source: Dummit and Foote, Section 3.1", export_index_text)
            self.assertIn(
                "  - Tags: #definition #normal-subgroup #subgroup #conjugation",
                export_index_text,
            )
            self.assertIn("  - Related: [[Subgroup]], [[Conjugation]]", export_index_text)
            manifest = json.loads(
                (project / "07_exports" / "obsidian" / "export_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(manifest["version"], 2)
            self.assertEqual(
                manifest["exported_notes"],
                [
                    {
                        "note_id": "normal_subgroup",
                        "concept": "Normal Subgroup",
                        "type": "definition",
                        "path": "normal_subgroup.md",
                        "review_status": "approved",
                        "source_id": "df",
                        "source_title": "Dummit and Foote",
                        "source_location": "Section 3.1",
                        "tags": ["definition", "normal-subgroup", "subgroup", "conjugation"],
                        "related": ["[[Subgroup]]", "[[Conjugation]]"],
                    }
                ],
            )

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
