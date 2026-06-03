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
    def test_tool_inventory_cli_records_local_optional_tool_availability(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "p"))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "tool",
                    "inventory",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Tool inventory status:", result.stdout)
            self.assertIn("Tools available:", result.stdout)
            verification_dir = project / "08_evals" / "tool_verification"
            inventory_report = verification_dir / "tool_inventory_report.md"
            inventory_manifest = verification_dir / "tool_inventory_manifest.json"
            registry_manifest = verification_dir / "manifest.json"
            report_text = inventory_report.read_text(encoding="utf-8")
            self.assertIn("# Tool Inventory", report_text)
            self.assertIn("- External verifier invoked: false", report_text)
            self.assertIn("- No external verifier executable was invoked.", report_text)
            manifest = json.loads(inventory_manifest.read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema_version"], 1)
            self.assertIn(manifest["status"], {"available", "partial", "unavailable"})
            self.assertEqual(manifest["external_verifier_invoked"], False)
            tool_ids = {tool["id"] for tool in manifest["tools"]}
            self.assertEqual(tool_ids, {"lean", "lake", "sage", "gap", "sympy"})
            registry = json.loads(registry_manifest.read_text(encoding="utf-8"))
            record = registry["records"][0]
            self.assertEqual(record["kind"], "tool_inventory")
            self.assertEqual(record["object_id"], "local_tool_inventory")
            self.assertEqual(
                record["artifact_path"],
                "08_evals/tool_verification/tool_inventory_manifest.json",
            )
            self.assertEqual(
                record["report_path"],
                "08_evals/tool_verification/tool_inventory_report.md",
            )

            list_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "tool",
                    "list",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(list_result.returncode, 0, list_result.stderr)
            self.assertIn("local_tool_inventory", list_result.stdout)
            self.assertIn("tool_inventory", list_result.stdout)

            check_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "tool",
                    "check",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(check_result.returncode, 0, check_result.stderr)
            self.assertIn(
                "Checked 1 tool-verification record: 1 passed, 0 failed",
                check_result.stdout,
            )

    def test_lean_skeleton_cli_writes_unchecked_tool_verification_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = _project_with_kernel_reference(root / "p")

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

    def test_tool_check_cli_writes_quality_report_for_persisted_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = _project_with_kernel_reference(root / "p")
            subprocess.run(
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
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=True,
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "tool",
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
            self.assertIn(
                "Checked 1 tool-verification record: 1 passed, 0 failed",
                result.stdout,
            )
            self.assertIn("Tool verification eval report:", result.stdout)
            self.assertIn("Tool verification quality manifest:", result.stdout)
            report_text = (project / "08_evals" / "tool_verification_eval.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("- Status: pass", report_text)
            self.assertIn(
                "- `unchecked_skeleton` records are scaffolds, not verified proofs.",
                report_text,
            )
            self.assertIn("- No external verifier executable was invoked.", report_text)
            manifest = json.loads(
                (project / "08_evals" / "tool_verification_quality_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual(manifest["status"], "pass")
            self.assertEqual(manifest["checked"], 1)
            self.assertEqual(manifest["passed"], 1)
            self.assertEqual(manifest["failed"], 0)
            self.assertEqual(
                manifest["source_manifest"],
                "08_evals/tool_verification/manifest.json",
            )
            record = manifest["records"][0]
            self.assertEqual(record["object_id"], "kernel_normality")
            self.assertEqual(record["record_status"], "unchecked_skeleton")
            self.assertEqual(record["quality_status"], "pass")
            self.assertEqual(
                manifest["verification_boundary"]["external_verifier_invoked"],
                False,
            )
            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn(
                "Tool verification check: pass (1/1 passed, 0 failed)",
                status.stdout,
            )

    def test_tool_check_cli_fails_for_missing_persisted_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "p"))
            verification_dir = project / "08_evals" / "tool_verification"
            verification_dir.mkdir(parents=True, exist_ok=True)
            (verification_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "records": [
                            {
                                "kind": "lean_statement_skeleton",
                                "object_id": "missing_kernel",
                                "status": "unchecked_skeleton",
                                "skeleton_path": (
                                    "08_evals/tool_verification/missing_kernel.lean"
                                ),
                                "report_path": (
                                    "08_evals/tool_verification/missing_kernel_report.md"
                                ),
                            }
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "tool",
                    "check",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn(
                "Checked 1 tool-verification record: 0 passed, 1 failed",
                result.stdout,
            )
            report_text = (project / "08_evals" / "tool_verification_eval.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("- Status: fail", report_text)
            self.assertIn(
                "missing artifact: 08_evals/tool_verification/missing_kernel.lean",
                report_text,
            )
            self.assertIn(
                "missing report: 08_evals/tool_verification/missing_kernel_report.md",
                report_text,
            )
            manifest = json.loads(
                (project / "08_evals" / "tool_verification_quality_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(manifest["status"], "fail")
            self.assertEqual(manifest["checked"], 1)
            self.assertEqual(manifest["passed"], 0)
            self.assertEqual(manifest["failed"], 1)
            self.assertEqual(manifest["records"][0]["quality_status"], "fail")


def _project_with_kernel_reference(path: Path) -> Path:
    project = create_project(ProjectSpec(topic="Group Theory", path=path))
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
    return project


if __name__ == "__main__":
    unittest.main()
