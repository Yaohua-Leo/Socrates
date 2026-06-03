from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from socrates.project import ProjectSpec, create_project
from socrates.references import curate_reference, import_reference


REPO_ROOT = Path(__file__).resolve().parents[1]


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

    def test_curate_markdown_reference_creates_curated_draft_and_updates_registry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "project"))
            source = root / "normal_subgroups.md"
            source.write_text("### Definition: Normal Subgroup\nStable under conjugation.\n", encoding="utf-8")
            record = import_reference(
                project,
                source,
                role="lecture_notes",
                title="Normal Subgroups Notes",
            )

            curated = curate_reference(project, record.id)

            self.assertEqual(
                curated.relative_to(project).as_posix(),
                "01_references/curated/normal_subgroups_notes.curated.md",
            )
            converted = project / "01_references" / "converted" / "markdown" / "normal_subgroups_notes.md"
            self.assertTrue(converted.exists())
            converted_text = converted.read_text(encoding="utf-8")
            self.assertIn("# Converted Reference: Normal Subgroups Notes", converted_text)
            self.assertIn("### Definition: Normal Subgroup", converted_text)
            curated_text = curated.read_text(encoding="utf-8")
            self.assertIn("# Curated Reference: Normal Subgroups Notes", curated_text)
            self.assertIn("source_id: normal_subgroups_notes", curated_text)
            self.assertIn("### Definition: Normal Subgroup", curated_text)

            registry = (project / "01_references" / "source_registry.yaml").read_text(
                encoding="utf-8"
            )
            self.assertIn("status: curated_draft", registry)
            self.assertIn(
                'markdown: "01_references/converted/markdown/normal_subgroups_notes.md"',
                registry,
            )
            self.assertIn(
                'curated: "01_references/curated/normal_subgroups_notes.curated.md"',
                registry,
            )
            project_log = (project / "00_meta" / "project_log.md").read_text(encoding="utf-8")
            self.assertIn("Created curated draft for reference normal_subgroups_notes", project_log)

    def test_curate_command_creates_curated_reference_from_cli(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "project"))
            source = root / "normal_subgroups.txt"
            source.write_text("### Definition: Normal Subgroup\nStable under conjugation.\n", encoding="utf-8")
            record = import_reference(
                project,
                source,
                role="lecture_notes",
                title="Normal Subgroups Notes",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "curate",
                    "--project",
                    str(project),
                    "--source-id",
                    record.id,
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Curated reference normal_subgroups_notes", result.stdout)
            self.assertTrue(
                (project / "01_references" / "curated" / "normal_subgroups_notes.curated.md").exists()
            )

    def test_curate_latex_reference_converts_sections_and_definition_environments(self) -> None:
        from socrates.kb import build_reference_kb

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "project"))
            source = root / "normal_subgroups.tex"
            source.write_text(
                "\\section{Normal Subgroups}\n"
                "\\begin{definition}[Normal Subgroup]\n"
                "A subgroup N of G is normal if gNg^{-1}=N for every g in G.\n"
                "Depends: subgroup, conjugation\n"
                "\\end{definition}\n",
                encoding="utf-8",
                newline="\n",
            )
            record = import_reference(
                project,
                source,
                role="lecture_notes",
                title="Normal Subgroups TeX",
            )

            curate_reference(project, record.id)
            result = build_reference_kb(project)

            converted = project / "01_references" / "converted" / "markdown" / "normal_subgroups_tex.md"
            converted_text = converted.read_text(encoding="utf-8")
            self.assertIn("## Normal Subgroups", converted_text)
            self.assertIn("### Definition: Normal Subgroup", converted_text)
            self.assertEqual(result.object_count, 1)


if __name__ == "__main__":
    unittest.main()
