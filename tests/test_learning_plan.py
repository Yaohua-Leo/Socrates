from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from socrates.contracts import SourceRecord
from socrates.planning import create_learning_plan
from socrates.project import ProjectSpec, create_project


class LearningPlanTests(unittest.TestCase):
    def test_create_learning_plan_writes_three_plan_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(
                ProjectSpec(
                    topic="Group Theory",
                    path=Path(temp_dir) / "group_theory",
                    goal="Prepare for representation theory.",
                )
            )

            written = create_learning_plan(project)

            self.assertEqual(
                written,
                [
                    project / "02_learning_plan" / "long_term_plan.md",
                    project / "02_learning_plan" / "short_term_plan.md",
                    project / "02_learning_plan" / "session_0001_plan.md",
                ],
            )
            for path in written:
                self.assertTrue(path.exists(), path)

    def test_generated_plans_use_project_topic_goal_and_source_titles(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(
                ProjectSpec(
                    topic="Homological Algebra",
                    path=Path(temp_dir) / "homological_algebra",
                    goal="Learn enough to read derived categories.",
                )
            )
            registry = project / "01_references" / "source_registry.yaml"
            registry.write_text(
                "sources:\n"
                + SourceRecord(
                    id="weibel",
                    type="pdf",
                    title="An Introduction to Homological Algebra",
                    role="main_textbook",
                    priority=1,
                    status="raw_imported",
                    local_path="01_references/raw/weibel.pdf",
                ).to_registry_yaml(),
                encoding="utf-8",
                newline="\n",
            )

            create_learning_plan(project)

            plan_text = "\n".join(
                path.read_text(encoding="utf-8")
                for path in [
                    project / "02_learning_plan" / "long_term_plan.md",
                    project / "02_learning_plan" / "short_term_plan.md",
                    project / "02_learning_plan" / "session_0001_plan.md",
                ]
            )
            self.assertIn("Homological Algebra", plan_text)
            self.assertIn("Learn enough to read derived categories.", plan_text)
            self.assertIn("An Introduction to Homological Algebra", plan_text)


if __name__ == "__main__":
    unittest.main()
