from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from socrates.artifacts import generate_atomic_note_draft
from socrates.kb import build_reference_kb
from socrates.project import ProjectSpec, create_project


REPO_ROOT = Path(__file__).resolve().parents[1]


class NoteQualityTests(unittest.TestCase):
    def test_note_check_cli_writes_quality_report_for_atomic_notes(self) -> None:
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
                    "- How is normality different from commutativity?\n"
                ),
                source_id="df-1",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "note",
                    "check",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Checked 1 atomic note: 1 passed, 0 failed", result.stdout)
            report = project / "08_evals" / "note_quality_eval.md"
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("# Note Quality Eval", report_text)
            self.assertIn("## Summary", report_text)
            self.assertIn("- Notes checked: 1", report_text)
            self.assertIn("- Passed: 1", report_text)
            self.assertIn("- Failed: 0", report_text)
            self.assertIn("drafts/normal_subgroup.md: pass", report_text)


if __name__ == "__main__":
    unittest.main()
