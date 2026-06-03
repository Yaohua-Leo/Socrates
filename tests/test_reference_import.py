from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from socrates.project import ProjectSpec, create_project
from socrates.references import import_reference


class ReferenceImportTests(unittest.TestCase):
    def test_import_markdown_source_copies_file_and_updates_registry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "project"))
            source = root / "normal_subgroups.md"
            source.write_text("# Normal Subgroups\n", encoding="utf-8")

            record = import_reference(
                project,
                source,
                role="lecture_notes",
                title="Normal Subgroups Notes",
                priority=2,
                notes="Local notes for the first session.",
            )

            copied = project / "01_references" / "raw" / "markdown" / "normal_subgroups.md"
            self.assertTrue(copied.exists())
            self.assertEqual(copied.read_text(encoding="utf-8"), "# Normal Subgroups\n")
            self.assertEqual(record.id, "normal_subgroups_notes")
            self.assertEqual(record.type, "markdown")
            self.assertEqual(record.status, "raw_imported")
            self.assertEqual(record.local_path, "01_references/raw/markdown/normal_subgroups.md")

            registry = (project / "01_references" / "source_registry.yaml").read_text(
                encoding="utf-8"
            )
            self.assertIn("- id: normal_subgroups_notes", registry)
            self.assertIn("role: lecture_notes", registry)
            self.assertIn("priority: 2", registry)
            self.assertIn('title: "Normal Subgroups Notes"', registry)

            project_log = (project / "00_meta" / "project_log.md").read_text(encoding="utf-8")
            self.assertIn("Imported reference normal_subgroups_notes", project_log)

    def test_import_pdf_source_uses_books_folder_and_unique_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "project"))
            first = root / "abstract_algebra.pdf"
            second = root / "abstract_algebra_copy.pdf"
            first.write_bytes(b"%PDF first")
            second.write_bytes(b"%PDF second")

            first_record = import_reference(project, first, role="main_textbook", title="Abstract Algebra")
            second_record = import_reference(
                project,
                second,
                role="secondary_reference",
                title="Abstract Algebra",
            )

            self.assertEqual(first_record.local_path, "01_references/raw/books/abstract_algebra.pdf")
            self.assertEqual(second_record.id, "abstract_algebra_2")
            self.assertTrue((project / "01_references" / "raw" / "books" / "abstract_algebra.pdf").exists())
            self.assertTrue(
                (project / "01_references" / "raw" / "books" / "abstract_algebra_copy.pdf").exists()
            )


if __name__ == "__main__":
    unittest.main()
