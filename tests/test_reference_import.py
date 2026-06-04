from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from socrates.kb import build_reference_kb
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

    def test_curate_pdf_reference_records_conversion_pending_without_curated_draft(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "project"))
            source = root / "abstract_algebra.pdf"
            source.write_bytes(b"%PDF placeholder")
            record = import_reference(
                project,
                source,
                role="main_textbook",
                title="Abstract Algebra",
            )

            pending = curate_reference(project, record.id)

            self.assertEqual(
                pending.relative_to(project).as_posix(),
                "01_references/converted/markdown/abstract_algebra.conversion_pending.md",
            )
            pending_text = pending.read_text(encoding="utf-8")
            self.assertIn("# Conversion Pending: Abstract Algebra", pending_text)
            self.assertIn("- source_id: abstract_algebra", pending_text)
            self.assertIn("- raw_path: 01_references/raw/books/abstract_algebra.pdf", pending_text)
            self.assertFalse(
                (project / "01_references" / "curated" / "abstract_algebra.curated.md").exists()
            )

            registry = (project / "01_references" / "source_registry.yaml").read_text(
                encoding="utf-8"
            )
            self.assertIn("status: conversion_pending", registry)
            self.assertIn(
                'markdown: "01_references/converted/markdown/abstract_algebra.conversion_pending.md"',
                registry,
            )
            self.assertIn("curated: null", registry)

    def test_status_reports_conversion_pending_references(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "project"))
            source = root / "abstract_algebra.pdf"
            source.write_bytes(b"%PDF placeholder")
            record = import_reference(
                project,
                source,
                role="main_textbook",
                title="Abstract Algebra",
            )
            curate_reference(project, record.id)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "status",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Conversion pending references: 1", result.stdout)

    def test_sources_list_cli_shows_registry_status_and_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "project"))
            notes = root / "normal_subgroups.md"
            book = root / "abstract_algebra.pdf"
            notes.write_text(
                "### Definition: Normal Subgroup\nStable under conjugation.\n",
                encoding="utf-8",
                newline="\n",
            )
            book.write_bytes(b"%PDF placeholder")
            notes_record = import_reference(
                project,
                notes,
                role="lecture_notes",
                title="Normal Subgroups Notes",
                priority=2,
                notes="Local notes for the first session.",
            )
            book_record = import_reference(
                project,
                book,
                role="main_textbook",
                title="Abstract Algebra",
            )
            curate_reference(project, notes_record.id)
            curate_reference(project, book_record.id)

            all_sources = subprocess.run(
                [sys.executable, "-m", "socrates", "sources", "list", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            pending_sources = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "sources",
                    "list",
                    "--project",
                    str(project),
                    "--status",
                    "conversion_pending",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            lecture_sources = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "sources",
                    "list",
                    "--project",
                    str(project),
                    "--role",
                    "lecture_notes",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            pdf_sources = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "sources",
                    "list",
                    "--project",
                    str(project),
                    "--type",
                    "pdf",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(all_sources.returncode, 0, all_sources.stderr)
            curated_line = (
                "- normal_subgroups_notes | curated_draft | markdown | "
                "lecture_notes | priority 2 | Normal Subgroups Notes"
            )
            pending_line = (
                "- abstract_algebra | conversion_pending | pdf | "
                "main_textbook | priority 1 | Abstract Algebra"
            )
            self.assertIn("# Source Registry", all_sources.stdout)
            self.assertIn(curated_line, all_sources.stdout)
            self.assertIn("  - raw: 01_references/raw/markdown/normal_subgroups.md", all_sources.stdout)
            self.assertIn(
                "  - markdown: 01_references/converted/markdown/normal_subgroups_notes.md",
                all_sources.stdout,
            )
            self.assertIn(
                "  - curated: 01_references/curated/normal_subgroups_notes.curated.md",
                all_sources.stdout,
            )
            self.assertIn("  - notes: Local notes for the first session.", all_sources.stdout)
            self.assertIn(pending_line, all_sources.stdout)
            self.assertIn(
                "  - markdown: 01_references/converted/markdown/abstract_algebra.conversion_pending.md",
                all_sources.stdout,
            )
            self.assertIn("  - curated: none", all_sources.stdout)

            self.assertEqual(pending_sources.returncode, 0, pending_sources.stderr)
            self.assertIn(pending_line, pending_sources.stdout)
            self.assertNotIn("normal_subgroups_notes", pending_sources.stdout)

            self.assertEqual(lecture_sources.returncode, 0, lecture_sources.stderr)
            self.assertIn(curated_line, lecture_sources.stdout)
            self.assertNotIn("abstract_algebra", lecture_sources.stdout)

            self.assertEqual(pdf_sources.returncode, 0, pdf_sources.stderr)
            self.assertIn(pending_line, pdf_sources.stdout)
            self.assertNotIn("normal_subgroups_notes", pdf_sources.stdout)

    def test_sources_list_cli_shows_checked_curated_quality_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "project"))
            notes = root / "normal_subgroups.md"
            notes.write_text(
                "### Definition: Normal Subgroup\n"
                "A normal subgroup is stable under conjugation.\n"
                "Depends: subgroup, conjugation\n",
                encoding="utf-8",
                newline="\n",
            )
            record = import_reference(
                project,
                notes,
                role="lecture_notes",
                title="Normal Subgroups Notes",
            )
            curate_reference(project, record.id)

            check = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "kb",
                    "check",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            sources = subprocess.run(
                [sys.executable, "-m", "socrates", "sources", "list", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(check.returncode, 0, check.stderr)
            self.assertEqual(sources.returncode, 0, sources.stderr)
            self.assertIn(
                "- normal_subgroups_notes | curated_draft | markdown | "
                "lecture_notes | priority 1 | Normal Subgroups Notes",
                sources.stdout,
            )
            self.assertIn("  - curated quality: pass", sources.stdout)

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

    def test_curate_latex_reference_preserves_numbered_object_titles_for_kb(self) -> None:
        from socrates.kb import build_reference_kb

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "project"))
            source = root / "normal_subgroups.tex"
            source.write_text(
                "\\section{Normal Subgroups}\n"
                "\\begin{definition}[3.1 Normal Subgroup]\n"
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
            index = result.index_path.read_text(encoding="utf-8")
            self.assertIn("### Definition 3.1: Normal Subgroup", converted_text)
            self.assertIn('"number": "3.1"', index)

    def test_curate_latex_reference_converts_common_theorem_environment_aliases(self) -> None:
        from socrates.kb import build_reference_kb

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "project"))
            source = root / "normality_aliases.tex"
            source.write_text(
                "\\section{Normality}\n"
                "\\begin{defn}[3.1 Normal Subgroup]\n"
                "A subgroup N is normal if gNg^{-1}=N.\n"
                "\\end{defn}\n"
                "\\begin{thm}[3.2 Kernel Normality]\n"
                "The kernel of a homomorphism is normal.\n"
                "Depends: kernel, homomorphism\n"
                "\\end{thm}\n"
                "\\begin{lem}[3.3 Coset Lemma]\n"
                "Cosets are equal or disjoint.\n"
                "\\end{lem}\n"
                "\\begin{prop}[3.4 Quotient Multiplication]\n"
                "Coset multiplication is well-defined for normal subgroups.\n"
                "\\end{prop}\n"
                "\\begin{cor}[3.5 Quotient Group]\n"
                "The quotient by a normal subgroup is a group.\n"
                "\\end{cor}\n",
                encoding="utf-8",
                newline="\n",
            )
            record = import_reference(
                project,
                source,
                role="lecture_notes",
                title="Normality Aliases",
            )

            curate_reference(project, record.id)
            result = build_reference_kb(project)

            converted = project / "01_references" / "converted" / "markdown" / "normality_aliases.md"
            converted_text = converted.read_text(encoding="utf-8")
            index = json.loads(result.index_path.read_text(encoding="utf-8"))
            self.assertIn("### Definition 3.1: Normal Subgroup", converted_text)
            self.assertIn("### Theorem 3.2: Kernel Normality", converted_text)
            self.assertIn("### Lemma 3.3: Coset Lemma", converted_text)
            self.assertIn("### Proposition 3.4: Quotient Multiplication", converted_text)
            self.assertIn("### Corollary 3.5: Quotient Group", converted_text)
            self.assertEqual(result.object_count, 5)
            self.assertEqual(
                [item["type"] for item in index["objects"]],
                ["definition", "theorem", "lemma", "proposition", "corollary"],
            )

    def test_patch_command_writes_patch_only_correction_without_mutating_references(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "project"))
            source = root / "normal_subgroups.md"
            source.write_text(
                "### Definition: Normal Subgroup\n"
                "Let G he a group. A subgroup N is normal when gNg^{-1}=N.\n",
                encoding="utf-8",
                newline="\n",
            )
            record = import_reference(
                project,
                source,
                role="lecture_notes",
                title="Normality OCR Notes",
            )
            curated = curate_reference(project, record.id)
            raw = project / "01_references" / "raw" / "markdown" / "normal_subgroups.md"
            converted = (
                project
                / "01_references"
                / "converted"
                / "markdown"
                / "normality_ocr_notes.md"
            )
            raw_before = raw.read_text(encoding="utf-8")
            converted_before = converted.read_text(encoding="utf-8")
            curated_before = curated.read_text(encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "patch",
                    "--project",
                    str(project),
                    "--source-id",
                    record.id,
                    "--location",
                    "Definition paragraph 1",
                    "--original",
                    "Let G he a group.",
                    "--proposed-correction",
                    "Let G be a group.",
                    "--reason",
                    "OCR likely misread be as he.",
                    "--risk-level",
                    "low",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Wrote correction patch", result.stdout)
            patch = (
                project
                / "01_references"
                / "converted"
                / "patches"
                / "normality_ocr_notes_patch_001.patch.md"
            )
            self.assertTrue(patch.exists())
            patch_text = patch.read_text(encoding="utf-8")
            self.assertIn("# Correction Patch: Normality OCR Notes", patch_text)
            self.assertIn("## Patch 001", patch_text)
            self.assertIn("- source_id: normality_ocr_notes", patch_text)
            self.assertIn(
                "- converted_path: 01_references/converted/markdown/normality_ocr_notes.md",
                patch_text,
            )
            self.assertIn("### Location\n\nDefinition paragraph 1", patch_text)
            self.assertIn("### Original\n\n```text\nLet G he a group.\n```", patch_text)
            self.assertIn(
                "### Proposed Correction\n\n```text\nLet G be a group.\n```",
                patch_text,
            )
            self.assertIn("### Reason\n\nOCR likely misread be as he.", patch_text)
            self.assertIn("### Risk Level\n\nlow", patch_text)
            self.assertEqual(raw.read_text(encoding="utf-8"), raw_before)
            self.assertEqual(converted.read_text(encoding="utf-8"), converted_before)
            self.assertEqual(curated.read_text(encoding="utf-8"), curated_before)

    def test_patches_list_and_status_show_pending_correction_patches(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "project"))
            source = root / "normal_subgroups.md"
            source.write_text(
                "### Definition: Normal Subgroup\n"
                "Let G he a group. A subgroup N is normal when gNg^{-1}=N.\n",
                encoding="utf-8",
                newline="\n",
            )
            record = import_reference(
                project,
                source,
                role="lecture_notes",
                title="Normality OCR Notes",
            )
            curate_reference(project, record.id)
            patch_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "patch",
                    "--project",
                    str(project),
                    "--source-id",
                    record.id,
                    "--location",
                    "Definition paragraph 1",
                    "--original",
                    "Let G he a group.",
                    "--proposed-correction",
                    "Let G be a group.",
                    "--reason",
                    "OCR likely misread be as he.",
                    "--risk-level",
                    "low",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            list_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "patches",
                    "list",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            status_result = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(patch_result.returncode, 0, patch_result.stderr)
            self.assertEqual(list_result.returncode, 0, list_result.stderr)
            self.assertIn("# Correction Patches", list_result.stdout)
            self.assertIn(
                (
                    "- normality_ocr_notes_patch_001 | pending | normality_ocr_notes | "
                    "low | Definition paragraph 1 | "
                    "01_references/converted/patches/normality_ocr_notes_patch_001.patch.md"
                ),
                list_result.stdout,
            )
            self.assertEqual(status_result.returncode, 0, status_result.stderr)
            self.assertIn("Correction patches: 1", status_result.stdout)
            self.assertIn("Pending correction patches: 1", status_result.stdout)

    def test_patches_review_records_human_decision_without_mutating_references(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "project"))
            source = root / "normal_subgroups.md"
            source.write_text(
                "### Definition: Normal Subgroup\n"
                "Let G he a group. A subgroup N is normal when gNg^{-1}=N.\n",
                encoding="utf-8",
                newline="\n",
            )
            record = import_reference(
                project,
                source,
                role="lecture_notes",
                title="Normality OCR Notes",
            )
            curated = curate_reference(project, record.id)
            raw = project / "01_references" / "raw" / "markdown" / "normal_subgroups.md"
            converted = (
                project
                / "01_references"
                / "converted"
                / "markdown"
                / "normality_ocr_notes.md"
            )
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "patch",
                    "--project",
                    str(project),
                    "--source-id",
                    record.id,
                    "--location",
                    "Definition paragraph 1",
                    "--original",
                    "Let G he a group.",
                    "--proposed-correction",
                    "Let G be a group.",
                    "--reason",
                    "OCR likely misread be as he.",
                    "--risk-level",
                    "low",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=True,
            )
            raw_before = raw.read_text(encoding="utf-8")
            converted_before = converted.read_text(encoding="utf-8")
            curated_before = curated.read_text(encoding="utf-8")

            review_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "patches",
                    "review",
                    "--project",
                    str(project),
                    "--patch",
                    "normality_ocr_notes_patch_001",
                    "--decision",
                    "accepted",
                    "--note",
                    "Verified against the converted source.",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            list_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "patches",
                    "list",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            status_result = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(review_result.returncode, 0, review_result.stderr)
            self.assertIn(
                "Reviewed correction patch normality_ocr_notes_patch_001: accepted",
                review_result.stdout,
            )
            patch = (
                project
                / "01_references"
                / "converted"
                / "patches"
                / "normality_ocr_notes_patch_001.patch.md"
            )
            patch_text = patch.read_text(encoding="utf-8")
            self.assertIn("### Review Decision\n\n- decision: accepted", patch_text)
            self.assertIn("- note: Verified against the converted source.", patch_text)
            self.assertIn(
                "- normality_ocr_notes_patch_001 | accepted | normality_ocr_notes | low |",
                list_result.stdout,
            )
            self.assertIn("Correction patches: 1", status_result.stdout)
            self.assertIn("Pending correction patches: 0", status_result.stdout)
            self.assertEqual(raw.read_text(encoding="utf-8"), raw_before)
            self.assertEqual(converted.read_text(encoding="utf-8"), converted_before)
            self.assertEqual(curated.read_text(encoding="utf-8"), curated_before)

    def test_patches_apply_replaces_accepted_correction_in_curated_reference_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "project"))
            source = root / "normal_subgroups.md"
            source.write_text(
                "### Definition: Normal Subgroup\n"
                "Let G he a group. A subgroup N is normal when gNg^{-1}=N.\n",
                encoding="utf-8",
                newline="\n",
            )
            record = import_reference(
                project,
                source,
                role="lecture_notes",
                title="Normality OCR Notes",
            )
            curated = curate_reference(project, record.id)
            kb_result = build_reference_kb(project)
            raw = project / "01_references" / "raw" / "markdown" / "normal_subgroups.md"
            converted = (
                project
                / "01_references"
                / "converted"
                / "markdown"
                / "normality_ocr_notes.md"
            )
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "patch",
                    "--project",
                    str(project),
                    "--source-id",
                    record.id,
                    "--location",
                    "Definition paragraph 1",
                    "--original",
                    "Let G he a group.",
                    "--proposed-correction",
                    "Let G be a group.",
                    "--reason",
                    "OCR likely misread be as he.",
                    "--risk-level",
                    "low",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=True,
            )
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "patches",
                    "review",
                    "--project",
                    str(project),
                    "--patch",
                    "normality_ocr_notes_patch_001",
                    "--decision",
                    "accepted",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=True,
            )
            raw_before = raw.read_text(encoding="utf-8")
            converted_before = converted.read_text(encoding="utf-8")

            apply_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "patches",
                    "apply",
                    "--project",
                    str(project),
                    "--patch",
                    "normality_ocr_notes_patch_001",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            index_time_ns = kb_result.index_path.stat().st_mtime_ns
            os.utime(
                curated,
                ns=(index_time_ns + 1_000_000_000, index_time_ns + 1_000_000_000),
            )
            list_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "patches",
                    "list",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            status_result = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            search_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "kb",
                    "search",
                    "--project",
                    str(project),
                    "--query",
                    "Let G",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(apply_result.returncode, 0, apply_result.stderr)
            self.assertIn(
                "Applied correction patch normality_ocr_notes_patch_001",
                apply_result.stdout,
            )
            curated_text = curated.read_text(encoding="utf-8")
            self.assertIn("Let G be a group.", curated_text)
            self.assertNotIn("Let G he a group.", curated_text)
            self.assertEqual(raw.read_text(encoding="utf-8"), raw_before)
            self.assertEqual(converted.read_text(encoding="utf-8"), converted_before)
            patch = (
                project
                / "01_references"
                / "converted"
                / "patches"
                / "normality_ocr_notes_patch_001.patch.md"
            )
            patch_text = patch.read_text(encoding="utf-8")
            self.assertIn("### Apply Result\n\n- status: applied", patch_text)
            self.assertIn(
                "- target: 01_references/curated/normality_ocr_notes.curated.md",
                patch_text,
            )
            self.assertIn(
                "- normality_ocr_notes_patch_001 | applied | normality_ocr_notes | low |",
                list_result.stdout,
            )
            self.assertEqual(status_result.returncode, 0, status_result.stderr)
            self.assertIn("Reference KB status: stale", status_result.stdout)
            self.assertEqual(search_result.returncode, 0, search_result.stderr)
            self.assertIn("warning: Reference KB status is stale", search_result.stderr)
            self.assertIn("socrates kb build --project", search_result.stderr)

    def test_patches_apply_rejects_unaccepted_patch_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "project"))
            source = root / "normal_subgroups.md"
            source.write_text(
                "### Definition: Normal Subgroup\n"
                "Let G he a group. A subgroup N is normal when gNg^{-1}=N.\n",
                encoding="utf-8",
                newline="\n",
            )
            record = import_reference(
                project,
                source,
                role="lecture_notes",
                title="Normality OCR Notes",
            )
            curated = curate_reference(project, record.id)
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "patch",
                    "--project",
                    str(project),
                    "--source-id",
                    record.id,
                    "--location",
                    "Definition paragraph 1",
                    "--original",
                    "Let G he a group.",
                    "--proposed-correction",
                    "Let G be a group.",
                    "--reason",
                    "OCR likely misread be as he.",
                    "--risk-level",
                    "low",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=True,
            )
            curated_before = curated.read_text(encoding="utf-8")

            apply_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "patches",
                    "apply",
                    "--project",
                    str(project),
                    "--patch",
                    "normality_ocr_notes_patch_001",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(apply_result.returncode, 1)
            self.assertEqual(apply_result.stdout, "")
            self.assertIn(
                "error: Correction patch normality_ocr_notes_patch_001 must be accepted before apply",
                apply_result.stderr,
            )
            self.assertNotIn("Traceback", apply_result.stderr)
            self.assertEqual(curated.read_text(encoding="utf-8"), curated_before)


if __name__ == "__main__":
    unittest.main()
