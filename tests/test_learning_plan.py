from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from socrates.context import load_project
from socrates.contracts import SourceRecord
from socrates.kb import build_reference_kb
from socrates.planning import create_learning_plan
from socrates.project import ProjectSpec, create_project
from socrates.state import (
    LearningStatePatch,
    MistakeRecord,
    build_review_schedule,
    update_learning_state,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


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

    def test_session_plan_includes_source_grounded_reference_context_from_kb(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(
                ProjectSpec(
                    topic="Normal Subgroup",
                    path=Path(temp_dir) / "normal_subgroup",
                    goal="Understand the definition before quotient groups.",
                )
            )
            curated = project / "01_references" / "curated" / "normal_subgroups.curated.md"
            curated.write_text(
                "# Group Theory\n"
                "## Subgroups\n"
                "### Definition 3.1: Normal Subgroup\n"
                "Page: 82\n"
                "A subgroup N of G is normal when it is stable under conjugation.\n"
                "Depends: subgroup, conjugation\n",
                encoding="utf-8",
                newline="\n",
            )
            build_reference_kb(project)

            create_learning_plan(project)

            session_plan = (
                project / "02_learning_plan" / "session_0001_plan.md"
            ).read_text(encoding="utf-8")
            self.assertIn("## Reference Context", session_plan)
            self.assertIn("Definition 3.1: Normal Subgroup", session_plan)
            self.assertIn(
                "Source: 01_references/curated/normal_subgroups.curated.md",
                session_plan,
            )
            self.assertIn("Page: 82", session_plan)
            self.assertIn("Depends: subgroup, conjugation", session_plan)

    def test_plan_cli_warns_and_records_stale_reference_kb_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(
                ProjectSpec(
                    topic="Normal Subgroup",
                    path=Path(temp_dir) / "normal_subgroup",
                    goal="Understand the definition before quotient groups.",
                )
            )
            curated = project / "01_references" / "curated" / "normal_subgroups.curated.md"
            curated.write_text(
                "# Group Theory\n"
                "## Subgroups\n"
                "### Definition 3.1: Normal Subgroup\n"
                "A subgroup N of G is normal when it is stable under conjugation.\n"
                "Depends: subgroup, conjugation\n",
                encoding="utf-8",
                newline="\n",
            )
            kb_result = build_reference_kb(project)
            index_time_ns = kb_result.index_path.stat().st_mtime_ns
            curated.write_text(
                curated.read_text(encoding="utf-8")
                + "\n### Remark: Fresh Curated Planning Note\n"
                + "This note is newer than the existing Reference KB index.\n",
                encoding="utf-8",
                newline="\n",
            )
            os.utime(
                curated,
                ns=(index_time_ns + 1_000_000_000, index_time_ns + 1_000_000_000),
            )

            result = subprocess.run(
                [sys.executable, "-m", "socrates", "plan", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("warning: Reference KB status is stale", result.stderr)
            session_plan = (
                project / "02_learning_plan" / "session_0001_plan.md"
            ).read_text(encoding="utf-8")
            self.assertIn("- Reference KB status: stale", session_plan)

    def test_review_adjust_plan_command_updates_short_term_plan_from_schedule(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            create_learning_plan(project)
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(
                    concept_mastery={"normal_subgroup": 0.41},
                    mistakes=[
                        MistakeRecord(
                            session_id="session-001",
                            concept="normal_subgroup",
                            misconception_id="normal_equals_central",
                            user_answer="Normal means central.",
                            analysis="Confuses normality with centrality.",
                            repair_suggestion="Compare gNg^-1=N with gn=ng.",
                        )
                    ],
                ),
            )
            build_review_schedule(context)

            first = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "adjust-plan",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            second = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "adjust-plan",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertIn("Adjusted short-term plan", first.stdout)
            short_term_plan = (
                project / "02_learning_plan" / "short_term_plan.md"
            ).read_text(encoding="utf-8")
            self.assertEqual(short_term_plan.count("## Review Adjustments"), 1)
            self.assertIn(
                "- normal_subgroup (high, next_session): "
                "mastery 0.41; active misconception normal_equals_central x1",
                short_term_plan,
            )
            self.assertIn(
                "  - Repair suggestion: Compare gNg^-1=N with gn=ng.",
                short_term_plan,
            )


if __name__ == "__main__":
    unittest.main()
