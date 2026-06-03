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
                    "A normal subgroup is stable under conjugation.\n\n"
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
            self.assertIn("[normal_subgroup_notes]", search)
            self.assertTrue((project / "06_kb" / "theorem_index.json").exists())
            self.assertTrue((project / "06_kb" / "exercise_index.json").exists())
            self.assertTrue(exported.exists())
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
