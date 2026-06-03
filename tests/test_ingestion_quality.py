from __future__ import annotations

import json
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
                "## Source Metadata\n"
                "- source_id: normality_notes\n"
                "- title: Normality Notes\n"
                "- role: lecture_notes\n"
                "- raw_path: 01_references/raw/markdown/normality.md\n"
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
            self.assertIn("Ingestion quality manifest:", result.stdout)
            report = project / "08_evals" / "ingestion_eval.md"
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("# Ingestion Eval", report_text)
            self.assertIn("## Summary", report_text)
            self.assertIn("- Curated files checked: 1", report_text)
            self.assertIn("- Extractable objects: 1", report_text)
            self.assertIn("normal_subgroups.curated.md: pass", report_text)
            manifest = json.loads(
                (project / "08_evals" / "ingestion_quality_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual(manifest["checked"], 1)
            self.assertEqual(manifest["passed"], 1)
            self.assertEqual(manifest["failed"], 0)
            self.assertEqual(manifest["extractable_objects"], 1)
            self.assertEqual(manifest["raw_references_modified"], False)
            self.assertEqual(manifest["curated_only_policy"], "enforced")
            reference = manifest["curated_references"][0]
            self.assertEqual(reference["file"], "normal_subgroups.curated.md")
            self.assertEqual(
                reference["path"],
                "01_references/curated/normal_subgroups.curated.md",
            )
            self.assertEqual(reference["quality_status"], "pass")
            self.assertEqual(reference["source_metadata"]["source_id"], "normality_notes")
            self.assertEqual(reference["source_metadata"]["role"], "lecture_notes")
            self.assertEqual(reference["extractable_object_count"], 1)
            self.assertEqual(reference["has_dependency_metadata"], True)
            self.assertEqual(
                reference["objects"][0],
                {
                    "line": 8,
                    "type": "definition",
                    "title": "Normal Subgroup",
                    "dependencies": ["subgroup", "conjugation"],
                },
            )

    def test_kb_check_accepts_numbered_math_object_headings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "numbered.curated.md"
            curated.write_text(
                "# Group Theory\n"
                "## Source Metadata\n"
                "- source_id: numbered_notes\n"
                "- title: Numbered Notes\n"
                "- role: lecture_notes\n"
                "## Normal Subgroups\n"
                "### Definition 3.1: Normal Subgroup\n"
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
            report_text = (project / "08_evals" / "ingestion_eval.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("- Extractable objects: 1", report_text)
            self.assertIn("numbered.curated.md: pass", report_text)
            manifest = json.loads(
                (project / "08_evals" / "ingestion_quality_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                manifest["curated_references"][0]["objects"][0]["number"],
                "3.1",
            )

    def test_kb_check_requires_source_id_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "missing_source.curated.md"
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
            self.assertIn("Checked 1 curated reference: 0 passed, 1 failed", result.stdout)
            report_text = (project / "08_evals" / "ingestion_eval.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("missing_source.curated.md: fail", report_text)
            self.assertIn("missing source id metadata", report_text)
            manifest = json.loads(
                (project / "08_evals" / "ingestion_quality_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            reference = manifest["curated_references"][0]
            self.assertEqual(reference["quality_status"], "fail")
            self.assertIn("missing source id metadata", reference["issues"])


if __name__ == "__main__":
    unittest.main()
