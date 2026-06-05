from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


class LifecycleCanaryTests(unittest.TestCase):
    def test_lifecycle_canary_cli_reports_passing_temporary_mvp_scenario(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "socrates", "lifecycle", "canary"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertIn("MVP lifecycle canary: pass", result.stdout)
        self.assertIn("Scenario: normal_subgroup_mvp", result.stdout)
        self.assertIn("Lifecycle audit:", result.stdout)
        self.assertIn("Temporary project: cleaned", result.stdout)

    def test_lifecycle_canary_cli_json_reports_structured_evidence(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "socrates", "lifecycle", "canary", "--json"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertNotIn("MVP lifecycle canary:", result.stdout)
        payload = json.loads(result.stdout)

        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["quality_boundary"], "deterministic_mvp_lifecycle_canary")
        self.assertEqual(payload["scenario"], "normal_subgroup_mvp")
        self.assertEqual(payload["status"], "pass")
        self.assertTrue(payload["temporary_project"]["cleaned"])
        self.assertEqual(
            payload["lifecycle"]["passed_checks"],
            payload["lifecycle"]["total_checks"],
        )
        self.assertGreaterEqual(payload["lifecycle"]["total_checks"], 25)
        self.assertGreaterEqual(payload["artifacts"]["kb_objects"], 1)
        self.assertGreaterEqual(payload["artifacts"]["reviewed_notes"], 2)
        self.assertGreaterEqual(payload["artifacts"]["generated_exercises"], 5)
        self.assertGreaterEqual(payload["artifacts"]["learning_reports"], 3)


if __name__ == "__main__":
    unittest.main()
