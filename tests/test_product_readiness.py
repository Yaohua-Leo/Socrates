from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


class ProductReadinessTests(unittest.TestCase):
    def test_product_readiness_cli_json_reports_v1_capability_gap_map(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "socrates", "product", "readiness", "--json"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertNotIn("# Product Readiness Audit", result.stdout)
        payload = json.loads(result.stdout)

        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["quality_boundary"], "deterministic_product_readiness_audit")
        self.assertEqual(payload["product_goal"], "v1.0_math_learning_agent")
        self.assertEqual(payload["current_version"], "v0.59-alpha")
        self.assertEqual(payload["overall_status"], "not_v1_ready")
        self.assertEqual(payload["summary"]["capability_count"], 10)
        self.assertGreaterEqual(payload["summary"]["partial"], 1)
        self.assertGreaterEqual(payload["summary"]["decision_required"], 1)

        capabilities = {item["id"]: item for item in payload["capabilities"]}
        self.assertEqual(len(capabilities), 10)
        self.assertEqual(capabilities["project_initialization"]["status"], "implemented")
        self.assertEqual(capabilities["reference_discovery_management"]["status"], "partial")
        self.assertEqual(capabilities["literature_cleaning_structuring"]["status"], "partial")
        self.assertIn("web/arXiv discovery", " ".join(capabilities["reference_discovery_management"]["gaps"]))
        self.assertIn("built-in OCR/PDF backend", " ".join(capabilities["literature_cleaning_structuring"]["gaps"]))

        decision_points = {item["id"]: item for item in payload["decision_points"]}
        self.assertIn("next_major_product_lane", decision_points)
        self.assertIn("ocr_pdf_backend", decision_points["next_major_product_lane"]["options"])
        self.assertIn("autonomous_llm_tutoring", decision_points["next_major_product_lane"]["options"])
        self.assertIn("ui_plugin_surface", decision_points["next_major_product_lane"]["options"])
        self.assertIn("real_long_term_validation", decision_points["next_major_product_lane"]["options"])

    def test_product_readiness_cli_renders_prose_audit(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "socrates", "product", "readiness"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertIn("# Product Readiness Audit", result.stdout)
        self.assertIn("- Current version: v0.59-alpha", result.stdout)
        self.assertIn("- Overall status: not_v1_ready", result.stdout)
        self.assertIn("## Capability Map", result.stdout)
        self.assertIn("- project_initialization | implemented", result.stdout)
        self.assertIn("- reference_discovery_management | partial", result.stdout)
        self.assertIn("## Decision Points", result.stdout)
        self.assertIn("- next_major_product_lane:", result.stdout)
        self.assertIn("ocr_pdf_backend", result.stdout)
        self.assertIn("## Boundary", result.stdout)


if __name__ == "__main__":
    unittest.main()
