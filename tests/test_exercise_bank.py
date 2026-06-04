from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

from socrates.artifacts import generate_exercise_drafts
from socrates.exercise_bank import build_exercise_bank, read_exercise_bank
from socrates.exercise_validation import validate_project_exercises
from socrates.exercises import approve_exercise_draft, record_exercise_attempt
from socrates.project import ProjectSpec, create_project


REPO_ROOT = Path(__file__).resolve().parents[1]


class ExerciseBankTests(unittest.TestCase):
    def test_bank_includes_only_approved_passing_validation_records(self) -> None:
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
            approve_exercise_draft(project, "normal_subgroup_01")
            approve_exercise_draft(project, "normal_subgroup_02")
            validate_project_exercises(project)

            result = build_exercise_bank(project)

            self.assertEqual(result.total_exercises, 2)
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual(
                [item["exercise_id"] for item in manifest["records"]],
                [
                    "normal_subgroup_01",
                    "normal_subgroup_02",
                ],
            )
            summaries = read_exercise_bank(project)
            self.assertEqual(
                [item.exercise_id for item in summaries],
                [
                    "normal_subgroup_01",
                    "normal_subgroup_02",
                ],
            )

    def test_exercise_bank_cli_builds_and_prints_status(self) -> None:
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
            approve_exercise_draft(project, "normal_subgroup_01")
            validate_project_exercises(project)

            build = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "exercise",
                    "bank",
                    "build",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            status = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "exercise",
                    "bank",
                    "status",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(build.returncode, 0, build.stderr)
            self.assertIn("Exercise bank entries: 1", build.stdout)
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("# Exercise Bank", status.stdout)
            self.assertIn(
                "- normal_subgroup_01 | Normal Subgroup | difficulty 1",
                status.stdout,
            )

    def test_bank_keeps_approved_exercise_after_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "p"))
            answer = root / "answer.md"
            answer.write_text("Use conjugation invariance.\n", encoding="utf-8", newline="\n")
            generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="df-1",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )
            approve_exercise_draft(project, "normal_subgroup_01")
            record_exercise_attempt(project, "normal_subgroup_01", answer)
            validate_project_exercises(project)

            result = build_exercise_bank(project)

            self.assertEqual(result.total_exercises, 1)
            summaries = read_exercise_bank(project)
            self.assertEqual(summaries[0].exercise_id, "normal_subgroup_01")


if __name__ == "__main__":
    unittest.main()
