from __future__ import annotations

from datetime import date
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from socrates.context import load_project
from socrates.contracts import SourceRecord
from socrates.kb import build_reference_kb
from socrates.planning import create_learning_plan, create_next_session_plan
from socrates.project import ProjectSpec, create_project
from socrates.state import (
    LearningStatePatch,
    MistakeRecord,
    build_review_schedule,
    update_learning_state,
)
from socrates.tutoring import run_scripted_tutoring_session


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

    def test_long_term_plan_includes_reference_chapter_outline_from_kb(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(
                ProjectSpec(
                    topic="Normal Subgroup",
                    path=Path(temp_dir) / "normal_subgroup",
                    goal="Follow the textbook route into quotient groups.",
                )
            )
            curated = project / "01_references" / "curated" / "normal_subgroups.curated.md"
            curated.write_text(
                "# Chapter 3: Quotient Groups\n"
                "## Section 3.1 Normal Subgroups\n"
                "### Definition 3.1: Normal Subgroup\n"
                "A subgroup N of G is normal when it is stable under conjugation.\n"
                "Depends: subgroup, conjugation\n",
                encoding="utf-8",
                newline="\n",
            )
            build_reference_kb(project)

            create_learning_plan(project)

            long_term_plan = (
                project / "02_learning_plan" / "long_term_plan.md"
            ).read_text(encoding="utf-8")
            self.assertIn("## Reference Reading Path", long_term_plan)
            self.assertIn("- Chapter 3: Quotient Groups", long_term_plan)
            self.assertIn("  - Section 3.1 Normal Subgroups", long_term_plan)
            self.assertIn("    - Definition 3.1: Normal Subgroup", long_term_plan)

    def test_create_learning_plan_updates_chapter_sequence_and_checkpoints_from_kb(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(
                ProjectSpec(
                    topic="Normal Subgroup",
                    path=Path(temp_dir) / "normal_subgroup",
                    goal="Follow the textbook route into quotient groups.",
                )
            )
            curated = project / "01_references" / "curated" / "normal_subgroups.curated.md"
            curated.write_text(
                "# Chapter 3: Quotient Groups\n"
                "## Section 3.1 Normal Subgroups\n"
                "### Definition 3.1: Normal Subgroup\n"
                "A subgroup N of G is normal when it is stable under conjugation.\n"
                "Depends: subgroup, conjugation\n"
                "### Theorem 3.2: Kernel Normality\n"
                "The kernel of a group homomorphism is normal.\n"
                "Depends: kernel, homomorphism\n",
                encoding="utf-8",
                newline="\n",
            )
            build_reference_kb(project)

            create_learning_plan(project)

            chapter_sequence = (
                project / "02_learning_plan" / "chapter_sequence.yaml"
            ).read_text(encoding="utf-8")
            checkpoints = (
                project / "02_learning_plan" / "checkpoints.yaml"
            ).read_text(encoding="utf-8")
            self.assertIn('title: "Chapter 3: Quotient Groups"', chapter_sequence)
            self.assertIn('title: "Section 3.1 Normal Subgroups"', chapter_sequence)
            self.assertIn("id: normal_subgroup", chapter_sequence)
            self.assertIn("type: definition", chapter_sequence)
            self.assertIn('number: "3.1"', chapter_sequence)
            self.assertIn("id: checkpoint_001", checkpoints)
            self.assertIn('scope: "Chapter 3: Quotient Groups"', checkpoints)
            self.assertIn("object_count: 2", checkpoints)
            self.assertIn("status: pending", checkpoints)

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

    def test_plan_cli_warns_and_continues_with_invalid_reference_kb_index(self) -> None:
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
            kb_result.index_path.write_text("{not valid json\n", encoding="utf-8", newline="\n")

            result = subprocess.run(
                [sys.executable, "-m", "socrates", "plan", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("warning: Reference KB status is invalid", result.stderr)
            self.assertIn("socrates kb build --project", result.stderr)
            self.assertNotIn("Expecting property name", result.stderr)
            session_plan = (
                project / "02_learning_plan" / "session_0001_plan.md"
            ).read_text(encoding="utf-8")
            self.assertIn("- Reference KB status: invalid", session_plan)
            self.assertIn("- Reference KB context: none indexed yet.", session_plan)

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

    def test_review_adjust_plan_rejects_corrupt_learning_state_without_rewriting_plan(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            create_learning_plan(project)
            short_term_path = project / "02_learning_plan" / "short_term_plan.md"
            original_short_term_plan = short_term_path.read_text(encoding="utf-8")
            (project / "00_meta" / "learning_state.json").write_text(
                "{not valid json\n",
                encoding="utf-8",
                newline="\n",
            )

            result = subprocess.run(
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

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertIn("error: invalid learning_state.json", result.stderr)
            self.assertIn("repair the JSON before adjusting review plans", result.stderr)
            self.assertNotIn("Expecting property name", result.stderr)
            self.assertEqual(
                short_term_path.read_text(encoding="utf-8"),
                original_short_term_plan,
            )

    def test_create_next_session_plan_writes_stateful_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(
                ProjectSpec(
                    topic="Normal Subgroup",
                    path=root / "normal_subgroup",
                    goal="Understand normality before quotient groups.",
                )
            )
            curated = project / "01_references" / "curated" / "normal_subgroups.curated.md"
            curated.write_text(
                "# Group Theory\n"
                "## Normal Subgroups\n"
                "### Definition 3.1: Normal Subgroup\n"
                "A subgroup N of G is normal when it is stable under conjugation.\n"
                "Depends: subgroup, conjugation\n",
                encoding="utf-8",
                newline="\n",
            )
            build_reference_kb(project)
            script = root / "session.script"
            script.write_text(
                "topic: Normal Subgroup\n"
                "question: What does conjugation invariance require?\n"
                "hint: Compare normality with centrality.\n"
                "attempt: Normal means central.\n"
                "misconception: normal_equals_central\n"
                "next: Rebuild normality from gNg^-1=N.\n",
                encoding="utf-8",
                newline="\n",
            )
            run_scripted_tutoring_session(project, script, session_id="session_0001")
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(
                    concept_mastery={"normal_subgroup": 0.42},
                    mistakes=[
                        MistakeRecord(
                            session_id="session_0001",
                            concept="normal_subgroup",
                            misconception_id="normal_equals_central",
                            user_answer="Normal means central.",
                            analysis="Confuses normality with centrality.",
                            repair_suggestion="Compare gNg^-1=N with gn=ng.",
                        )
                    ],
                ),
            )
            build_review_schedule(context, as_of=date(2026, 6, 4))

            result = create_next_session_plan(
                project,
                session_id="session_0002",
                as_of=date(2026, 6, 4),
            )

            self.assertEqual(result.session_id, "session_0002")
            self.assertEqual(result.due_reviews, 1)
            self.assertEqual(result.previous_session_id, "session_0001")
            self.assertEqual(
                result.plan_path,
                project / "02_learning_plan" / "session_0002_plan.md",
            )
            self.assertEqual(
                result.manifest_path,
                project / "02_learning_plan" / "next_session_plan_manifest.json",
            )
            plan_text = result.plan_path.read_text(encoding="utf-8")
            self.assertIn("## Previous Session Handoff", plan_text)
            self.assertIn("## Due Reviews", plan_text)
            self.assertIn("normal_subgroup", plan_text)
            self.assertIn("repair: Compare gNg^-1=N with gn=ng.", plan_text)
            self.assertIn("Definition 3.1: Normal Subgroup", plan_text)
            self.assertIn("## Boundary", plan_text)
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual(manifest["session_id"], "session_0002")
            self.assertEqual(manifest["status"], "ready")
            self.assertEqual(manifest["quality_boundary"], "deterministic_handoff_plan")
            self.assertEqual(manifest["due_reviews"], 1)
            self.assertEqual(manifest["previous_session_id"], "session_0001")
            self.assertEqual(manifest["action_queue"]["scheduled_reviews"], 1)

    def test_create_next_session_plan_rejects_corrupt_learning_state_without_writing(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            plan_path = project / "02_learning_plan" / "session_0002_plan.md"
            (project / "00_meta" / "learning_state.json").write_text(
                "{not valid json\n",
                encoding="utf-8",
                newline="\n",
            )

            with self.assertRaisesRegex(
                ValueError,
                "invalid learning_state.json; repair the JSON before creating next-session plans",
            ):
                create_next_session_plan(project, session_id="session_0002")

            self.assertFalse(plan_path.exists())

    def test_session_plan_next_cli_writes_handoff_plan_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(
                ProjectSpec(
                    topic="Normal Subgroup",
                    path=Path(temp_dir) / "normal_subgroup",
                )
            )
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(concept_mastery={"normal_subgroup": 0.42}),
            )
            build_review_schedule(context, as_of=date(2026, 6, 4))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "session",
                    "plan-next",
                    "--project",
                    str(project),
                    "--session-id",
                    "session_0002",
                    "--as-of",
                    "2026-06-04",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Created next-session plan session_0002", result.stdout)
            self.assertIn("Next-session manifest:", result.stdout)
            self.assertTrue((project / "02_learning_plan" / "session_0002_plan.md").exists())
            self.assertTrue(
                (project / "02_learning_plan" / "next_session_plan_manifest.json").exists()
            )
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Next session plan: session_0002", status.stdout)
            self.assertIn("Next session due reviews: 1", status.stdout)
            self.assertIn("Next session handoff: ready", status.stdout)


if __name__ == "__main__":
    unittest.main()
