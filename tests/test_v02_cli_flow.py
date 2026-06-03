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
                body="A normal subgroup is stable under conjugation.",
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
            self.assertIn("Reviewed note normal_subgroup", review_result.stdout)
            self.assertIn("Exported 1 reviewed note", export_result.stdout)
            self.assertTrue((project / "06_kb" / "chunks" / "reference_index.json").exists())
            self.assertTrue((project / "07_exports" / "obsidian" / "normal_subgroup.md").exists())

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
