from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
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
        self.assertGreaterEqual(payload["artifacts"]["study_briefs"], 1)
        self.assertEqual(payload["returning_learner"]["study_brief"], "current")
        self.assertEqual(payload["returning_learner"]["dashboard_study_brief"], "current")
        self.assertEqual(payload["returning_learner"]["resume_state"], "ready")
        self.assertEqual(payload["returning_learner"]["recommended_command"], "none")

    def test_lifecycle_canary_cli_json_writes_inspectable_artifact_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts = Path(temp_dir) / "canary_artifacts"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "lifecycle",
                    "canary",
                    "--artifacts",
                    str(artifacts),
                    "--json",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, "")
            payload = json.loads(result.stdout)

            self.assertEqual(payload["status"], "pass")
            self.assertTrue(payload["temporary_project"]["cleaned"])
            self.assertTrue(payload["artifact_bundle"]["written"])
            self.assertEqual(Path(payload["artifact_bundle"]["root"]), artifacts)

            report_path = artifacts / "canary_report.json"
            project_path = artifacts / "project"
            self.assertEqual(Path(payload["artifact_bundle"]["report_path"]), report_path)
            self.assertEqual(Path(payload["artifact_bundle"]["project_path"]), project_path)
            self.assertTrue(report_path.exists())
            self.assertTrue((project_path / "08_evals" / "lifecycle_eval.md").exists())
            self.assertTrue((project_path / "07_exports" / "briefs" / "study_brief.md").exists())
            self.assertTrue((project_path / "07_exports" / "briefs" / "study_brief_manifest.json").exists())

            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["quality_boundary"], "deterministic_mvp_lifecycle_canary")
            self.assertEqual(report["status"], "pass")
            self.assertTrue(report["temporary_project"]["cleaned"])
            self.assertEqual(report["returning_learner"]["study_brief"], "current")
            self.assertEqual(report["returning_learner"]["resume_state"], "ready")

    def test_lifecycle_canary_cli_rejects_nonempty_artifact_bundle_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts = Path(temp_dir) / "canary_artifacts"
            artifacts.mkdir()
            (artifacts / "keep.txt").write_text("do not overwrite\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "lifecycle",
                    "canary",
                    "--artifacts",
                    str(artifacts),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("artifact directory is not empty", result.stderr)
            self.assertEqual((artifacts / "keep.txt").read_text(encoding="utf-8"), "do not overwrite\n")
            self.assertFalse((artifacts / "project").exists())


if __name__ == "__main__":
    unittest.main()
