from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from socrates.project import ProjectSpec, create_project


REPO_ROOT = Path(__file__).resolve().parents[1]


class IngestionQualityTests(unittest.TestCase):
    def test_kb_check_cli_writes_ingestion_quality_report_for_curated_references(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "normal_subgroups.curated.md"
            curated.write_text(
                "# Group Theory\n"
                "## Normal Subgroups\n"
                "### Definition: Normal Subgroup\n"
                "A normal subgroup is stable under conjugation.\n"
                "Depends: subgroup, conjugation\n",
                encoding="utf-8",
                newline="\n",
            )

            result = subprocess.run(
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

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Checked 1 curated reference: 1 passed, 0 failed", result.stdout)
            report = project / "08_evals" / "ingestion_eval.md"
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("# Ingestion Eval", report_text)
            self.assertIn("## Summary", report_text)
            self.assertIn("- Curated files checked: 1", report_text)
            self.assertIn("- Extractable objects: 1", report_text)
            self.assertIn("normal_subgroups.curated.md: pass", report_text)


if __name__ == "__main__":
    unittest.main()
