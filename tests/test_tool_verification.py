from __future__ import annotations

import hashlib
import json
import os
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

    def test_sympy_identity_cli_persists_computation_result_or_unavailable_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "p"))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "tool",
                    "sympy-identity",
                    "--project",
                    str(project),
                    "--object-id",
                    "square_expansion",
                    "--lhs",
                    "(x + 1)^2",
                    "--rhs",
                    "x^2 + 2*x + 1",
                    "--title",
                    "Square Expansion",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            verification_dir = project / "08_evals" / "tool_verification"
            artifact_path = verification_dir / "square_expansion_sympy_identity.json"
            report_path = verification_dir / "square_expansion_sympy_identity_report.md"
            manifest_path = verification_dir / "manifest.json"
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            expected_returncode = 0 if artifact["status"] == "verified" else 1
            self.assertEqual(result.returncode, expected_returncode, result.stderr)
            self.assertIn("SymPy identity status:", result.stdout)
            self.assertEqual(artifact["schema_version"], 1)
            self.assertEqual(artifact["kind"], "sympy_identity_check")
            self.assertEqual(artifact["object_id"], "square_expansion")
            self.assertEqual(artifact["input"]["lhs"], "(x + 1)^2")
            self.assertEqual(artifact["input"]["rhs"], "x^2 + 2*x + 1")
            self.assertEqual(artifact["subprocess_invoked"], False)
            self.assertIn(artifact["status"], {"verified", "failed", "unavailable"})
            if artifact["status"] == "verified":
                self.assertEqual(artifact["passed"], True)
                self.assertEqual(artifact["output"]["simplified_difference"], "0")
            else:
                self.assertEqual(artifact["passed"], False)
                self.assertGreaterEqual(len(artifact["issues"]), 1)
            report_text = report_path.read_text(encoding="utf-8")
            self.assertIn("# Tool Verification: SymPy Identity Check", report_text)
            self.assertIn("- It is computation evidence, not a formal proof.", report_text)
            self.assertIn("- No external executable or shell subprocess was invoked.", report_text)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            record = manifest["records"][0]
            self.assertEqual(record["kind"], "sympy_identity_check")
            self.assertEqual(record["object_id"], "square_expansion")
            self.assertEqual(
                record["artifact_path"],
                "08_evals/tool_verification/square_expansion_sympy_identity.json",
            )
            self.assertEqual(
                record["report_path"],
                "08_evals/tool_verification/square_expansion_sympy_identity_report.md",
            )

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

    def test_sympy_counterexample_cli_persists_found_or_unavailable_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "p"))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "tool",
                    "sympy-counterexample",
                    "--project",
                    str(project),
                    "--object-id",
                    "false_square_identity",
                    "--lhs",
                    "x^2",
                    "--rhs",
                    "x + 1",
                    "--samples",
                    "0,1,2",
                    "--title",
                    "False Square Identity",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            verification_dir = project / "08_evals" / "tool_verification"
            artifact_path = verification_dir / "false_square_identity_sympy_counterexample.json"
            report_path = verification_dir / "false_square_identity_sympy_counterexample_report.md"
            manifest_path = verification_dir / "manifest.json"
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            expected_returncode = (
                0
                if artifact["status"] in {"counterexample_found", "no_counterexample_found"}
                else 1
            )
            self.assertEqual(result.returncode, expected_returncode, result.stderr)
            self.assertIn("SymPy counterexample status:", result.stdout)
            self.assertEqual(artifact["schema_version"], 1)
            self.assertEqual(artifact["kind"], "sympy_counterexample_search")
            self.assertEqual(artifact["object_id"], "false_square_identity")
            self.assertEqual(artifact["input"]["samples"], [0, 1, 2])
            self.assertEqual(artifact["subprocess_invoked"], False)
            self.assertIn(
                artifact["status"],
                {"counterexample_found", "no_counterexample_found", "failed", "unavailable"},
            )
            if artifact["status"] == "counterexample_found":
                self.assertEqual(artifact["counterexample_found"], True)
                self.assertIn("assignment", artifact["output"]["counterexample"])
                self.assertIn("difference", artifact["output"]["counterexample"])
            else:
                self.assertEqual(artifact["counterexample_found"], False)
            report_text = report_path.read_text(encoding="utf-8")
            self.assertIn(
                "# Tool Verification: SymPy Counterexample Search",
                report_text,
            )
            self.assertIn(
                "- Not finding a counterexample is not a proof of the identity.",
                report_text,
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            record = manifest["records"][0]
            self.assertEqual(record["kind"], "sympy_counterexample_search")
            self.assertEqual(record["object_id"], "false_square_identity")
            self.assertEqual(
                record["artifact_path"],
                "08_evals/tool_verification/false_square_identity_sympy_counterexample.json",
            )
            self.assertEqual(
                record["report_path"],
                "08_evals/tool_verification/false_square_identity_sympy_counterexample_report.md",
            )

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

    def test_gap_order_cli_persists_group_order_result_or_unavailable_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "p"))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "tool",
                    "gap-order",
                    "--project",
                    str(project),
                    "--object-id",
                    "cyclic_order_three",
                    "--group",
                    "Group((1,2,3))",
                    "--expected-order",
                    "3",
                    "--title",
                    "Cyclic Order Three",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            verification_dir = project / "08_evals" / "tool_verification"
            artifact_path = verification_dir / "cyclic_order_three_gap_order.json"
            report_path = verification_dir / "cyclic_order_three_gap_order_report.md"
            manifest_path = verification_dir / "manifest.json"
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            expected_returncode = 0 if artifact["status"] == "verified" else 1
            self.assertEqual(result.returncode, expected_returncode, result.stderr)
            self.assertIn("GAP group order status:", result.stdout)
            self.assertEqual(artifact["schema_version"], 1)
            self.assertEqual(artifact["kind"], "gap_group_order_check")
            self.assertEqual(artifact["object_id"], "cyclic_order_three")
            self.assertEqual(artifact["tool"], "gap")
            self.assertEqual(artifact["input"]["group_expression"], "Group((1,2,3))")
            self.assertEqual(artifact["input"]["expected_order"], 3)
            self.assertIn(artifact["status"], {"verified", "failed", "unavailable"})
            if artifact["status"] == "verified":
                self.assertEqual(artifact["passed"], True)
                self.assertEqual(artifact["output"]["actual_order"], 3)
                self.assertEqual(artifact["external_executable_invoked"], True)
            else:
                self.assertEqual(artifact["passed"], False)
                self.assertGreaterEqual(len(artifact["issues"]), 1)
            report_text = report_path.read_text(encoding="utf-8")
            self.assertIn("# Tool Verification: GAP Group Order Check", report_text)
            self.assertIn("- It is computation evidence for one finite-structure expression.", report_text)
            self.assertIn("- It is not a formal proof.", report_text)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            record = manifest["records"][0]
            self.assertEqual(record["kind"], "gap_group_order_check")
            self.assertEqual(record["object_id"], "cyclic_order_three")
            self.assertEqual(
                record["artifact_path"],
                "08_evals/tool_verification/cyclic_order_three_gap_order.json",
            )
            self.assertEqual(
                record["report_path"],
                "08_evals/tool_verification/cyclic_order_three_gap_order_report.md",
            )

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

    def test_sage_order_cli_persists_group_order_result_or_unavailable_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "p"))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "tool",
                    "sage-order",
                    "--project",
                    str(project),
                    "--object-id",
                    "sage_cyclic_order_three",
                    "--group",
                    "PermutationGroup([[(1,2,3)]])",
                    "--expected-order",
                    "3",
                    "--title",
                    "Sage Cyclic Order Three",
                    "--timeout-seconds",
                    "30",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            verification_dir = project / "08_evals" / "tool_verification"
            artifact_path = verification_dir / "sage_cyclic_order_three_sage_order.json"
            report_path = verification_dir / "sage_cyclic_order_three_sage_order_report.md"
            manifest_path = verification_dir / "manifest.json"
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            expected_returncode = 0 if artifact["status"] == "verified" else 1
            self.assertEqual(result.returncode, expected_returncode, result.stderr)
            self.assertIn("Sage group order status:", result.stdout)
            self.assertEqual(artifact["schema_version"], 1)
            self.assertEqual(artifact["kind"], "sage_group_order_check")
            self.assertEqual(artifact["object_id"], "sage_cyclic_order_three")
            self.assertEqual(artifact["tool"], "sage")
            self.assertEqual(
                artifact["input"]["group_expression"],
                "PermutationGroup([[(1,2,3)]])",
            )
            self.assertEqual(artifact["input"]["expected_order"], 3)
            self.assertIn(artifact["status"], {"verified", "failed", "unavailable"})
            if artifact["status"] == "verified":
                self.assertEqual(artifact["passed"], True)
                self.assertEqual(artifact["output"]["actual_order"], 3)
                self.assertEqual(artifact["external_executable_invoked"], True)
            else:
                self.assertEqual(artifact["passed"], False)
                self.assertGreaterEqual(len(artifact["issues"]), 1)
            report_text = report_path.read_text(encoding="utf-8")
            self.assertIn("# Tool Verification: Sage Group Order Check", report_text)
            self.assertIn("- It is computation evidence for one Sage expression.", report_text)
            self.assertIn("- It is not a formal proof.", report_text)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            record = manifest["records"][0]
            self.assertEqual(record["kind"], "sage_group_order_check")
            self.assertEqual(record["object_id"], "sage_cyclic_order_three")
            self.assertEqual(
                record["artifact_path"],
                "08_evals/tool_verification/sage_cyclic_order_three_sage_order.json",
            )
            self.assertEqual(
                record["report_path"],
                "08_evals/tool_verification/sage_cyclic_order_three_sage_order_report.md",
            )

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

    def test_lean_skeleton_cli_marks_stale_reference_kb_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = _project_with_kernel_reference(root / "p")
            curated = project / "01_references" / "curated" / "kernel.curated.md"
            index_path = project / "06_kb" / "chunks" / "reference_index.json"
            index_time_ns = index_path.stat().st_mtime_ns
            curated.write_text(
                curated.read_text(encoding="utf-8")
                + "\n### Remark: New Kernel Context\n"
                + "The existing Reference KB index is stale for this curated text.\n",
                encoding="utf-8",
                newline="\n",
            )
            os.utime(
                curated,
                ns=(index_time_ns + 1_000_000_000, index_time_ns + 1_000_000_000),
            )

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
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Status: stale_reference_kb", result.stdout)
            verification_dir = project / "08_evals" / "tool_verification"
            report = verification_dir / "kernel_normality_statement_report.md"
            manifest_path = verification_dir / "manifest.json"
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("- Status: stale_reference_kb", report_text)
            self.assertIn("- Reference KB status: stale", report_text)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            record = manifest["records"][0]
            self.assertEqual(record["status"], "stale_reference_kb")
            self.assertEqual(record["reference_kb_status"], "stale")

    def test_tool_check_fails_stale_reference_kb_skeleton_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = _project_with_kernel_reference(root / "p")
            curated = project / "01_references" / "curated" / "kernel.curated.md"
            index_path = project / "06_kb" / "chunks" / "reference_index.json"
            index_time_ns = index_path.stat().st_mtime_ns
            curated.write_text(
                curated.read_text(encoding="utf-8")
                + "\n### Remark: New Kernel Context\n"
                + "The existing Reference KB index is stale for this curated text.\n",
                encoding="utf-8",
                newline="\n",
            )
            os.utime(
                curated,
                ns=(index_time_ns + 1_000_000_000, index_time_ns + 1_000_000_000),
            )
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

            self.assertEqual(result.returncode, 1)
            self.assertIn(
                "Checked 1 tool-verification record: 0 passed, 1 failed",
                result.stdout,
            )
            report_text = (project / "08_evals" / "tool_verification_eval.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("reference KB status is stale", report_text)

    def test_lean_check_cli_persists_frontend_result_or_unavailable_record(self) -> None:
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
                    "lean-check",
                    "--project",
                    str(project),
                    "--file",
                    "08_evals/tool_verification/kernel_normality_statement.lean",
                    "--object-id",
                    "kernel_normality_lean_frontend",
                    "--title",
                    "Kernel Normality Lean Frontend",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            verification_dir = project / "08_evals" / "tool_verification"
            artifact_path = verification_dir / "kernel_normality_lean_frontend_lean_check.json"
            report_path = verification_dir / "kernel_normality_lean_frontend_lean_check_report.md"
            manifest_path = verification_dir / "manifest.json"
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            expected_returncode = 0 if artifact["status"] == "lean_checked" else 1
            self.assertEqual(result.returncode, expected_returncode, result.stderr)
            self.assertIn("Lean check status:", result.stdout)
            self.assertEqual(artifact["schema_version"], 1)
            self.assertEqual(artifact["kind"], "lean_frontend_check")
            self.assertEqual(artifact["object_id"], "kernel_normality_lean_frontend")
            self.assertEqual(
                artifact["input"]["lean_file"],
                "08_evals/tool_verification/kernel_normality_statement.lean",
            )
            self.assertEqual(artifact["accepts_sorry"], True)
            self.assertIn(artifact["status"], {"lean_checked", "failed", "unavailable"})
            if artifact["status"] == "lean_checked":
                self.assertEqual(artifact["checked"], True)
                self.assertEqual(artifact["output"]["exit_code"], 0)
                self.assertEqual(artifact["external_executable_invoked"], True)
            else:
                self.assertEqual(artifact["checked"], False)
                self.assertGreaterEqual(len(artifact["issues"]), 1)
            report_text = report_path.read_text(encoding="utf-8")
            self.assertIn("# Tool Verification: Lean Frontend Check", report_text)
            self.assertIn("- Files containing `sorry` may still pass this check.", report_text)
            self.assertIn("- A passing check is not a completed formal proof.", report_text)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            record = next(
                row
                for row in manifest["records"]
                if row["object_id"] == "kernel_normality_lean_frontend"
            )
            self.assertEqual(record["kind"], "lean_frontend_check")
            self.assertEqual(
                record["artifact_path"],
                "08_evals/tool_verification/kernel_normality_lean_frontend_lean_check.json",
            )
            self.assertEqual(
                record["report_path"],
                "08_evals/tool_verification/kernel_normality_lean_frontend_lean_check_report.md",
            )

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
                "Checked 2 tool-verification records: 2 passed, 0 failed",
                check_result.stdout,
            )

    def test_lean_deps_cli_maps_reference_dependencies_for_formalization(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = _project_with_resolved_kernel_dependencies(root / "p")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "tool",
                    "lean-deps",
                    "--project",
                    str(project),
                    "--object-id",
                    "kernel_normality",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Lean dependency map status: mapped", result.stdout)
            self.assertIn("Dependencies: 3", result.stdout)
            self.assertIn("Resolved: 3", result.stdout)
            verification_dir = project / "08_evals" / "tool_verification"
            artifact_path = verification_dir / "kernel_normality_lean_dependencies.json"
            report_path = verification_dir / "kernel_normality_lean_dependencies_report.md"
            manifest_path = verification_dir / "manifest.json"
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            self.assertEqual(artifact["schema_version"], 1)
            self.assertEqual(artifact["kind"], "lean_dependency_map")
            self.assertEqual(artifact["object_id"], "kernel_normality")
            self.assertEqual(artifact["object_type"], "theorem")
            self.assertEqual(artifact["status"], "mapped")
            self.assertEqual(artifact["dependency_count"], 3)
            self.assertEqual(artifact["resolved_count"], 3)
            self.assertEqual(artifact["external_executable_invoked"], False)
            mapped = {row["label"]: row for row in artifact["dependencies"]}
            self.assertEqual(mapped["kernel"]["resolved_object_id"], "kernel")
            self.assertEqual(
                mapped["normal_subgroup"]["resolved_object_id"],
                "normal_subgroup",
            )
            self.assertEqual(
                mapped["homomorphism"]["resolved_object_id"],
                "homomorphism",
            )
            self.assertEqual(mapped["kernel"]["lean_identifier"], "kernel")
            self.assertEqual(artifact["issues"], [])
            report_text = report_path.read_text(encoding="utf-8")
            self.assertIn("# Tool Verification: Lean Dependency Map", report_text)
            self.assertIn("- This map links Reference KB dependencies to Lean formalization targets.", report_text)
            self.assertIn("- It does not prove the statement or any prerequisite.", report_text)
            self.assertIn("- No Lean executable was invoked.", report_text)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            record = manifest["records"][0]
            self.assertEqual(record["kind"], "lean_dependency_map")
            self.assertEqual(record["status"], "mapped")
            self.assertEqual(
                record["artifact_path"],
                "08_evals/tool_verification/kernel_normality_lean_dependencies.json",
            )
            self.assertEqual(
                record["report_path"],
                "08_evals/tool_verification/kernel_normality_lean_dependencies_report.md",
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
                    "--status",
                    "mapped",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(list_result.returncode, 0, list_result.stderr)
            self.assertIn("kernel_normality | mapped | lean_dependency_map", list_result.stdout)

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

    def test_lean_deps_cli_marks_stale_reference_kb_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = _project_with_resolved_kernel_dependencies(root / "p")
            curated = project / "01_references" / "curated" / "kernel_dependencies.curated.md"
            index_path = project / "06_kb" / "chunks" / "reference_index.json"
            index_time_ns = index_path.stat().st_mtime_ns
            curated.write_text(
                curated.read_text(encoding="utf-8")
                + "\n### Remark: New Kernel Dependency Context\n"
                + "The existing Reference KB index is stale for this dependency map.\n",
                encoding="utf-8",
                newline="\n",
            )
            os.utime(
                curated,
                ns=(index_time_ns + 1_000_000_000, index_time_ns + 1_000_000_000),
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "tool",
                    "lean-deps",
                    "--project",
                    str(project),
                    "--object-id",
                    "kernel_normality",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Lean dependency map status: stale_reference_kb", result.stdout)
            verification_dir = project / "08_evals" / "tool_verification"
            artifact_path = verification_dir / "kernel_normality_lean_dependencies.json"
            report_path = verification_dir / "kernel_normality_lean_dependencies_report.md"
            manifest_path = verification_dir / "manifest.json"
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            self.assertEqual(artifact["status"], "stale_reference_kb")
            self.assertEqual(artifact["mapping_status"], "mapped")
            self.assertEqual(artifact["reference_kb_status"], "stale")
            self.assertEqual(artifact["dependency_count"], 3)
            self.assertEqual(artifact["resolved_count"], 3)
            report_text = report_path.read_text(encoding="utf-8")
            self.assertIn("- Status: stale_reference_kb", report_text)
            self.assertIn("- Reference KB status: stale", report_text)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            record = manifest["records"][0]
            self.assertEqual(record["status"], "stale_reference_kb")
            self.assertEqual(record["reference_kb_status"], "stale")

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
                    "stale_reference_kb",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(list_result.returncode, 0, list_result.stderr)
            self.assertIn(
                "kernel_normality | stale_reference_kb | lean_dependency_map",
                list_result.stdout,
            )
            self.assertIn("reference_kb_status: stale", list_result.stdout)

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
            self.assertEqual(check_result.returncode, 1)
            self.assertIn(
                "Checked 1 tool-verification record: 0 passed, 1 failed",
                check_result.stdout,
            )
            quality_report = project / "08_evals" / "tool_verification_eval.md"
            self.assertIn(
                "reference KB status is stale",
                quality_report.read_text(encoding="utf-8"),
            )

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
            source_manifest = project / "08_evals" / "tool_verification" / "manifest.json"
            self.assertEqual(
                manifest["source_manifest_fingerprint"],
                {
                    "algorithm": "sha256",
                    "value": hashlib.sha256(source_manifest.read_bytes()).hexdigest(),
                },
            )
            record = manifest["records"][0]
            self.assertEqual(record["object_id"], "kernel_normality")
            self.assertEqual(record["record_status"], "unchecked_skeleton")
            self.assertEqual(record["quality_status"], "pass")
            artifact_path = project / record["artifact_path"]
            report_path = project / record["report_path"]
            self.assertEqual(
                record["artifact_fingerprint"],
                {
                    "algorithm": "sha256",
                    "value": hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
                },
            )
            self.assertEqual(
                record["report_fingerprint"],
                {
                    "algorithm": "sha256",
                    "value": hashlib.sha256(report_path.read_bytes()).hexdigest(),
                },
            )
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


def _project_with_resolved_kernel_dependencies(path: Path) -> Path:
    project = create_project(ProjectSpec(topic="Group Theory", path=path))
    curated = project / "01_references" / "curated" / "kernel_dependencies.curated.md"
    curated.write_text(
        "# Homomorphisms\n\n"
        "## Kernels\n\n"
        "### Definition: Kernel\n"
        "The kernel of a group homomorphism is the preimage of the identity.\n\n"
        "### Definition: Normal Subgroup\n"
        "A subgroup is normal when it is invariant under conjugation.\n\n"
        "### Definition: Homomorphism\n"
        "A homomorphism preserves multiplication and identities.\n\n"
        "### Theorem 3.2: Kernel Normality\n"
        "The kernel of a group homomorphism is a normal subgroup.\n"
        "Depends: kernel, normal_subgroup, homomorphism\n",
        encoding="utf-8",
        newline="\n",
    )
    build_reference_kb(project)
    return project


if __name__ == "__main__":
    unittest.main()
