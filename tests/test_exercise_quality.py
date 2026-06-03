from __future__ import annotations

from datetime import date
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from socrates.artifacts import generate_exercise_drafts
from socrates.project import ProjectSpec, create_project


REPO_ROOT = Path(__file__).resolve().parents[1]


class ExerciseQualityTests(unittest.TestCase):
    def test_exercise_approve_cli_marks_draft_as_approved(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
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
                    "approve",
                    "--project",
                    str(project),
                    "--exercise",
                    "normal_subgroup_01",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Approved exercise normal_subgroup_01", result.stdout)
            approved = project / "05_exercises" / "generated" / "normal_subgroup_01.md"
            approved_text = approved.read_text(encoding="utf-8")
            self.assertIn('status: "approved"', approved_text)
            self.assertIn('review_status: "approved"', approved_text)
            self.assertIn("reviewed_by_user: true", approved_text)

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Approved exercises: 1", status.stdout)

    def test_exercise_attempt_cli_records_answer_for_approved_exercise(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "p"))
            answer = root / "answer.md"
            answer.write_text(
                "I would prove normality by checking gng^-1 remains in N.\n",
                encoding="utf-8",
                newline="\n",
            )
            generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="df-1",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )
            from socrates.exercises import approve_exercise_draft

            approve_exercise_draft(project, "normal_subgroup_01")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "exercise",
                    "attempt",
                    "--project",
                    str(project),
                    "--exercise",
                    "normal_subgroup_01",
                    "--answer",
                    str(answer),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Recorded attempt for exercise normal_subgroup_01", result.stdout)
            attempted = project / "05_exercises" / "attempted" / "normal_subgroup_01_attempt_001.md"
            attempt_text = attempted.read_text(encoding="utf-8")
            self.assertIn('exercise_id: "normal_subgroup_01"', attempt_text)
            self.assertIn('status: "attempted"', attempt_text)
            self.assertIn("I would prove normality", attempt_text)

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Attempted exercises: 1", status.stdout)

    def test_exercise_list_cli_shows_draft_approved_attempted_and_graded(self) -> None:
        from socrates.exercises import (
            approve_exercise_draft,
            grade_exercise_attempt,
            record_exercise_attempt,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "p"))
            answer = root / "answer.md"
            feedback = root / "feedback.md"
            answer.write_text(
                "Use conjugation invariance directly.\n",
                encoding="utf-8",
                newline="\n",
            )
            feedback.write_text("Correct core idea.\n", encoding="utf-8", newline="\n")
            generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="df-1",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )
            approve_exercise_draft(project, "normal_subgroup_01")
            approve_exercise_draft(project, "normal_subgroup_02")
            approve_exercise_draft(project, "normal_subgroup_03")
            record_exercise_attempt(project, "normal_subgroup_02", answer)
            record_exercise_attempt(project, "normal_subgroup_03", answer)
            grade_exercise_attempt(project, "normal_subgroup_03_attempt_001", 0.8, feedback)

            all_exercises = subprocess.run(
                [sys.executable, "-m", "socrates", "exercise", "list", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            attempted_exercises = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "exercise",
                    "list",
                    "--project",
                    str(project),
                    "--status",
                    "attempted",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            graded_exercises = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "exercise",
                    "list",
                    "--project",
                    str(project),
                    "--status",
                    "graded",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(all_exercises.returncode, 0, all_exercises.stderr)
            draft = (
                "- normal_subgroup_04 | draft | generated_exercise | Normal Subgroup | "
                "05_exercises/generated/normal_subgroup_04.md"
            )
            approved = (
                "- normal_subgroup_01 | approved | generated_exercise | Normal Subgroup | "
                "05_exercises/generated/normal_subgroup_01.md"
            )
            attempted = (
                "- normal_subgroup_02 | attempted | generated_exercise | Normal Subgroup | "
                "05_exercises/generated/normal_subgroup_02.md | attempt normal_subgroup_02_attempt_001"
            )
            graded = (
                "- normal_subgroup_03 | graded | generated_exercise | Normal Subgroup | "
                "05_exercises/generated/normal_subgroup_03.md | "
                "normal_subgroup_03_attempt_001, score 0.8"
            )
            self.assertIn("# Exercises", all_exercises.stdout)
            self.assertIn(draft, all_exercises.stdout)
            self.assertIn(approved, all_exercises.stdout)
            self.assertIn(attempted, all_exercises.stdout)
            self.assertIn(graded, all_exercises.stdout)
            self.assertLess(all_exercises.stdout.index(draft), all_exercises.stdout.index(approved))
            self.assertLess(all_exercises.stdout.index(approved), all_exercises.stdout.index(attempted))
            self.assertLess(all_exercises.stdout.index(attempted), all_exercises.stdout.index(graded))

            self.assertEqual(attempted_exercises.returncode, 0, attempted_exercises.stderr)
            self.assertIn(attempted, attempted_exercises.stdout)
            self.assertNotIn("normal_subgroup_01", attempted_exercises.stdout)
            self.assertNotIn("normal_subgroup_03", attempted_exercises.stdout)

            self.assertEqual(graded_exercises.returncode, 0, graded_exercises.stderr)
            self.assertIn(graded, graded_exercises.stdout)
            self.assertNotIn("normal_subgroup_01", graded_exercises.stdout)
            self.assertNotIn("normal_subgroup_02", graded_exercises.stdout)

    def test_record_exercise_attempt_rejects_unapproved_exercise(self) -> None:
        from socrates.exercises import record_exercise_attempt

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "p"))
            answer = root / "answer.md"
            answer.write_text("A first attempt.\n", encoding="utf-8", newline="\n")
            generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="df-1",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )

            with self.assertRaisesRegex(ValueError, "not approved"):
                record_exercise_attempt(project, "normal_subgroup_01", answer)

            attempted = project / "05_exercises" / "attempted" / "normal_subgroup_01_attempt_001.md"
            self.assertFalse(attempted.exists())

    def test_record_exercise_attempt_keeps_multiple_attempts(self) -> None:
        from socrates.exercises import approve_exercise_draft, record_exercise_attempt

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "p"))
            first_answer = root / "first_answer.md"
            second_answer = root / "second_answer.md"
            first_answer.write_text("First attempt.\n", encoding="utf-8", newline="\n")
            second_answer.write_text("Second attempt.\n", encoding="utf-8", newline="\n")
            generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="df-1",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )
            approve_exercise_draft(project, "normal_subgroup_01")

            first = record_exercise_attempt(project, "normal_subgroup_01", first_answer)
            second = record_exercise_attempt(project, "normal_subgroup_01", second_answer)

            self.assertEqual(first.name, "normal_subgroup_01_attempt_001.md")
            self.assertEqual(second.name, "normal_subgroup_01_attempt_002.md")
            self.assertIn("First attempt.", first.read_text(encoding="utf-8"))
            self.assertIn("Second attempt.", second.read_text(encoding="utf-8"))

    def test_exercise_grade_cli_writes_grade_and_updates_learning_state(self) -> None:
        from socrates.exercises import approve_exercise_draft, record_exercise_attempt

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "p"))
            answer = root / "answer.md"
            feedback = root / "feedback.md"
            answer.write_text(
                "I would prove normality by checking gng^-1 remains in N.\n",
                encoding="utf-8",
                newline="\n",
            )
            feedback.write_text(
                "Good use of conjugation invariance; subgroup closure still needs detail.\n",
                encoding="utf-8",
                newline="\n",
            )
            generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="df-1",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )
            approve_exercise_draft(project, "normal_subgroup_01")
            record_exercise_attempt(project, "normal_subgroup_01", answer)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "exercise",
                    "grade",
                    "--project",
                    str(project),
                    "--attempt",
                    "normal_subgroup_01_attempt_001",
                    "--score",
                    "0.8",
                    "--feedback",
                    str(feedback),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Graded attempt normal_subgroup_01_attempt_001", result.stdout)
            graded = project / "05_exercises" / "graded" / "normal_subgroup_01_attempt_001_grade.md"
            grade_text = graded.read_text(encoding="utf-8")
            self.assertIn('attempt_id: "normal_subgroup_01_attempt_001"', grade_text)
            self.assertIn('exercise_id: "normal_subgroup_01"', grade_text)
            self.assertIn("score: 0.8", grade_text)
            self.assertIn("Good use of conjugation invariance", grade_text)

            learning_state = json.loads(
                (project / "00_meta" / "learning_state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(learning_state["concept_mastery"]["normal_subgroup"], 0.8)
            self.assertEqual(learning_state["proof_skills"]["exercise_solving"], 0.8)

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Graded exercises: 1", status.stdout)

    def test_low_score_grade_cli_schedules_targeted_review(self) -> None:
        from socrates.exercises import approve_exercise_draft, record_exercise_attempt

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "p"))
            answer = root / "answer.md"
            feedback = root / "feedback.md"
            answer.write_text(
                "I treated normality as commutativity.\n",
                encoding="utf-8",
                newline="\n",
            )
            feedback.write_text(
                "This misses the conjugation condition.\n",
                encoding="utf-8",
                newline="\n",
            )
            generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="df-1",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )
            approve_exercise_draft(project, "normal_subgroup_01")
            record_exercise_attempt(project, "normal_subgroup_01", answer)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "exercise",
                    "grade",
                    "--project",
                    str(project),
                    "--attempt",
                    "normal_subgroup_01_attempt_001",
                    "--score",
                    "0.4",
                    "--feedback",
                    str(feedback),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            learning_state = json.loads(
                (project / "00_meta" / "learning_state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                learning_state["review_schedule"][0],
                {
                    "concept": "normal_subgroup",
                    "priority": "high",
                    "due": "next_session",
                    "scheduled_for": date.today().isoformat(),
                    "reason": "mastery 0.4",
                },
            )
            schedule_text = (project / "02_learning_plan" / "review_schedule.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("## normal_subgroup", schedule_text)
            self.assertIn("- Reason: mastery 0.4", schedule_text)

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Scheduled reviews: 1", status.stdout)

    def test_grade_cli_records_labeled_misconception_in_mistake_bank(self) -> None:
        from socrates.exercises import approve_exercise_draft, record_exercise_attempt

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "p"))
            answer = root / "answer.md"
            feedback = root / "feedback.md"
            answer.write_text(
                "I treated normality as elementwise commutativity.\n",
                encoding="utf-8",
                newline="\n",
            )
            feedback.write_text(
                "Use conjugation invariance instead of commutativity.\n",
                encoding="utf-8",
                newline="\n",
            )
            generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="df-1",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )
            approve_exercise_draft(project, "normal_subgroup_01")
            record_exercise_attempt(project, "normal_subgroup_01", answer)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "exercise",
                    "grade",
                    "--project",
                    str(project),
                    "--attempt",
                    "normal_subgroup_01_attempt_001",
                    "--score",
                    "0.35",
                    "--feedback",
                    str(feedback),
                    "--misconception",
                    "normal_equals_central",
                    "--analysis",
                    "Confuses normality with centrality or commutativity.",
                    "--repair-suggestion",
                    "Compare gNg^-1=N with gn=ng.",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            learning_state = json.loads(
                (project / "00_meta" / "learning_state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                learning_state["misconceptions"]["normal_equals_central"],
                {"concept": "normal_subgroup", "count": 1, "status": "active"},
            )
            self.assertEqual(
                learning_state["review_schedule"][0]["reason"],
                "mastery 0.35; active misconception normal_equals_central x1",
            )
            mistake_bank = (project / "05_exercises" / "mistake_bank.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("## normal_subgroup_01_attempt_001 - normal_subgroup", mistake_bank)
            self.assertIn("- Misconception: normal_equals_central", mistake_bank)
            self.assertIn(
                "- User answer: I treated normality as elementwise commutativity.",
                mistake_bank,
            )
            self.assertIn(
                "- Analysis: Confuses normality with centrality or commutativity.",
                mistake_bank,
            )
            self.assertIn("- Repair suggestion: Compare gNg^-1=N with gn=ng.", mistake_bank)
            self.assertIn("  - normal_subgroup_01", mistake_bank)

    def test_high_score_grade_cli_clears_existing_review_schedule(self) -> None:
        from socrates.context import load_project
        from socrates.exercises import approve_exercise_draft, record_exercise_attempt
        from socrates.state import LearningStatePatch, build_review_schedule, update_learning_state

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "p"))
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(concept_mastery={"normal_subgroup": 0.4}),
            )
            build_review_schedule(context)
            answer = root / "answer.md"
            feedback = root / "feedback.md"
            answer.write_text(
                "I checked conjugation invariance directly.\n",
                encoding="utf-8",
                newline="\n",
            )
            feedback.write_text(
                "This resolves the scheduled review item.\n",
                encoding="utf-8",
                newline="\n",
            )
            generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="df-1",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )
            approve_exercise_draft(project, "normal_subgroup_01")
            record_exercise_attempt(project, "normal_subgroup_01", answer)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "exercise",
                    "grade",
                    "--project",
                    str(project),
                    "--attempt",
                    "normal_subgroup_01_attempt_001",
                    "--score",
                    "0.8",
                    "--feedback",
                    str(feedback),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            learning_state = json.loads(
                (project / "00_meta" / "learning_state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(learning_state["concept_mastery"]["normal_subgroup"], 0.8)
            self.assertEqual(learning_state["review_schedule"], [])
            schedule_text = (project / "02_learning_plan" / "review_schedule.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("No review items scheduled.", schedule_text)

            queue = subprocess.run(
                [sys.executable, "-m", "socrates", "queue", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(queue.returncode, 0, queue.stderr)
            self.assertIn("## Scheduled Reviews\n\n- none", queue.stdout)
            self.assertNotIn("- normal_subgroup | 02_learning_plan/review_schedule.md", queue.stdout)

    def test_high_score_targeted_review_grade_resolves_active_misconception(self) -> None:
        from socrates.artifacts import generate_targeted_review_exercise_drafts
        from socrates.context import load_project
        from socrates.exercises import approve_exercise_draft, record_exercise_attempt
        from socrates.state import (
            LearningStatePatch,
            MistakeRecord,
            build_review_schedule,
            update_learning_state,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "p"))
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
                            user_answer="Normal subgroups are central.",
                            analysis="Confuses normality with centrality.",
                            repair_suggestion="Use conjugation rather than commutativity.",
                        )
                    ],
                ),
            )
            build_review_schedule(context)
            generate_targeted_review_exercise_drafts(project)
            approve_exercise_draft(project, "review_normal_subgroup_01")
            answer = root / "answer.md"
            feedback = root / "feedback.md"
            answer.write_text(
                "Normality asks for gNg^-1=N, not elementwise commutativity.\n",
                encoding="utf-8",
                newline="\n",
            )
            feedback.write_text(
                "The misconception is resolved for this review item.\n",
                encoding="utf-8",
                newline="\n",
            )
            record_exercise_attempt(project, "review_normal_subgroup_01", answer)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "exercise",
                    "grade",
                    "--project",
                    str(project),
                    "--attempt",
                    "review_normal_subgroup_01_attempt_001",
                    "--score",
                    "0.85",
                    "--feedback",
                    str(feedback),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            learning_state = json.loads(
                (project / "00_meta" / "learning_state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                learning_state["misconceptions"]["normal_equals_central"]["status"],
                "resolved",
            )
            self.assertEqual(learning_state["review_schedule"], [])
            schedule_text = (project / "02_learning_plan" / "review_schedule.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("No review items scheduled.", schedule_text)

    def test_grade_exercise_attempt_rejects_missing_attempt(self) -> None:
        from socrates.exercises import grade_exercise_attempt

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "p"))
            feedback = root / "feedback.md"
            feedback.write_text("No attempt exists.\n", encoding="utf-8", newline="\n")

            with self.assertRaisesRegex(FileNotFoundError, "Attempt does not exist"):
                grade_exercise_attempt(project, "missing_attempt", 0.4, feedback)

    def test_approve_exercise_draft_rejects_failed_quality_gate(self) -> None:
        from socrates.exercises import approve_exercise_draft

        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            malformed = project / "05_exercises" / "generated" / "bad_exercise.md"
            malformed.write_text(
                "---\n"
                "status: draft\n"
                "review_status: needs_review\n"
                "type: generated_exercise\n"
                "concept: Bad Exercise\n"
                "---\n\n"
                "# Bad Exercise\n\n"
                "This exercise is missing required sections.\n",
                encoding="utf-8",
                newline="\n",
            )

            with self.assertRaisesRegex(ValueError, "failed quality gate"):
                approve_exercise_draft(project, "bad_exercise")

            text = malformed.read_text(encoding="utf-8")
            self.assertIn("status: draft", text)
            self.assertNotIn('status: "approved"', text)
            report = project / "08_evals" / "exercise_quality_eval.md"
            self.assertIn("bad_exercise.md: fail", report.read_text(encoding="utf-8"))

    def test_exercise_quality_requires_training_point_and_common_mistakes(self) -> None:
        from socrates.quality import exercise_quality_issues

        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            exercise = project / "05_exercises" / "generated" / "thin_exercise.md"
            exercise.write_text(
                "---\n"
                "status: draft\n"
                "review_status: needs_review\n"
                "type: generated_exercise\n"
                "concept: Normal Subgroup\n"
                "---\n\n"
                "# Thin Exercise\n\n"
                "## Statement\n\n"
                "Prove a basic fact.\n\n"
                "## Hints\n\n"
                "- Use the definition.\n\n"
                "## Solution Outline\n\n"
                "- Unfold the definition.\n\n"
                "## Rubric\n\n"
                "- Checks the right condition.\n",
                encoding="utf-8",
                newline="\n",
            )

            issues = exercise_quality_issues(exercise)

            self.assertIn("missing section Target Training Point", issues)
            self.assertIn("missing section Common Mistakes", issues)
            self.assertIn("missing hint ladder", issues)
            self.assertIn("missing structured solution steps", issues)
            self.assertIn("missing rubric point values", issues)

    def test_exercise_quality_rejects_rubric_points_that_do_not_sum_to_total(self) -> None:
        from socrates.quality import exercise_quality_issues

        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            exercise = project / "05_exercises" / "generated" / "bad_rubric.md"
            exercise.write_text(
                "---\n"
                "status: draft\n"
                "review_status: needs_review\n"
                "type: generated_exercise\n"
                "concept: Normal Subgroup\n"
                "---\n\n"
                "# Bad Rubric\n\n"
                "## Statement\n\n"
                "Prove a basic fact about normal subgroups.\n\n"
                "## Target Training Point\n\n"
                "Practice checking conjugation invariance explicitly.\n\n"
                "## Hints\n\n"
                "Hint 1: Recall the definition.\n"
                "Hint 2: Pick g in G and n in N.\n"
                "Hint 3: Show gng^-1 lies in N.\n\n"
                "## Solution Outline\n\n"
                "Step 1: State the subgroup condition.\n"
                "Step 2: Apply conjugation.\n"
                "Step 3: Conclude normality.\n\n"
                "## Rubric\n\n"
                "- Setup: 4 pts\n"
                "- Conjugation check: 4 pts\n"
                "- Conclusion: 1 pts\n"
                "- Clarity: 0 pts\n"
                "Total: 10 pts\n\n"
                "## Common Mistakes\n\n"
                "- Confusing normality with commutativity.\n",
                encoding="utf-8",
                newline="\n",
            )

            issues = exercise_quality_issues(exercise)

            self.assertIn("rubric point values do not sum to total", issues)

    def test_exercise_quality_rejects_duplicate_hint_ladder_steps(self) -> None:
        from socrates.quality import exercise_quality_issues

        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            exercise = project / "05_exercises" / "generated" / "flat_hints.md"
            exercise.write_text(
                "---\n"
                "status: draft\n"
                "review_status: needs_review\n"
                "type: generated_exercise\n"
                "concept: Normal Subgroup\n"
                "---\n\n"
                "# Flat Hints\n\n"
                "## Statement\n\n"
                "Prove a basic fact about normal subgroups.\n\n"
                "## Target Training Point\n\n"
                "Practice checking conjugation invariance explicitly.\n\n"
                "## Hints\n\n"
                "Hint 1: Use the definition of normal subgroup.\n"
                "Hint 2: Use the definition of normal subgroup.\n"
                "Hint 3: Use the definition of normal subgroup.\n\n"
                "## Solution Outline\n\n"
                "Step 1: State the subgroup condition.\n"
                "Step 2: Apply conjugation.\n"
                "Step 3: Conclude normality.\n\n"
                "## Rubric\n\n"
                "- Setup: 3 pts\n"
                "- Conjugation check: 4 pts\n"
                "- Conclusion: 3 pts\n"
                "Total: 10 pts\n\n"
                "## Common Mistakes\n\n"
                "- Confusing normality with commutativity.\n",
                encoding="utf-8",
                newline="\n",
            )

            issues = exercise_quality_issues(exercise)

            self.assertIn("non-progressive hint ladder", issues)

    def test_exercise_check_cli_writes_quality_report_for_generated_exercises(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
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
                    "check",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Checked 5 exercise drafts: 5 passed, 0 failed", result.stdout)
            self.assertIn("Exercise quality manifest:", result.stdout)
            report = project / "08_evals" / "exercise_quality_eval.md"
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("# Exercise Quality Eval", report_text)
            self.assertIn("## Summary", report_text)
            self.assertIn("- Drafts checked: 5", report_text)
            self.assertIn("- Passed: 5", report_text)
            self.assertIn("- Failed: 0", report_text)
            self.assertIn("normal_subgroup_01.md: pass", report_text)
            manifest = json.loads(
                (project / "08_evals" / "exercise_quality_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual(manifest["checked"], 5)
            self.assertEqual(manifest["passed"], 5)
            self.assertEqual(manifest["failed"], 0)
            self.assertEqual(manifest["exercises"][0]["id"], "normal_subgroup_01")
            self.assertEqual(
                manifest["exercises"][0]["frontmatter"]["concept"],
                "Normal Subgroup",
            )
            self.assertEqual(manifest["exercises"][0]["sections"]["hint_count"], 3)
            self.assertEqual(
                manifest["exercises"][0]["counterexample_search"]["status"],
                "not_run",
            )

    def test_exercise_check_cli_reports_reference_counterexample_candidates(self) -> None:
        from socrates.kb import build_reference_kb

        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "counterexamples.curated.md"
            curated.write_text(
                "### Definition: Normal Subgroup\n"
                "A normal subgroup is stable under conjugation.\n"
                "Depends: subgroup, conjugation\n"
                "### Counterexample: Subgroup That Is Not Normal\n"
                "In S3, a subgroup generated by a transposition is not normal.\n"
                "Depends: normal subgroup, conjugation\n",
                encoding="utf-8",
                newline="\n",
            )
            build_reference_kb(project)
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
                    "check",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Checked 5 exercise drafts: 5 passed, 0 failed", result.stdout)
            report_text = (project / "08_evals" / "exercise_quality_eval.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("## Counterexample Search", report_text)
            self.assertIn(
                "- normal_subgroup_01.md | Normal Subgroup | searched | matches: 1",
                report_text,
            )
            self.assertIn(
                "counterexample: Subgroup That Is Not Normal "
                "(01_references/curated/counterexamples.curated.md:4)",
                report_text,
            )
            manifest = json.loads(
                (project / "08_evals" / "exercise_quality_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            first_exercise = manifest["exercises"][0]
            self.assertEqual(first_exercise["quality_status"], "pass")
            self.assertEqual(
                first_exercise["counterexample_search"]["status"],
                "searched",
            )
            self.assertEqual(first_exercise["counterexample_search"]["match_count"], 1)
            self.assertEqual(
                first_exercise["counterexample_search"]["matches"][0],
                {
                    "id": "subgroup_that_is_not_normal",
                    "type": "counterexample",
                    "title": "Subgroup That Is Not Normal",
                    "source_path": "01_references/curated/counterexamples.curated.md",
                    "line": 4,
                },
            )

    def test_exercise_check_cli_reports_linked_tool_verification_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="df-1",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )
            _write_linked_sage_tool_record(project)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "exercise",
                    "check",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report_text = (project / "08_evals" / "exercise_quality_eval.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("## Tool Verification Evidence", report_text)
            self.assertIn(
                (
                    "- normal_subgroup_01.md | linked | records: 1 | "
                    "quality: not_run (tool-verification check not run)"
                ),
                report_text,
            )
            self.assertIn(
                "sage_group_order_check | verified | 08_evals/tool_verification/"
                "normal_subgroup_01_sage_order.json",
                report_text,
            )
            manifest = json.loads(
                (project / "08_evals" / "exercise_quality_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            first_exercise = manifest["exercises"][0]
            self.assertEqual(first_exercise["id"], "normal_subgroup_01")
            self.assertEqual(first_exercise["tool_verification"]["status"], "linked")
            self.assertEqual(first_exercise["tool_verification"]["record_count"], 1)
            self.assertEqual(first_exercise["tool_verification"]["quality_status"], "not_run")
            self.assertEqual(
                first_exercise["tool_verification"]["quality_reason"],
                "tool-verification check not run",
            )
            self.assertEqual(
                first_exercise["tool_verification"]["records"][0],
                {
                    "kind": "sage_group_order_check",
                    "status": "verified",
                    "artifact_path": (
                        "08_evals/tool_verification/normal_subgroup_01_sage_order.json"
                    ),
                    "report_path": (
                        "08_evals/tool_verification/"
                        "normal_subgroup_01_sage_order_report.md"
                    ),
                },
            )

    def test_exercise_check_cli_reports_tool_verification_quality_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="df-1",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )
            _write_linked_sage_tool_record(project)
            _write_sage_tool_quality_manifest(project)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "exercise",
                    "check",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report_text = (project / "08_evals" / "exercise_quality_eval.md").read_text(
                encoding="utf-8"
            )
            self.assertIn(
                "- normal_subgroup_01.md | linked | records: 1 | quality: pass",
                report_text,
            )
            manifest = json.loads(
                (project / "08_evals" / "exercise_quality_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            first_exercise = manifest["exercises"][0]
            self.assertEqual(first_exercise["tool_verification"]["quality_status"], "pass")
            self.assertEqual(
                first_exercise["tool_verification"]["quality_records"][0],
                {
                    "kind": "sage_group_order_check",
                    "record_status": "verified",
                    "quality_status": "pass",
                    "artifact_path": (
                        "08_evals/tool_verification/normal_subgroup_01_sage_order.json"
                    ),
                    "report_path": (
                        "08_evals/tool_verification/"
                        "normal_subgroup_01_sage_order_report.md"
                    ),
                    "artifact_fingerprint": _fingerprint(
                        project / "08_evals" / "tool_verification"
                        / "normal_subgroup_01_sage_order.json"
                    ),
                    "report_fingerprint": _fingerprint(
                        project / "08_evals" / "tool_verification"
                        / "normal_subgroup_01_sage_order_report.md"
                    ),
                    "issues": [],
                },
            )

    def test_exercise_check_cli_marks_stale_tool_verification_quality(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="df-1",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )
            _write_linked_sage_tool_record(project)
            quality_manifest = _write_sage_tool_quality_manifest(
                project,
                include_source_manifest_fingerprint=False,
            )
            source_manifest = project / "08_evals" / "tool_verification" / "manifest.json"
            os.utime(quality_manifest, (1000, 1000))
            os.utime(source_manifest, (2000, 2000))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "exercise",
                    "check",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report_text = (project / "08_evals" / "exercise_quality_eval.md").read_text(
                encoding="utf-8"
            )
            self.assertIn(
                (
                    "- normal_subgroup_01.md | linked | records: 1 | "
                    "quality: stale (tool-verification check is older than source manifest)"
                ),
                report_text,
            )
            manifest = json.loads(
                (project / "08_evals" / "exercise_quality_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            first_exercise = manifest["exercises"][0]
            self.assertEqual(first_exercise["tool_verification"]["quality_status"], "stale")
            self.assertEqual(
                first_exercise["tool_verification"]["quality_reason"],
                "tool-verification check is older than source manifest",
            )

    def test_exercise_check_cli_marks_changed_tool_manifest_fingerprint_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="df-1",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )
            _write_linked_sage_tool_record(project)
            quality_manifest = _write_sage_tool_quality_manifest(
                project,
                source_manifest_fingerprint={
                    "algorithm": "sha256",
                    "value": "stale-fingerprint",
                },
            )
            source_manifest = project / "08_evals" / "tool_verification" / "manifest.json"
            os.utime(source_manifest, (1000, 1000))
            os.utime(quality_manifest, (2000, 2000))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "exercise",
                    "check",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report_text = (project / "08_evals" / "exercise_quality_eval.md").read_text(
                encoding="utf-8"
            )
            self.assertIn(
                (
                    "- normal_subgroup_01.md | linked | records: 1 | "
                    "quality: stale (tool-verification source manifest fingerprint changed)"
                ),
                report_text,
            )
            manifest = json.loads(
                (project / "08_evals" / "exercise_quality_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            first_exercise = manifest["exercises"][0]
            self.assertEqual(first_exercise["tool_verification"]["quality_status"], "stale")
            self.assertEqual(
                first_exercise["tool_verification"]["quality_reason"],
                "tool-verification source manifest fingerprint changed",
            )

    def test_exercise_check_cli_marks_changed_tool_artifact_fingerprint_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="df-1",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )
            _write_linked_sage_tool_record(project)
            _write_sage_tool_quality_manifest(project)
            artifact_path = (
                project
                / "08_evals"
                / "tool_verification"
                / "normal_subgroup_01_sage_order.json"
            )
            artifact_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "kind": "sage_group_order_check",
                        "object_id": "normal_subgroup_01",
                        "status": "verified",
                        "passed": False,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "exercise",
                    "check",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report_text = (project / "08_evals" / "exercise_quality_eval.md").read_text(
                encoding="utf-8"
            )
            self.assertIn(
                (
                    "- normal_subgroup_01.md | linked | records: 1 | "
                    "quality: stale (tool-verification artifact fingerprint changed)"
                ),
                report_text,
            )
            manifest = json.loads(
                (project / "08_evals" / "exercise_quality_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            first_exercise = manifest["exercises"][0]
            self.assertEqual(first_exercise["tool_verification"]["quality_status"], "stale")
            self.assertEqual(
                first_exercise["tool_verification"]["quality_reason"],
                "tool-verification artifact fingerprint changed",
            )

    def test_exercise_check_cli_reports_all_tool_record_drift_reasons(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="df-1",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )
            _write_linked_sage_tool_record(project)
            _write_sage_tool_quality_manifest(project)
            artifact_path = (
                project
                / "08_evals"
                / "tool_verification"
                / "normal_subgroup_01_sage_order.json"
            )
            artifact_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "kind": "sage_group_order_check",
                        "object_id": "normal_subgroup_01",
                        "status": "verified",
                        "passed": False,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            report_path = (
                project
                / "08_evals"
                / "tool_verification"
                / "normal_subgroup_01_sage_order_report.md"
            )
            report_path.write_text(
                "# Tool Verification: Mutated Report\n\n",
                encoding="utf-8",
                newline="\n",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "exercise",
                    "check",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report_text = (project / "08_evals" / "exercise_quality_eval.md").read_text(
                encoding="utf-8"
            )
            self.assertIn(
                (
                    "- normal_subgroup_01.md | linked | records: 1 | quality: stale "
                    "(tool-verification artifact fingerprint changed; "
                    "tool-verification report fingerprint changed)"
                ),
                report_text,
            )
            manifest = json.loads(
                (project / "08_evals" / "exercise_quality_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            first_exercise = manifest["exercises"][0]
            self.assertEqual(
                first_exercise["tool_verification"]["quality_reasons"],
                [
                    "tool-verification artifact fingerprint changed",
                    "tool-verification report fingerprint changed",
                ],
            )
            self.assertEqual(
                first_exercise["tool_verification"]["quality_reason"],
                "tool-verification artifact fingerprint changed",
            )


def _write_linked_sage_tool_record(project: Path) -> None:
    verification_dir = project / "08_evals" / "tool_verification"
    artifact_path = verification_dir / "normal_subgroup_01_sage_order.json"
    report_path = verification_dir / "normal_subgroup_01_sage_order_report.md"
    artifact_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "kind": "sage_group_order_check",
                "object_id": "normal_subgroup_01",
                "status": "verified",
                "passed": True,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    report_path.write_text(
        "# Tool Verification: Sage Group Order Check\n\n",
        encoding="utf-8",
        newline="\n",
    )
    (verification_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "records": [
                    {
                        "kind": "sage_group_order_check",
                        "object_id": "normal_subgroup_01",
                        "object_type": "finite_group_order",
                        "title": "Normal Subgroup Exercise 01",
                        "status": "verified",
                        "artifact_path": (
                            "08_evals/tool_verification/"
                            "normal_subgroup_01_sage_order.json"
                        ),
                        "report_path": (
                            "08_evals/tool_verification/"
                            "normal_subgroup_01_sage_order_report.md"
                        ),
                        "source": {"tool": "sage"},
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_sage_tool_quality_manifest(
    project: Path,
    *,
    include_source_manifest_fingerprint: bool = True,
    source_manifest_fingerprint: dict[str, str] | None = None,
) -> Path:
    manifest_path = project / "08_evals" / "tool_verification_quality_manifest.json"
    source_manifest = project / "08_evals" / "tool_verification" / "manifest.json"
    if source_manifest_fingerprint is None:
        source_manifest_fingerprint = {
            "algorithm": "sha256",
            "value": hashlib.sha256(source_manifest.read_bytes()).hexdigest(),
        }
    source_manifest_fields: dict[str, object] = {
        "source_manifest": "08_evals/tool_verification/manifest.json"
    }
    if include_source_manifest_fingerprint:
        source_manifest_fields["source_manifest_fingerprint"] = source_manifest_fingerprint
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "status": "pass",
                "checked": 1,
                "passed": 1,
                "failed": 0,
                **source_manifest_fields,
                "records": [
                    {
                        "object_id": "normal_subgroup_01",
                        "kind": "sage_group_order_check",
                        "record_status": "verified",
                        "quality_status": "pass",
                        "artifact_path": (
                            "08_evals/tool_verification/"
                            "normal_subgroup_01_sage_order.json"
                        ),
                        "report_path": (
                            "08_evals/tool_verification/"
                            "normal_subgroup_01_sage_order_report.md"
                        ),
                        "artifact_fingerprint": _fingerprint(
                            project / "08_evals" / "tool_verification"
                            / "normal_subgroup_01_sage_order.json"
                        ),
                        "report_fingerprint": _fingerprint(
                            project / "08_evals" / "tool_verification"
                            / "normal_subgroup_01_sage_order_report.md"
                        ),
                        "issues": [],
                    }
                ],
                "issues": [],
                "verification_boundary": {
                    "external_verifier_invoked": False,
                    "unchecked_skeleton_policy": "scaffold_only_not_proof",
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest_path


def _fingerprint(path: Path) -> dict[str, str]:
    return {"algorithm": "sha256", "value": hashlib.sha256(path.read_bytes()).hexdigest()}


if __name__ == "__main__":
    unittest.main()
