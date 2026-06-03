from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from socrates.context import load_project
from socrates.project import ProjectSpec, create_project
from socrates.state import (
    EvalReportUpdate,
    LearningStatePatch,
    MistakeRecord,
    build_review_schedule,
    resolve_active_misconceptions_for_concept,
    update_eval_report,
    update_learning_state,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class StateEvalTests(unittest.TestCase):
    def test_update_learning_state_merges_scores_and_appends_mistake(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)

            update_learning_state(
                context,
                LearningStatePatch(
                    concept_mastery={"normal_subgroup": 0.64},
                    proof_skills={"unfold_definition": 0.82},
                    mistakes=[
                        MistakeRecord(
                            session_id="session-001",
                            concept="normal_subgroup",
                            misconception_id="normal_equals_central",
                            user_answer="Every normal subgroup commutes with every element.",
                            analysis="Confuses normality with centrality.",
                            repair_suggestion="Compare gNg^-1 = N with gn = ng.",
                            follow_up_exercises=["Find a non-central normal subgroup."],
                        )
                    ],
                ),
            )

            learning_state = json.loads(context.learning_state.read_text(encoding="utf-8"))
            self.assertEqual(learning_state["concept_mastery"]["normal_subgroup"], 0.64)
            self.assertEqual(learning_state["proof_skills"]["unfold_definition"], 0.82)
            self.assertEqual(
                learning_state["misconceptions"]["normal_equals_central"],
                {"concept": "normal_subgroup", "count": 1, "status": "active"},
            )

            mistake_bank = context.mistake_bank.read_text(encoding="utf-8")
            self.assertIn("## session-001 - normal_subgroup", mistake_bank)
            self.assertIn("- Misconception: normal_equals_central", mistake_bank)
            self.assertIn("- Recurrence: no", mistake_bank)
            self.assertIn("- Follow-up exercises:", mistake_bank)
            self.assertIn("  - Find a non-central normal subgroup.", mistake_bank)

    def test_repeated_mistake_marks_recurrence_and_increments_count(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            mistake = MistakeRecord(
                session_id="session-001",
                concept="normal_subgroup",
                misconception_id="normal_equals_central",
                user_answer="Normal means commutative.",
                analysis="Confuses normality with centrality.",
                repair_suggestion="Use conjugation examples.",
            )

            update_learning_state(context, LearningStatePatch(mistakes=[mistake]))
            update_learning_state(
                context,
                LearningStatePatch(
                    mistakes=[
                        MistakeRecord(
                            session_id="session-002",
                            concept="normal_subgroup",
                            misconception_id="normal_equals_central",
                            user_answer="Normal elements are central.",
                            analysis="Same confusion recurred.",
                            repair_suggestion="Contrast center Z(G) with normal subgroups.",
                        )
                    ]
                ),
            )

            learning_state = json.loads(context.learning_state.read_text(encoding="utf-8"))
            self.assertEqual(learning_state["misconceptions"]["normal_equals_central"]["count"], 2)
            mistake_bank = context.mistake_bank.read_text(encoding="utf-8")
            self.assertIn("## session-002 - normal_subgroup", mistake_bank)
            self.assertIn("- Recurrence: yes", mistake_bank)

    def test_build_review_schedule_uses_weak_concepts_and_active_misconceptions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            mistake = MistakeRecord(
                session_id="session-001",
                concept="normal_subgroup",
                misconception_id="normal_equals_central",
                user_answer="Normal means central.",
                analysis="Confuses normality with centrality.",
                repair_suggestion="Compare normality with the center.",
            )

            update_learning_state(
                context,
                LearningStatePatch(
                    concept_mastery={"normal_subgroup": 0.41, "subgroup": 0.82},
                    mistakes=[mistake],
                ),
            )
            update_learning_state(context, LearningStatePatch(mistakes=[mistake]))

            schedule_path = build_review_schedule(context)

            self.assertEqual(schedule_path, project / "02_learning_plan" / "review_schedule.md")
            schedule_text = schedule_path.read_text(encoding="utf-8")
            self.assertIn("# Review Schedule", schedule_text)
            self.assertIn("## normal_subgroup", schedule_text)
            self.assertIn("- Priority: high", schedule_text)
            self.assertIn("- Due: next_session", schedule_text)
            self.assertIn("- Reason: mastery 0.41; active misconception normal_equals_central x2", schedule_text)
            self.assertNotIn("## subgroup", schedule_text)

            learning_state = json.loads(context.learning_state.read_text(encoding="utf-8"))
            self.assertEqual(
                learning_state["review_schedule"][0],
                {
                    "concept": "normal_subgroup",
                    "priority": "high",
                    "due": "next_session",
                    "reason": "mastery 0.41; active misconception normal_equals_central x2",
                },
            )

    def test_review_schedule_command_updates_status_count(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(concept_mastery={"normal_subgroup": 0.43}),
            )

            schedule_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "schedule",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            exercises_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "exercises",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            status_result = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(schedule_result.returncode, 0, schedule_result.stderr)
            self.assertIn("Scheduled 1 review item", schedule_result.stdout)
            self.assertEqual(exercises_result.returncode, 0, exercises_result.stderr)
            self.assertIn("Generated 1 targeted review exercise", exercises_result.stdout)
            self.assertTrue(
                (project / "05_exercises" / "generated" / "review_normal_subgroup_01.md").exists()
            )
            self.assertEqual(status_result.returncode, 0, status_result.stderr)
            self.assertIn("Scheduled reviews: 1", status_result.stdout)
            self.assertIn("Generated exercises: 1", status_result.stdout)

    def test_status_counts_active_and_resolved_misconceptions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(
                    mistakes=[
                        MistakeRecord(
                            session_id="session-001",
                            concept="normal_subgroup",
                            misconception_id="normal_equals_central",
                            user_answer="Normal means central.",
                            analysis="Confuses normality with centrality.",
                            repair_suggestion="Compare gNg^-1 = N with gn = ng.",
                        ),
                        MistakeRecord(
                            session_id="session-002",
                            concept="quotient_group",
                            misconception_id="cosets_are_subgroups",
                            user_answer="Each coset is a subgroup.",
                            analysis="Confuses cosets with subgroups.",
                            repair_suggestion="Check whether arbitrary cosets contain the identity.",
                        ),
                    ],
                ),
            )
            resolve_active_misconceptions_for_concept(context, "normal_subgroup")

            status_result = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status_result.returncode, 0, status_result.stderr)
            self.assertIn("Active misconceptions: 1", status_result.stdout)
            self.assertIn("Resolved misconceptions: 1", status_result.stdout)

    def test_update_eval_report_scaffolds_allowed_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)

            report_path = update_eval_report(
                context,
                EvalReportUpdate(
                    report="tutoring",
                    subject="session-001",
                    score=0.78,
                    summary="Socratic hints stayed targeted.",
                    strengths=["Asked for definitions before examples."],
                    issues=["Could have checked quotient group prerequisites earlier."],
                    next_actions=["Add one diagnostic question on cosets."],
                ),
            )

            self.assertEqual(report_path, context.evals_dir / "tutoring_eval.md")
            report_text = report_path.read_text(encoding="utf-8")
            self.assertIn("# Tutoring Eval", report_text)
            self.assertIn("## session-001", report_text)
            self.assertIn("- Score: 0.78", report_text)
            self.assertIn("### Strengths", report_text)
            self.assertIn("- Asked for definitions before examples.", report_text)
            self.assertIn("### Issues", report_text)
            self.assertIn("- Could have checked quotient group prerequisites earlier.", report_text)
            self.assertIn("### Next Actions", report_text)

    def test_update_eval_report_rejects_unknown_report_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)

            with self.assertRaises(ValueError):
                update_eval_report(
                    context,
                    EvalReportUpdate(
                        report="ingestion",
                        subject="source-001",
                        score=1.0,
                        summary="Not part of this lane.",
                    ),
                )


if __name__ == "__main__":
    unittest.main()
