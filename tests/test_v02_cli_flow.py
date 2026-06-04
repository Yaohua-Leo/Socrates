from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from socrates.artifacts import generate_atomic_note_draft
from socrates.project import ProjectSpec, create_project


REPO_ROOT = Path(__file__).resolve().parents[1]


class V02CliFlowTests(unittest.TestCase):
    def test_reference_kb_and_obsidian_review_flow_from_cli(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "normal_subgroups.curated.md"
            curated.write_text(
                "### Definition: Normal Subgroup\n"
                "A normal subgroup is stable under conjugation.\n"
                "Depends: subgroup, conjugation\n",
                encoding="utf-8",
            )
            generate_atomic_note_draft(
                project,
                concept="Normal Subgroup",
                note_type="definition",
                body=(
                    "A normal subgroup is stable under conjugation; compare [[Subgroup]].\n\n"
                    "## Review Questions\n\n"
                    "- What conjugation condition must be checked?\n"
                ),
                source_id="df",
            )

            build_result = self._run_cli("kb", "build", "--project", str(project))
            search_result = self._run_cli(
                "kb",
                "search",
                "--project",
                str(project),
                "--query",
                "conjugation",
            )
            review_result = self._run_cli(
                "note",
                "review",
                "--project",
                str(project),
                "--note",
                "normal_subgroup",
            )
            export_result = self._run_cli("note", "export-obsidian", "--project", str(project))

            self.assertIn("Indexed 1 reference object", build_result.stdout)
            self.assertIn("Concept graph: 3 nodes, 2 edges", build_result.stdout)
            self.assertIn("Dependency graph: 3 nodes, 2 edges", build_result.stdout)
            self.assertIn("Normal Subgroup", search_result.stdout)
            self.assertIn("definition", search_result.stdout)
            self.assertIn("normal_subgroups.curated.md:1", search_result.stdout)
            self.assertIn("Reviewed note normal_subgroup", review_result.stdout)
            self.assertIn("Exported 1 reviewed note", export_result.stdout)
            self.assertTrue((project / "06_kb" / "chunks" / "reference_index.json").exists())
            self.assertTrue((project / "07_exports" / "obsidian" / "normal_subgroup.md").exists())

    def test_kb_search_displays_page_provenance_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "normality.curated.md"
            curated.write_text(
                "### Definition 3.1: Normal Subgroup\n"
                "Page: 82\n"
                "A normal subgroup is stable under conjugation.\n"
                "Depends: subgroup, conjugation\n",
                encoding="utf-8",
            )

            self._run_cli("kb", "build", "--project", str(project))
            search = self._run_cli(
                "kb",
                "search",
                "--project",
                str(project),
                "--query",
                "conjugation",
            ).stdout

            self.assertIn("definition 3.1: Normal Subgroup", search)
            self.assertIn("normality.curated.md:p82:1", search)

    def test_kb_search_filters_by_reference_object_type(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "normality.curated.md"
            curated.write_text(
                "### Definition: Normal Subgroup\n"
                "A normal subgroup is stable under conjugation.\n\n"
                "### Theorem: Kernel Normality\n"
                "The kernel of a homomorphism is normal by conjugation.\n",
                encoding="utf-8",
                newline="\n",
            )

            self._run_cli("kb", "build", "--project", str(project))
            search = self._run_cli(
                "kb",
                "search",
                "--project",
                str(project),
                "--query",
                "normal",
                "--type",
                "theorem",
            ).stdout

            self.assertIn("theorem: Kernel Normality", search)
            self.assertNotIn("definition: Normal Subgroup", search)

    def test_kb_search_filters_by_source_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "normality.curated.md"
            curated.write_text(
                "## Source Metadata\n\n"
                "- source_id: normality_notes\n"
                "- title: Normality Notes\n\n"
                "### Definition: Normal Subgroup\n"
                "A normal subgroup is stable under conjugation.\n",
                encoding="utf-8",
                newline="\n",
            )
            exercises = project / "01_references" / "curated" / "exercises.curated.md"
            exercises.write_text(
                "## Source Metadata\n\n"
                "- source_id: exercise_notes\n"
                "- title: Exercise Notes\n\n"
                "### Exercise: Test Normality\n"
                "Decide whether the given subgroup is normal.\n",
                encoding="utf-8",
                newline="\n",
            )

            self._run_cli("kb", "build", "--project", str(project))
            search = self._run_cli(
                "kb",
                "search",
                "--project",
                str(project),
                "--query",
                "normal",
                "--source-id",
                "exercise_notes",
            ).stdout

            self.assertIn("exercise: Test Normality", search)
            self.assertIn("Exercise Notes [exercise_notes]", search)
            self.assertNotIn("definition: Normal Subgroup", search)
            self.assertNotIn("Normality Notes", search)

    def test_kb_search_filters_by_explicit_relationship_type(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "relations.curated.md"
            curated.write_text(
                "### Example: Alternating Group In S3\n"
                "A3 is normal in S3.\n"
                "Example of: normal subgroup\n\n"
                "### Counterexample: Transposition Subgroup\n"
                "A transposition subgroup is not normal in S3.\n"
                "Counterexample to: normal subgroup\n",
                encoding="utf-8",
                newline="\n",
            )

            self._run_cli("kb", "build", "--project", str(project))
            search = self._run_cli(
                "kb",
                "search",
                "--project",
                str(project),
                "--query",
                "normal subgroup",
                "--relationship-type",
                "example_of",
            ).stdout

            self.assertIn("example: Alternating Group In S3", search)
            self.assertNotIn("counterexample: Transposition Subgroup", search)

    def test_kb_list_displays_indexed_objects_and_filters(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "normality.curated.md"
            curated.write_text(
                "# Curated Reference: Normality Notes\n\n"
                "## Source Metadata\n\n"
                "- source_id: normality_notes\n"
                "- title: Normality Notes\n"
                "- role: lecture_notes\n"
                "- raw_path: 01_references/raw/markdown/normality.md\n\n"
                "# Chapter 3: Quotient Groups\n"
                "## Section 3.1 Normal Subgroups\n"
                "### Definition 3.1: Normal Subgroup\n"
                "Page: 82\n"
                "A normal subgroup is stable under conjugation.\n"
                "Depends: subgroup, conjugation\n\n"
                "### Theorem 3.2: Kernel Normality\n"
                "The kernel of a group homomorphism is normal.\n"
                "Depends: kernel, homomorphism\n",
                encoding="utf-8",
                newline="\n",
            )
            exercises = project / "01_references" / "curated" / "exercises.curated.md"
            exercises.write_text(
                "## Source Metadata\n\n"
                "- source_id: exercise_notes\n"
                "- title: Exercise Notes\n"
                "- role: exercise_source\n\n"
                "### Exercise: Construct A Non-Normal Subgroup\n"
                "Find a subgroup of S3 that is not normal.\n"
                "Depends: normal subgroup, symmetric group\n",
                encoding="utf-8",
                newline="\n",
            )

            self._run_cli("kb", "build", "--project", str(project))
            all_objects = self._run_cli("kb", "list", "--project", str(project)).stdout
            theorem_objects = self._run_cli(
                "kb",
                "list",
                "--project",
                str(project),
                "--type",
                "theorem",
            ).stdout
            exercise_source_objects = self._run_cli(
                "kb",
                "list",
                "--project",
                str(project),
                "--source-id",
                "exercise_notes",
            ).stdout
            missing_source_objects = self._run_cli(
                "kb",
                "list",
                "--project",
                str(project),
                "--source-id",
                "missing_source",
            ).stdout

            self.assertIn("# Reference KB Objects", all_objects)
            self.assertIn("definition 3.1: Normal Subgroup", all_objects)
            self.assertIn("theorem 3.2: Kernel Normality", all_objects)
            self.assertIn("exercise: Construct A Non-Normal Subgroup", all_objects)
            self.assertIn("Normality Notes (lecture_notes) [normality_notes]", all_objects)
            self.assertIn("normality.curated.md:p82", all_objects)

            self.assertIn("theorem 3.2: Kernel Normality", theorem_objects)
            self.assertNotIn("definition 3.1: Normal Subgroup", theorem_objects)
            self.assertNotIn("Construct A Non-Normal Subgroup", theorem_objects)

            self.assertIn("exercise: Construct A Non-Normal Subgroup", exercise_source_objects)
            self.assertIn(
                "Exercise Notes (exercise_source) [exercise_notes]",
                exercise_source_objects,
            )
            self.assertNotIn("Kernel Normality", exercise_source_objects)

            self.assertIn("- none", missing_source_objects)

    def test_kb_chapters_displays_chapter_section_and_object_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "normality.curated.md"
            curated.write_text(
                "# Curated Reference: Normality Notes\n\n"
                "## Source Metadata\n\n"
                "- source_id: normality_notes\n"
                "- title: Normality Notes\n"
                "- role: lecture_notes\n\n"
                "# Chapter 3: Quotient Groups\n"
                "## Section 3.1 Normal Subgroups\n"
                "### Definition 3.1: Normal Subgroup\n"
                "Page: 82\n"
                "A normal subgroup is stable under conjugation.\n"
                "Depends: subgroup, conjugation\n\n"
                "### Theorem 3.2: Kernel Normality\n"
                "The kernel of a group homomorphism is normal.\n"
                "Depends: kernel, homomorphism\n",
                encoding="utf-8",
                newline="\n",
            )

            self._run_cli("kb", "build", "--project", str(project))
            chapters = self._run_cli("kb", "chapters", "--project", str(project)).stdout

            self.assertIn("# Reference KB Chapters", chapters)
            self.assertIn("## Chapter 3: Quotient Groups", chapters)
            self.assertIn(
                "- Section 3.1 Normal Subgroups | 01_references/curated/normality.curated.md",
                chapters,
            )
            self.assertIn(
                "  - definition 3.1: Normal Subgroup | "
                "01_references/curated/normality.curated.md:p82:11",
                chapters,
            )
            self.assertIn(
                "  - theorem 3.2: Kernel Normality | "
                "01_references/curated/normality.curated.md:16",
                chapters,
            )

    def test_kb_chapters_reports_missing_index_with_rebuild_hint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "kb",
                    "chapters",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("Reference KB chapter index is missing", result.stderr)
            self.assertIn("socrates kb build --project", result.stderr)
            self.assertNotIn("No such file or directory", result.stderr)

    def test_kb_list_reports_invalid_index_with_rebuild_hint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            index_path = project / "06_kb" / "chunks" / "reference_index.json"
            index_path.write_text("{not valid json\n", encoding="utf-8", newline="\n")

            result = subprocess.run(
                [sys.executable, "-m", "socrates", "kb", "list", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("Reference KB index is invalid", result.stderr)
            self.assertIn("socrates kb build --project", result.stderr)
            self.assertNotIn("Expecting property name", result.stderr)

    def test_kb_search_reports_invalid_index_with_rebuild_hint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            index_path = project / "06_kb" / "chunks" / "reference_index.json"
            index_path.write_text("{not valid json\n", encoding="utf-8", newline="\n")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "kb",
                    "search",
                    "--project",
                    str(project),
                    "--query",
                    "normal",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("Reference KB index is invalid", result.stderr)
            self.assertIn("socrates kb build --project", result.stderr)
            self.assertNotIn("Expecting property name", result.stderr)

    def test_kb_counterexamples_reports_invalid_index_with_rebuild_hint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            index_path = project / "06_kb" / "chunks" / "reference_index.json"
            index_path.write_text("{not valid json\n", encoding="utf-8", newline="\n")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "kb",
                    "counterexamples",
                    "--project",
                    str(project),
                    "--concept",
                    "normal subgroup",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("Reference KB index is invalid", result.stderr)
            self.assertIn("socrates kb build --project", result.stderr)
            self.assertNotIn("Expecting property name", result.stderr)

    def test_kb_counterexamples_lists_matching_reference_counterexamples(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "counterexamples.curated.md"
            curated.write_text(
                "### Definition: Normal Subgroup\n"
                "A normal subgroup is stable under conjugation.\n"
                "Depends: subgroup, conjugation\n"
                "### Counterexample: Subgroup That Is Not Normal\n"
                "In S3, a subgroup generated by a transposition is not normal.\n"
                "Depends: normal subgroup, conjugation\n",
                encoding="utf-8",
            )

            self._run_cli("kb", "build", "--project", str(project))
            result = self._run_cli(
                "kb",
                "counterexamples",
                "--project",
                str(project),
                "--concept",
                "normal subgroup",
            )

            self.assertIn("counterexample: Subgroup That Is Not Normal", result.stdout)
            self.assertIn("counterexamples.curated.md:4", result.stdout)

    def test_kb_relationships_lists_and_filters_concept_graph_edges(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "relations.curated.md"
            curated.write_text(
                "### Definition: Normal Subgroup\n"
                "A normal subgroup is stable under conjugation.\n"
                "Depends: subgroup, conjugation\n\n"
                "### Theorem: Kernel Normality\n"
                "The kernel of a group homomorphism is normal.\n"
                "Depends: kernel, group homomorphism\n\n"
                "### Example: Alternating Group In S3\n"
                "The alternating group A3 is normal in S3.\n"
                "Example of: normal subgroup\n\n"
                "### Counterexample: Transposition Subgroup\n"
                "A subgroup generated by a transposition in S3 is not normal.\n"
                "Counterexample to: normal subgroup\n\n"
                "### Proof: Kernel Normality Proof\n"
                "Use homomorphism fibers to show conjugation stability.\n"
                "Proof of: Kernel Normality\n",
                encoding="utf-8",
                newline="\n",
            )

            self._run_cli("kb", "build", "--project", str(project))
            all_relationships = self._run_cli(
                "kb",
                "relationships",
                "--project",
                str(project),
            ).stdout
            examples = self._run_cli(
                "kb",
                "relationships",
                "--project",
                str(project),
                "--type",
                "example_of",
            ).stdout

            self.assertIn("# Reference KB Relationships", all_relationships)
            self.assertIn("- alternating_group_in_s3 --example_of--> normal_subgroup", all_relationships)
            self.assertIn(
                "- transposition_subgroup --counterexample_to--> normal_subgroup",
                all_relationships,
            )
            self.assertIn(
                "- kernel_normality_proof --used_in_proof_of--> kernel_normality",
                all_relationships,
            )
            self.assertIn("- alternating_group_in_s3 --example_of--> normal_subgroup", examples)
            self.assertNotIn("counterexample_to", examples)

    def test_import_curate_kb_plan_teach_review_export_flow_from_cli(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "group_theory"
            reference = root / "normal_subgroups.md"
            reference.write_text(
                "### Definition: Normal Subgroup\n"
                "A normal subgroup is stable under conjugation.\n"
                "Depends: subgroup, conjugation\n",
                encoding="utf-8",
                newline="\n",
            )
            script = root / "session.script"
            script.write_text(
                "topic: Normal Subgroup\n"
                "question: What must you check to prove a subgroup is normal?\n"
                "hint: Use conjugation rather than elementwise commutativity.\n"
                "prerequisite: subgroup\n"
                "attempt: I think normal means every element commutes.\n"
                "misconception: normal_equals_abelian\n"
                "next: Compare normality with commutativity using conjugation.\n",
                encoding="utf-8",
                newline="\n",
            )

            self._run_cli(
                "init",
                "--topic",
                "Normal Subgroup",
                "--path",
                str(project),
                "--goal",
                "Prepare for quotient groups.",
            )
            self._run_cli(
                "import",
                "--project",
                str(project),
                str(reference),
                "--role",
                "lecture_notes",
                "--title",
                "Normal Subgroup Notes",
            )
            self._run_cli(
                "curate",
                "--project",
                str(project),
                "--source-id",
                "normal_subgroup_notes",
            )
            self._run_cli("kb", "build", "--project", str(project))
            search = self._run_cli(
                "kb",
                "search",
                "--project",
                str(project),
                "--query",
                "conjugation",
            ).stdout
            self._run_cli("plan", "--project", str(project))
            self._run_cli(
                "teach",
                "--project",
                str(project),
                "--session-id",
                "session_0001",
                "--script",
                str(script),
            )
            self._run_cli(
                "note",
                "review",
                "--project",
                str(project),
                "--note",
                "normal_subgroup",
            )
            self._run_cli("note", "export-obsidian", "--project", str(project))

            status = self._run_cli("status", "--project", str(project)).stdout
            session_plan = (project / "02_learning_plan" / "session_0001_plan.md").read_text(
                encoding="utf-8"
            )
            exported = project / "07_exports" / "obsidian" / "normal_subgroup.md"

            self.assertIn("Definition: Normal Subgroup", session_plan)
            self.assertIn("Source: 01_references/curated/normal_subgroup_notes.curated.md", session_plan)
            self.assertIn(
                "Normal Subgroup Notes (lecture_notes) [normal_subgroup_notes]",
                search,
            )
            self.assertIn("[normal_subgroup_notes]", search)
            self.assertTrue((project / "06_kb" / "theorem_index.json").exists())
            self.assertTrue((project / "06_kb" / "exercise_index.json").exists())
            self.assertTrue(exported.exists())
            self.assertIn("Current phase: obsidian_exported", status)
            self.assertIn("Converted references: 1", status)
            self.assertIn("Curated references: 1", status)
            self.assertIn("KB objects: 1", status)
            self.assertIn("Reviewed notes: 1", status)
            self.assertIn("Obsidian exports: 1", status)

    def _run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, "-m", "socrates", *args],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result


if __name__ == "__main__":
    unittest.main()
