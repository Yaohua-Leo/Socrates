from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from socrates.kb import build_reference_kb
from socrates.project import ProjectSpec, create_project


REPO_ROOT = Path(__file__).resolve().parents[1]


class ToolVerificationTests(unittest.TestCase):
    def test_lean_skeleton_cli_writes_unchecked_tool_verification_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "p"))
            curated = project / "01_references" / "curated" / "kernel.curated.md"
            curated.write_text(
                "# Homomorphisms\n\n"
                "## Kernels\n\n"
                "### Theorem 3.2: Kernel Normality\n"
                "Page: 83\n"
                "The kernel of a group homomorphism is a normal subgroup.\n"
                "Depends: kernel, normal_subgroup, homomorphism\n",
                encoding="utf-8",
                newline="\n",
            )
            build_reference_kb(project)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "tool",
                    "lean-skeleton",
                    "--project",
                    str(project),
                    "--object-id",
                    "kernel_normality",
                    "--namespace",
                    "Socrates.GroupTheory",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Wrote Lean skeleton:", result.stdout)
            self.assertIn("Status: unchecked_skeleton", result.stdout)
            list_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "tool",
                    "list",
                    "--project",
                    str(project),
                    "--status",
                    "unchecked_skeleton",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            verification_dir = project / "08_evals" / "tool_verification"
            skeleton = verification_dir / "kernel_normality_statement.lean"
            report = verification_dir / "kernel_normality_statement_report.md"
            manifest_path = verification_dir / "manifest.json"
            skeleton_text = skeleton.read_text(encoding="utf-8")
            self.assertIn("namespace Socrates.GroupTheory", skeleton_text)
            self.assertIn("theorem kernel_normality_statement : Prop := by", skeleton_text)
            self.assertIn("-- The kernel of a group homomorphism is a normal subgroup.", skeleton_text)
            self.assertIn("  sorry", skeleton_text)
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("# Tool Verification: Lean Statement Skeleton", report_text)
            self.assertIn("- Status: unchecked_skeleton", report_text)
            self.assertIn("- No Lean executable was invoked.", report_text)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual(len(manifest["records"]), 1)
            record = manifest["records"][0]
            self.assertEqual(record["kind"], "lean_statement_skeleton")
            self.assertEqual(record["object_id"], "kernel_normality")
            self.assertEqual(record["status"], "unchecked_skeleton")
            self.assertEqual(
                record["skeleton_path"],
                "08_evals/tool_verification/kernel_normality_statement.lean",
            )
            self.assertEqual(record["source"]["page"], "83")
            self.assertEqual(list_result.returncode, 0, list_result.stderr)
            self.assertIn("# Tool Verification Records", list_result.stdout)
            self.assertIn(
                "- kernel_normality | unchecked_skeleton | lean_statement_skeleton | "
                "Kernel Normality | 08_evals/tool_verification/kernel_normality_statement.lean",
                list_result.stdout,
            )
            self.assertIn(
                "  - report: 08_evals/tool_verification/kernel_normality_statement_report.md",
                list_result.stdout,
            )

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Tool verification records: 1", status.stdout)


if __name__ == "__main__":
    unittest.main()
