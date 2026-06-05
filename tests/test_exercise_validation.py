from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

from socrates.artifacts import generate_exercise_drafts
from socrates.exercise_validation import validate_exercise, validate_project_exercises
from socrates.project import ProjectSpec, create_project


REPO_ROOT = Path(__file__).resolve().parents[1]


class ExerciseValidationTests(unittest.TestCase):
    def test_validate_one_exercise_writes_report_and_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(
                ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p")
            )
            draft = generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="df-1",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )[0]

            result = validate_exercise(project, draft.id)

            self.assertEqual(result.exercise_id, draft.id)
            self.assertEqual(result.status, "pass")
            self.assertTrue(result.report_path.exists())
            self.assertTrue(result.artifact_path.exists())
            artifact = json.loads(result.artifact_path.read_text(encoding="utf-8"))
            self.assertEqual(artifact["schema_version"], 1)
            self.assertEqual(artifact["exercise_id"], draft.id)
            self.assertEqual(artifact["status"], "pass")
            self.assertEqual(artifact["schema"]["status"], "pass")
            self.assertEqual(artifact["counterexample_search"]["status"], "not_run")

    def test_project_validation_manifest_records_failures(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(
                ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p")
            )
            draft = generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="df-1",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )[0]
            exercise_path = project / draft.path
            exercise_path.write_text(
                exercise_path.read_text(encoding="utf-8").replace(
                    "- Complete conclusion: 3 pts",
                    "- Complete conclusion: 2 pts",
                    1,
                ),
                encoding="utf-8",
                newline="\n",
            )

            result = validate_project_exercises(project)

            self.assertEqual(result.checked, 5)
            self.assertEqual(result.failed, 1)
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            failed = [item for item in manifest["records"] if item["status"] == "fail"]
            self.assertEqual(failed[0]["exercise_id"], draft.id)
            self.assertIn("rubric point values do not sum to total", failed[0]["issues"])

    def test_exercise_validate_cli_writes_project_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(
                ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p")
            )
            generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="df-1",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "exercise",
                    "validate",
                    "--project",
                    str(project),
                    "--all",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Exercise validation checked: 5", result.stdout)
            self.assertIn("Exercise validation manifest:", result.stdout)
            self.assertTrue((project / "08_evals" / "exercise_validation_manifest.json").exists())

    def test_exercise_validate_cli_returns_failure_for_invalid_exercise(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(
                ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p")
            )
            draft = generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="df-1",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )[0]
            exercise_path = project / draft.path
            exercise_path.write_text(
                exercise_path.read_text(encoding="utf-8").replace(
                    "- Correct verification: 4 pts",
                    "- Correct verification: 3 pts",
                    1,
                ),
                encoding="utf-8",
                newline="\n",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "exercise",
                    "validate",
                    "--project",
                    str(project),
                    "--exercise",
                    draft.id,
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn(f"Exercise validation {draft.id}: fail", result.stdout)
            self.assertIn("rubric point values do not sum to total", result.stdout)


if __name__ == "__main__":
    unittest.main()
