from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from socrates.project import ProjectExistsError, ProjectSpec, create_project


REPO_ROOT = Path(__file__).resolve().parents[1]


class ProjectInitTests(unittest.TestCase):
    def test_create_project_writes_expected_tree_and_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "group_theory"
            created = create_project(
                ProjectSpec(
                    topic="Group Theory",
                    path=target,
                    goal="Prepare for representation theory.",
                    main_reference="Dummit and Foote",
                )
            )

            self.assertEqual(created, target.resolve())
            expected_paths = [
                "project.yaml",
                "README.md",
                "00_meta/goals.md",
                "00_meta/learning_state.json",
                "01_references/source_registry.yaml",
                "02_learning_plan/long_term_plan.md",
                "03_sessions",
                "04_atomic_notes/drafts",
                "05_exercises/mistake_bank.md",
                "06_kb/concept_graph.json",
                "07_exports/obsidian",
                "07_exports/reports",
                "08_evals/note_quality_eval.md",
            ]
            for relative_path in expected_paths:
                self.assertTrue((created / relative_path).exists(), relative_path)

            project_yaml = (created / "project.yaml").read_text(encoding="utf-8")
            self.assertIn("id: group_theory", project_yaml)
            self.assertIn("source_registry: 01_references/source_registry.yaml", project_yaml)
            self.assertIn('main_reference: "Dummit and Foote"', project_yaml)

            learning_state = json.loads(
                (created / "00_meta" / "learning_state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(learning_state["concept_mastery"], {})
            self.assertEqual(learning_state["proof_skills"], {})
            self.assertEqual(learning_state["misconceptions"], {})
            self.assertEqual(
                (created / "01_references" / "source_registry.yaml").read_text(
                    encoding="utf-8"
                ),
                "sources: []\n",
            )

    def test_cli_init_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "homological_algebra"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "init",
                    "--topic",
                    "Homological Algebra",
                    "--path",
                    str(target),
                    "--goal",
                    "Prepare for derived categories.",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Created Socrates project at", result.stdout)
            self.assertTrue((target / "project.yaml").exists())

    def test_existing_nonempty_directory_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "existing"
            target.mkdir()
            (target / "notes.md").write_text("existing content\n", encoding="utf-8")

            with self.assertRaises(ProjectExistsError):
                create_project(ProjectSpec(topic="Group Theory", path=target))

    def test_cli_reports_existing_directory_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "existing"
            target.mkdir()
            (target / "notes.md").write_text("existing content\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "init",
                    "--topic",
                    "Group Theory",
                    "--path",
                    str(target),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("error: Target directory is not empty", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_docs_contain_extracted_plan_sentinels(self) -> None:
        goal_doc = (REPO_ROOT / "docs" / "final_development_goal.md").read_text(
            encoding="utf-8"
        )
        roadmap_doc = (REPO_ROOT / "docs" / "development_roadmap.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("# 最终开发目标", goal_doc)
        self.assertIn("# 各阶段开发计划", roadmap_doc)
        self.assertIn("Phase 12", roadmap_doc)
        self.assertIn("v0.1", roadmap_doc)
        self.assertIn("最小可用产品标准", roadmap_doc)
        self.assertEqual(goal_doc.count("```") % 2, 0)
        self.assertEqual(roadmap_doc.count("```") % 2, 0)


if __name__ == "__main__":
    unittest.main()
