from __future__ import annotations

from datetime import date
import json
import math
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
                {
                    "concept": "normal_subgroup",
                    "count": 1,
                    "status": "active",
                    "last_session_id": "session-001",
                    "analysis": "Confuses normality with centrality.",
                    "repair_suggestion": "Compare gNg^-1 = N with gn = ng.",
                    "follow_up_exercises": ["Find a non-central normal subgroup."],
                },
            )

            mistake_bank = context.mistake_bank.read_text(encoding="utf-8")
            self.assertIn("## session-001 - normal_subgroup", mistake_bank)
            self.assertIn("- Misconception: normal_equals_central", mistake_bank)
            self.assertIn("- Recurrence: no", mistake_bank)
            self.assertIn("- Follow-up exercises:", mistake_bank)
            self.assertIn("  - Find a non-central normal subgroup.", mistake_bank)

    def test_update_learning_state_rejects_nonfinite_scores_without_writing_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            original_state = context.learning_state.read_text(encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Learning state score must be finite"):
                update_learning_state(
                    context,
                    LearningStatePatch(
                        concept_mastery={"normal_subgroup": math.nan},
                        proof_skills={"exercise_solving": 0.8},
                    ),
                )

            self.assertEqual(context.learning_state.read_text(encoding="utf-8"), original_state)

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
            self.assertEqual(
                learning_state["misconceptions"]["normal_equals_central"]["last_session_id"],
                "session-002",
            )
            self.assertEqual(
                learning_state["misconceptions"]["normal_equals_central"]["analysis"],
                "Same confusion recurred.",
            )
            self.assertEqual(
                learning_state["misconceptions"]["normal_equals_central"]["repair_suggestion"],
                "Contrast center Z(G) with normal subgroups.",
            )
            mistake_bank = context.mistake_bank.read_text(encoding="utf-8")
            self.assertIn("## session-002 - normal_subgroup", mistake_bank)
            self.assertIn("- Recurrence: yes", mistake_bank)

    def test_update_learning_state_recovers_malformed_existing_misconception_count(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            context.learning_state.write_text(
                json.dumps(
                    {
                        "concept_mastery": {},
                        "proof_skills": {},
                        "misconceptions": {
                            "normal_equals_central": {
                                "concept": "normal_subgroup",
                                "count": "many",
                                "status": "active",
                                "last_session_id": "session-001",
                                "analysis": "Prior malformed count.",
                                "repair_suggestion": "Compare normality with centrality.",
                                "follow_up_exercises": [],
                            }
                        },
                        "review_schedule": [],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )

            update_learning_state(
                context,
                LearningStatePatch(
                    mistakes=[
                        MistakeRecord(
                            session_id="session-002",
                            concept="normal_subgroup",
                            misconception_id="normal_equals_central",
                            user_answer="Normal still means central.",
                            analysis="The same confusion recurred.",
                            repair_suggestion="Use conjugation instead of commutativity.",
                        )
                    ]
                ),
            )

            learning_state = json.loads(context.learning_state.read_text(encoding="utf-8"))
            self.assertEqual(
                learning_state["misconceptions"]["normal_equals_central"]["count"],
                2,
            )
            self.assertEqual(
                learning_state["misconceptions"]["normal_equals_central"]["last_session_id"],
                "session-002",
            )
            mistake_bank = context.mistake_bank.read_text(encoding="utf-8")
            self.assertIn("## session-002 - normal_subgroup", mistake_bank)
            self.assertIn("- Recurrence: yes", mistake_bank)

    def test_resolving_misconception_appends_repair_entry_to_mistake_bank(self) -> None:
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
                            repair_suggestion="Use conjugation rather than commutativity.",
                        )
                    ],
                ),
            )

            resolved = resolve_active_misconceptions_for_concept(context, "normal_subgroup")

            self.assertEqual(resolved, 1)
            mistake_bank = context.mistake_bank.read_text(encoding="utf-8")
            self.assertIn("## resolved - normal_subgroup", mistake_bank)
            self.assertIn("- Misconception: normal_equals_central", mistake_bank)
            self.assertIn("- Status: resolved", mistake_bank)

    def test_review_resolve_cli_marks_concept_misconceptions_resolved(self) -> None:
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
                            repair_suggestion="Compare normality with commutativity.",
                        ),
                        MistakeRecord(
                            session_id="session-002",
                            concept="quotient_group",
                            misconception_id="cosets_are_subgroups",
                            user_answer="Every coset is a subgroup.",
                            analysis="Confuses cosets with subgroups.",
                            repair_suggestion="Check whether a coset contains the identity.",
                        ),
                    ],
                ),
            )

            resolve = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "resolve",
                    "--project",
                    str(project),
                    "--concept",
                    "normal_subgroup",
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

            self.assertEqual(resolve.returncode, 0, resolve.stderr)
            self.assertIn(
                "Resolved 1 active misconception for normal_subgroup",
                resolve.stdout,
            )
            learning_state = json.loads(context.learning_state.read_text(encoding="utf-8"))
            self.assertEqual(
                learning_state["misconceptions"]["normal_equals_central"]["status"],
                "resolved",
            )
            self.assertEqual(
                learning_state["misconceptions"]["cosets_are_subgroups"]["status"],
                "active",
            )
            mistake_bank = context.mistake_bank.read_text(encoding="utf-8")
            self.assertIn("## resolved - normal_subgroup", mistake_bank)
            self.assertIn("- Misconception: normal_equals_central", mistake_bank)
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Active misconceptions: 1", status.stdout)
            self.assertIn("Resolved misconceptions: 1", status.stdout)

    def test_review_resolve_cli_accepts_title_case_concept_names(self) -> None:
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
                            repair_suggestion="Compare normality with commutativity.",
                        )
                    ],
                ),
            )

            resolve = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "resolve",
                    "--project",
                    str(project),
                    "--concept",
                    "Normal Subgroup",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(resolve.returncode, 0, resolve.stderr)
            self.assertIn(
                "Resolved 1 active misconception for Normal Subgroup",
                resolve.stdout,
            )
            learning_state = json.loads(context.learning_state.read_text(encoding="utf-8"))
            self.assertEqual(
                learning_state["misconceptions"]["normal_equals_central"]["status"],
                "resolved",
            )

    def test_review_resolve_json_marks_concept_misconceptions_resolved(self) -> None:
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
                            repair_suggestion="Compare normality with commutativity.",
                            follow_up_exercises=["normal_subgroup_review_01"],
                        ),
                        MistakeRecord(
                            session_id="session-002",
                            concept="quotient_group",
                            misconception_id="cosets_are_subgroups",
                            user_answer="Every coset is a subgroup.",
                            analysis="Confuses cosets with subgroups.",
                            repair_suggestion="Check whether a coset contains the identity.",
                        ),
                    ],
                ),
            )

            resolve = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "resolve",
                    "--project",
                    str(project),
                    "--concept",
                    "normal_subgroup",
                    "--json",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(resolve.returncode, 0, resolve.stderr)
            self.assertNotIn("Resolved 1 active misconception", resolve.stdout)
            payload = json.loads(resolve.stdout)
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(
                payload["quality_boundary"],
                "deterministic_misconception_resolver",
            )
            self.assertEqual(payload["project"], str(project))
            self.assertEqual(payload["concept"], "normal_subgroup")
            self.assertEqual(payload["resolved_count"], 1)
            self.assertEqual(
                payload["resolved_misconceptions"],
                [
                    {
                        "misconception_id": "normal_equals_central",
                        "concept": "normal_subgroup",
                        "previous_status": "active",
                        "status": "resolved",
                        "count": 1,
                        "last_session_id": "session-001",
                        "analysis": "Confuses normality with centrality.",
                        "repair_suggestion": "Compare normality with commutativity.",
                        "follow_up_exercises": ["normal_subgroup_review_01"],
                    }
                ],
            )
            learning_state = json.loads(context.learning_state.read_text(encoding="utf-8"))
            self.assertEqual(
                learning_state["misconceptions"]["normal_equals_central"]["status"],
                "resolved",
            )
            self.assertEqual(
                learning_state["misconceptions"]["cosets_are_subgroups"]["status"],
                "active",
            )
            mistake_bank = context.mistake_bank.read_text(encoding="utf-8")
            self.assertIn("## resolved - normal_subgroup", mistake_bank)
            self.assertIn("- Misconception: normal_equals_central", mistake_bank)

    def test_review_resolve_json_reports_noop_without_writes(self) -> None:
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
                            repair_suggestion="Compare normality with commutativity.",
                        )
                    ],
                ),
            )
            learning_state_before = context.learning_state.read_text(encoding="utf-8")
            mistake_bank_before = context.mistake_bank.read_text(encoding="utf-8")

            resolve = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "resolve",
                    "--project",
                    str(project),
                    "--concept",
                    "rings",
                    "--json",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(resolve.returncode, 0, resolve.stderr)
            payload = json.loads(resolve.stdout)
            self.assertEqual(payload["concept"], "rings")
            self.assertEqual(payload["resolved_count"], 0)
            self.assertEqual(payload["resolved_misconceptions"], [])
            self.assertEqual(
                context.learning_state.read_text(encoding="utf-8"),
                learning_state_before,
            )
            self.assertEqual(
                context.mistake_bank.read_text(encoding="utf-8"),
                mistake_bank_before,
            )

    def test_review_resolve_json_rejects_corrupt_learning_state_without_mistake_bank_append(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            original_mistake_bank = context.mistake_bank.read_text(encoding="utf-8")
            context.learning_state.write_text(
                "{not valid json\n",
                encoding="utf-8",
                newline="\n",
            )

            resolve = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "resolve",
                    "--project",
                    str(project),
                    "--concept",
                    "normal_subgroup",
                    "--json",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(resolve.returncode, 1)
            self.assertEqual(resolve.stdout, "")
            self.assertIn("error: invalid learning_state.json", resolve.stderr)
            self.assertIn(
                "repair the JSON before resolving misconceptions",
                resolve.stderr,
            )
            self.assertNotIn("Expecting property name", resolve.stderr)
            self.assertEqual(
                context.mistake_bank.read_text(encoding="utf-8"),
                original_mistake_bank,
            )

    def test_status_cli_recovers_corrupt_learning_state_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            (project / "00_meta" / "learning_state.json").write_text(
                "{not valid json\n",
                encoding="utf-8",
                newline="\n",
            )

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Current phase: planning_complete", status.stdout)
            self.assertIn("Scheduled reviews: 0", status.stdout)
            self.assertIn("Active misconceptions: 0", status.stdout)
            self.assertIn("Resolved misconceptions: 0", status.stdout)
            self.assertNotIn("Traceback", status.stderr)
            self.assertNotIn("Expecting property name", status.stderr)

    def test_review_misconceptions_cli_lists_statuses_and_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            repeated = MistakeRecord(
                session_id="session-001",
                concept="normal_subgroup",
                misconception_id="normal_equals_central",
                user_answer="Normal means central.",
                analysis="Confuses normality with centrality.",
                repair_suggestion="Compare normality with conjugation.",
                follow_up_exercises=["normal_subgroup_review_01"],
            )
            update_learning_state(
                context,
                LearningStatePatch(
                    mistakes=[
                        repeated,
                        MistakeRecord(
                            session_id="session-002",
                            concept="quotient_group",
                            misconception_id="cosets_are_subgroups",
                            user_answer="Every coset is a subgroup.",
                            analysis="Confuses cosets with subgroups.",
                            repair_suggestion="Check whether the identity is present.",
                            follow_up_exercises=["quotient_group_review_01"],
                        ),
                    ],
                ),
            )
            update_learning_state(context, LearningStatePatch(mistakes=[repeated]))
            resolve_active_misconceptions_for_concept(context, "normal_subgroup")

            all_items = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "misconceptions",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            active_items = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "misconceptions",
                    "--project",
                    str(project),
                    "--status",
                    "active",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            resolved_items = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "misconceptions",
                    "--project",
                    str(project),
                    "--status",
                    "resolved",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            active_line = "- cosets_are_subgroups | active | quotient_group | x1"
            resolved_line = "- normal_equals_central | resolved | normal_subgroup | x2"
            self.assertEqual(all_items.returncode, 0, all_items.stderr)
            self.assertIn("# Misconceptions", all_items.stdout)
            self.assertIn(active_line, all_items.stdout)
            self.assertIn(resolved_line, all_items.stdout)
            self.assertIn("  - Last session: session-002", all_items.stdout)
            self.assertIn("  - Analysis: Confuses cosets with subgroups.", all_items.stdout)
            self.assertIn(
                "  - Repair suggestion: Check whether the identity is present.",
                all_items.stdout,
            )
            self.assertIn(
                "  - Follow-up exercises: quotient_group_review_01",
                all_items.stdout,
            )
            self.assertIn("  - Last session: session-001", all_items.stdout)
            self.assertIn(
                "  - Analysis: Confuses normality with centrality.",
                all_items.stdout,
            )
            self.assertIn(
                "  - Repair suggestion: Compare normality with conjugation.",
                all_items.stdout,
            )
            self.assertIn(
                "  - Follow-up exercises: normal_subgroup_review_01",
                all_items.stdout,
            )
            self.assertLess(
                all_items.stdout.index(active_line),
                all_items.stdout.index(resolved_line),
            )

            self.assertEqual(active_items.returncode, 0, active_items.stderr)
            self.assertIn(active_line, active_items.stdout)
            self.assertNotIn("normal_equals_central", active_items.stdout)

            self.assertEqual(resolved_items.returncode, 0, resolved_items.stderr)
            self.assertIn(resolved_line, resolved_items.stdout)
            self.assertNotIn("cosets_are_subgroups", resolved_items.stdout)

    def test_review_misconceptions_json_lists_statuses_and_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            repeated = MistakeRecord(
                session_id="session-001",
                concept="normal_subgroup",
                misconception_id="normal_equals_central",
                user_answer="Normal means central.",
                analysis="Confuses normality with centrality.",
                repair_suggestion="Compare normality with conjugation.",
                follow_up_exercises=["normal_subgroup_review_01"],
            )
            update_learning_state(
                context,
                LearningStatePatch(
                    mistakes=[
                        repeated,
                        MistakeRecord(
                            session_id="session-002",
                            concept="quotient_group",
                            misconception_id="cosets_are_subgroups",
                            user_answer="Every coset is a subgroup.",
                            analysis="Confuses cosets with subgroups.",
                            repair_suggestion="Check whether the identity is present.",
                            follow_up_exercises=["quotient_group_review_01"],
                        ),
                    ],
                ),
            )
            update_learning_state(context, LearningStatePatch(mistakes=[repeated]))
            resolve_active_misconceptions_for_concept(context, "normal_subgroup")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "misconceptions",
                    "--project",
                    str(project),
                    "--json",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("# Misconceptions", result.stdout)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(
                payload["quality_boundary"],
                "deterministic_misconception_review",
            )
            self.assertEqual(payload["project"], str(project))
            self.assertEqual(payload["status_filter"], "all")
            self.assertEqual(payload["misconception_count"], 2)
            self.assertEqual(payload["active_count"], 1)
            self.assertEqual(payload["resolved_count"], 1)
            self.assertEqual(
                payload["misconceptions"],
                [
                    {
                        "misconception_id": "cosets_are_subgroups",
                        "status": "active",
                        "concept": "quotient_group",
                        "count": 1,
                        "last_session_id": "session-002",
                        "analysis": "Confuses cosets with subgroups.",
                        "repair_suggestion": "Check whether the identity is present.",
                        "follow_up_exercises": ["quotient_group_review_01"],
                    },
                    {
                        "misconception_id": "normal_equals_central",
                        "status": "resolved",
                        "concept": "normal_subgroup",
                        "count": 2,
                        "last_session_id": "session-001",
                        "analysis": "Confuses normality with centrality.",
                        "repair_suggestion": "Compare normality with conjugation.",
                        "follow_up_exercises": ["normal_subgroup_review_01"],
                    },
                ],
            )

    def test_review_misconceptions_json_filters_active_without_writes(self) -> None:
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
                            repair_suggestion="Compare normality with conjugation.",
                        ),
                        MistakeRecord(
                            session_id="session-002",
                            concept="quotient_group",
                            misconception_id="cosets_are_subgroups",
                            user_answer="Every coset is a subgroup.",
                            analysis="Confuses cosets with subgroups.",
                            repair_suggestion="Check whether the identity is present.",
                        ),
                    ],
                ),
            )
            resolve_active_misconceptions_for_concept(context, "normal_subgroup")
            learning_state_before = context.learning_state.read_text(encoding="utf-8")
            mistake_bank_before = context.mistake_bank.read_text(encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "misconceptions",
                    "--project",
                    str(project),
                    "--status",
                    "active",
                    "--json",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status_filter"], "active")
            self.assertEqual(payload["misconception_count"], 1)
            self.assertEqual(payload["active_count"], 1)
            self.assertEqual(payload["resolved_count"], 0)
            self.assertEqual(
                [
                    item["misconception_id"]
                    for item in payload["misconceptions"]
                ],
                ["cosets_are_subgroups"],
            )
            self.assertEqual(
                context.learning_state.read_text(encoding="utf-8"),
                learning_state_before,
            )
            self.assertEqual(
                context.mistake_bank.read_text(encoding="utf-8"),
                mistake_bank_before,
            )
            self.assertEqual(list((project / "04_atomic_notes" / "drafts").iterdir()), [])

    def test_review_misconceptions_cli_recovers_malformed_count(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            (project / "00_meta" / "learning_state.json").write_text(
                json.dumps(
                    {
                        "concept_mastery": {},
                        "proof_skills": {},
                        "misconceptions": {
                            "normal_equals_central": {
                                "concept": "normal_subgroup",
                                "count": "many",
                                "status": "active",
                                "last_session_id": "session-001",
                                "analysis": "Confuses normality with centrality.",
                                "repair_suggestion": "Compare normality with conjugation.",
                                "follow_up_exercises": [],
                            }
                        },
                        "review_schedule": [],
                    },
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
                    "review",
                    "misconceptions",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(
                "- normal_equals_central | active | normal_subgroup | x1",
                result.stdout,
            )
            self.assertNotIn("x0", result.stdout)
            self.assertNotIn("many", result.stdout)

    def test_review_mastery_cli_lists_learning_scores_with_filters(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(
                    concept_mastery={
                        "normal_subgroup": 0.42,
                        "subgroup": 0.82,
                    },
                    proof_skills={
                        "construct_counterexample": 0.35,
                        "unfold_definition": 0.86,
                    },
                ),
            )

            all_scores = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "mastery",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            weak_concepts = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "mastery",
                    "--project",
                    str(project),
                    "--kind",
                    "concept",
                    "--status",
                    "weak",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            ready_with_high_cutoff = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "mastery",
                    "--project",
                    str(project),
                    "--status",
                    "ready",
                    "--threshold",
                    "0.85",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            weak_concept = "- concept | normal_subgroup | weak | 0.42"
            weak_skill = "- proof_skill | construct_counterexample | weak | 0.35"
            ready_concept = "- concept | subgroup | ready | 0.82"
            ready_skill = "- proof_skill | unfold_definition | ready | 0.86"
            self.assertEqual(all_scores.returncode, 0, all_scores.stderr)
            self.assertIn("# Learning Mastery", all_scores.stdout)
            self.assertIn(weak_concept, all_scores.stdout)
            self.assertIn(weak_skill, all_scores.stdout)
            self.assertIn(ready_concept, all_scores.stdout)
            self.assertIn(ready_skill, all_scores.stdout)
            self.assertLess(
                all_scores.stdout.index(weak_concept),
                all_scores.stdout.index(ready_concept),
            )

            self.assertEqual(weak_concepts.returncode, 0, weak_concepts.stderr)
            self.assertIn(weak_concept, weak_concepts.stdout)
            self.assertNotIn("subgroup | ready", weak_concepts.stdout)
            self.assertNotIn("proof_skill", weak_concepts.stdout)

            self.assertEqual(ready_with_high_cutoff.returncode, 0, ready_with_high_cutoff.stderr)
            self.assertIn(ready_skill, ready_with_high_cutoff.stdout)
            self.assertNotIn("subgroup", ready_with_high_cutoff.stdout)
            self.assertNotIn("normal_subgroup", ready_with_high_cutoff.stdout)

    def test_review_mastery_json_lists_learning_scores_with_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(
                    concept_mastery={
                        "normal_subgroup": 0.42,
                        "subgroup": 0.82,
                    },
                    proof_skills={
                        "construct_counterexample": 0.35,
                        "unfold_definition": 0.86,
                    },
                ),
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "mastery",
                    "--project",
                    str(project),
                    "--json",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("# Learning Mastery", result.stdout)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(
                payload["quality_boundary"],
                "deterministic_learning_mastery_review",
            )
            self.assertEqual(payload["project"], str(project))
            self.assertEqual(payload["kind_filter"], "all")
            self.assertEqual(payload["status_filter"], "all")
            self.assertEqual(payload["threshold"], 0.7)
            self.assertEqual(payload["score_count"], 4)
            self.assertEqual(payload["weak_count"], 2)
            self.assertEqual(payload["ready_count"], 2)
            self.assertEqual(
                payload["scores"],
                [
                    {
                        "score_type": "concept",
                        "item_id": "normal_subgroup",
                        "status": "weak",
                        "score": 0.42,
                    },
                    {
                        "score_type": "proof_skill",
                        "item_id": "construct_counterexample",
                        "status": "weak",
                        "score": 0.35,
                    },
                    {
                        "score_type": "concept",
                        "item_id": "subgroup",
                        "status": "ready",
                        "score": 0.82,
                    },
                    {
                        "score_type": "proof_skill",
                        "item_id": "unfold_definition",
                        "status": "ready",
                        "score": 0.86,
                    },
                ],
            )

    def test_review_mastery_json_filters_weak_concepts_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(
                    concept_mastery={
                        "normal_subgroup": 0.42,
                        "subgroup": 0.82,
                    },
                    proof_skills={"construct_counterexample": 0.35},
                ),
            )
            learning_state_before = context.learning_state.read_text(encoding="utf-8")
            project_log_before = context.project_log.read_text(encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "mastery",
                    "--project",
                    str(project),
                    "--kind",
                    "concept",
                    "--status",
                    "weak",
                    "--threshold",
                    "0.8",
                    "--json",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["kind_filter"], "concept")
            self.assertEqual(payload["status_filter"], "weak")
            self.assertEqual(payload["threshold"], 0.8)
            self.assertEqual(payload["score_count"], 1)
            self.assertEqual(payload["weak_count"], 1)
            self.assertEqual(payload["ready_count"], 0)
            self.assertEqual(
                payload["scores"],
                [
                    {
                        "score_type": "concept",
                        "item_id": "normal_subgroup",
                        "status": "weak",
                        "score": 0.42,
                    }
                ],
            )
            self.assertEqual(
                context.learning_state.read_text(encoding="utf-8"),
                learning_state_before,
            )
            self.assertEqual(context.project_log.read_text(encoding="utf-8"), project_log_before)
            self.assertEqual(list((project / "04_atomic_notes" / "drafts").iterdir()), [])

    def test_review_mastery_cli_rejects_nonfinite_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(concept_mastery={"normal_subgroup": 0.42}),
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "mastery",
                    "--project",
                    str(project),
                    "--threshold",
                    "nan",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertIn("error: Review mastery threshold must be finite", result.stderr)

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
                follow_up_exercises=["normal_subgroup_review_01"],
            )

            update_learning_state(
                context,
                LearningStatePatch(
                    concept_mastery={"normal_subgroup": 0.41, "subgroup": 0.82},
                    mistakes=[mistake],
                ),
            )
            update_learning_state(context, LearningStatePatch(mistakes=[mistake]))

            schedule_path = build_review_schedule(context, as_of=date(2026, 6, 4))

            self.assertEqual(schedule_path, project / "02_learning_plan" / "review_schedule.md")
            schedule_text = schedule_path.read_text(encoding="utf-8")
            self.assertIn("# Review Schedule", schedule_text)
            self.assertIn("## normal_subgroup", schedule_text)
            self.assertIn("- Priority: high", schedule_text)
            self.assertIn("- Due: next_session", schedule_text)
            self.assertIn("- Scheduled for: 2026-06-04", schedule_text)
            self.assertIn("- Reason: mastery 0.41; active misconception normal_equals_central x2", schedule_text)
            self.assertIn("### Repair Context", schedule_text)
            self.assertIn("- Misconception: normal_equals_central (x2)", schedule_text)
            self.assertIn("  - Last session: session-001", schedule_text)
            self.assertIn("  - Analysis: Confuses normality with centrality.", schedule_text)
            self.assertIn(
                "  - Repair suggestion: Compare normality with the center.",
                schedule_text,
            )
            self.assertIn("  - Follow-up exercises: normal_subgroup_review_01", schedule_text)
            self.assertNotIn("## subgroup", schedule_text)

            learning_state = json.loads(context.learning_state.read_text(encoding="utf-8"))
            self.assertEqual(
                learning_state["review_schedule"][0],
                {
                    "concept": "normal_subgroup",
                    "priority": "high",
                    "due": "next_session",
                    "scheduled_for": "2026-06-04",
                    "reason": "mastery 0.41; active misconception normal_equals_central x2",
                    "repair_context": [
                        {
                            "misconception_id": "normal_equals_central",
                            "count": 2,
                            "last_session_id": "session-001",
                            "analysis": "Confuses normality with centrality.",
                            "repair_suggestion": "Compare normality with the center.",
                            "follow_up_exercises": ["normal_subgroup_review_01"],
                        }
                    ],
                },
            )

    def test_review_schedule_dates_medium_priority_items_three_days_out(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(concept_mastery={"quotient_group": 0.62}),
            )

            build_review_schedule(context, as_of=date(2026, 6, 4))

            learning_state = json.loads(context.learning_state.read_text(encoding="utf-8"))
            self.assertEqual(
                learning_state["review_schedule"][0],
                {
                    "concept": "quotient_group",
                    "priority": "medium",
                    "due": "within_3_days",
                    "scheduled_for": "2026-06-07",
                    "reason": "mastery 0.62",
                },
            )
            schedule_text = (project / "02_learning_plan" / "review_schedule.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("- Scheduled for: 2026-06-07", schedule_text)

    def test_review_schedule_orders_items_by_scheduled_date(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(
                    concept_mastery={
                        "alpha_medium_review": 0.62,
                        "zeta_urgent_review": 0.4,
                    }
                ),
            )

            build_review_schedule(context, as_of=date(2026, 6, 4))

            learning_state = json.loads(context.learning_state.read_text(encoding="utf-8"))
            self.assertEqual(
                [item["concept"] for item in learning_state["review_schedule"]],
                ["zeta_urgent_review", "alpha_medium_review"],
            )
            schedule_text = (project / "02_learning_plan" / "review_schedule.md").read_text(
                encoding="utf-8"
            )
            self.assertLess(
                schedule_text.index("## zeta_urgent_review"),
                schedule_text.index("## alpha_medium_review"),
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

    def test_status_shows_next_review_repair_guidance(self) -> None:
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
                        )
                    ],
                ),
            )
            build_review_schedule(context, as_of=date(2026, 6, 4))

            status_result = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status_result.returncode, 0, status_result.stderr)
            self.assertIn(
                (
                    "Next review: normal_subgroup | 2026-06-07 | medium | "
                    "active misconception normal_equals_central x1"
                ),
                status_result.stdout,
            )
            self.assertIn(
                "Next repair: Compare gNg^-1 = N with gn = ng.",
                status_result.stdout,
            )

    def test_review_schedule_cli_accepts_threshold_and_as_of_date(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(
                    concept_mastery={
                        "normal_subgroup": 0.62,
                        "quotient_group": 0.74,
                        "subgroup": 0.84,
                    }
                ),
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
                    "--threshold",
                    "0.8",
                    "--as-of",
                    "2026-06-04",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(schedule_result.returncode, 0, schedule_result.stderr)
            self.assertIn("Scheduled 2 review items:", schedule_result.stdout)
            learning_state = json.loads(context.learning_state.read_text(encoding="utf-8"))
            self.assertEqual(
                learning_state["review_schedule"],
                [
                    {
                        "concept": "normal_subgroup",
                        "priority": "medium",
                        "due": "within_3_days",
                        "scheduled_for": "2026-06-07",
                        "reason": "mastery 0.62",
                    },
                    {
                        "concept": "quotient_group",
                        "priority": "medium",
                        "due": "within_3_days",
                        "scheduled_for": "2026-06-07",
                        "reason": "mastery 0.74",
                    },
                ],
            )
            schedule_text = (project / "02_learning_plan" / "review_schedule.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("## normal_subgroup", schedule_text)
            self.assertIn("## quotient_group", schedule_text)
            self.assertNotIn("## subgroup", schedule_text)
            self.assertIn("- Scheduled for: 2026-06-07", schedule_text)

    def test_review_schedule_json_writes_schedule_and_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            mistake = MistakeRecord(
                session_id="session-001",
                concept="zeta_urgent_review",
                misconception_id="zeta_definition_confusion",
                user_answer="The zeta condition is automatic.",
                analysis="Treats the review condition as vacuous.",
                repair_suggestion="Contrast the definitions.",
                follow_up_exercises=["zeta_review_01"],
            )
            update_learning_state(
                context,
                LearningStatePatch(
                    concept_mastery={
                        "alpha_medium_review": 0.62,
                        "subgroup": 0.84,
                    },
                    mistakes=[mistake],
                ),
            )
            update_learning_state(context, LearningStatePatch(mistakes=[mistake]))

            schedule_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "schedule",
                    "--project",
                    str(project),
                    "--threshold",
                    "0.8",
                    "--as-of",
                    "2026-06-04",
                    "--json",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(schedule_result.returncode, 0, schedule_result.stderr)
            self.assertNotIn("Scheduled 2 review items:", schedule_result.stdout)
            self.assertNotIn("# Review Schedule", schedule_result.stdout)
            payload = json.loads(schedule_result.stdout)
            schedule_path = project / "02_learning_plan" / "review_schedule.md"
            self.assertEqual(
                payload,
                {
                    "schema_version": 1,
                    "quality_boundary": "deterministic_review_schedule_writer",
                    "project": str(project),
                    "as_of": "2026-06-04",
                    "threshold": 0.8,
                    "scheduled_count": 2,
                    "schedule_path": str(schedule_path),
                    "scheduled_reviews": [
                        {
                            "concept": "zeta_urgent_review",
                            "priority": "high",
                            "due": "next_session",
                            "scheduled_for": "2026-06-04",
                            "reason": "active misconception zeta_definition_confusion x2",
                            "repair": "Contrast the definitions.",
                        },
                        {
                            "concept": "alpha_medium_review",
                            "priority": "medium",
                            "due": "within_3_days",
                            "scheduled_for": "2026-06-07",
                            "reason": "mastery 0.62",
                            "repair": "",
                        },
                    ],
                },
            )

            learning_state = json.loads(context.learning_state.read_text(encoding="utf-8"))
            self.assertEqual(
                learning_state["review_schedule"],
                [
                    {
                        "concept": "zeta_urgent_review",
                        "priority": "high",
                        "due": "next_session",
                        "scheduled_for": "2026-06-04",
                        "reason": "active misconception zeta_definition_confusion x2",
                        "repair_context": [
                            {
                                "misconception_id": "zeta_definition_confusion",
                                "count": 2,
                                "last_session_id": "session-001",
                                "analysis": "Treats the review condition as vacuous.",
                                "repair_suggestion": "Contrast the definitions.",
                                "follow_up_exercises": ["zeta_review_01"],
                            }
                        ],
                    },
                    {
                        "concept": "alpha_medium_review",
                        "priority": "medium",
                        "due": "within_3_days",
                        "scheduled_for": "2026-06-07",
                        "reason": "mastery 0.62",
                    },
                ],
            )
            schedule_text = schedule_path.read_text(encoding="utf-8")
            self.assertIn("## zeta_urgent_review", schedule_text)
            self.assertIn("## alpha_medium_review", schedule_text)
            self.assertNotIn("## subgroup", schedule_text)

    def test_review_schedule_json_writes_empty_schedule_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))

            schedule_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "schedule",
                    "--project",
                    str(project),
                    "--as-of",
                    "2026-06-04",
                    "--json",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(schedule_result.returncode, 0, schedule_result.stderr)
            payload = json.loads(schedule_result.stdout)
            schedule_path = project / "02_learning_plan" / "review_schedule.md"
            self.assertEqual(
                payload,
                {
                    "schema_version": 1,
                    "quality_boundary": "deterministic_review_schedule_writer",
                    "project": str(project),
                    "as_of": "2026-06-04",
                    "threshold": 0.7,
                    "scheduled_count": 0,
                    "schedule_path": str(schedule_path),
                    "scheduled_reviews": [],
                },
            )
            learning_state = json.loads(
                (project / "00_meta" / "learning_state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(learning_state["review_schedule"], [])
            self.assertIn(
                "No review items scheduled.",
                schedule_path.read_text(encoding="utf-8"),
            )

    def test_review_schedule_cli_rejects_nonfinite_threshold_without_writing_schedule(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(concept_mastery={"normal_subgroup": 0.4}),
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "schedule",
                    "--project",
                    str(project),
                    "--threshold",
                    "nan",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertIn("error: Review mastery threshold must be finite", result.stderr)
            self.assertFalse((project / "02_learning_plan" / "review_schedule.md").exists())
            learning_state = json.loads(
                (project / "00_meta" / "learning_state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(learning_state.get("review_schedule", []), [])

    def test_review_schedule_cli_rejects_invalid_as_of_date(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "schedule",
                    "--project",
                    str(project),
                    "--as-of",
                    "not-a-date",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertIn(
                "error: invalid ISO date 'not-a-date'; expected YYYY-MM-DD",
                result.stderr,
            )
            self.assertNotIn("Traceback", result.stderr)

    def test_review_schedule_cli_treats_invalid_mastery_scores_as_weak(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            learning_state = project / "00_meta" / "learning_state.json"
            learning_state.write_text(
                json.dumps(
                    {
                        "concept_mastery": {
                            "normal_subgroup": "not-a-score",
                            "subgroup": 0.84,
                        },
                        "proof_skills": {},
                        "misconceptions": {},
                        "review_schedule": [],
                    },
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
                    "review",
                    "schedule",
                    "--project",
                    str(project),
                    "--as-of",
                    "2026-06-04",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Scheduled 1 review item", result.stdout)
            self.assertNotIn("Traceback", result.stderr)
            state = json.loads(learning_state.read_text(encoding="utf-8"))
            self.assertEqual(
                state["review_schedule"],
                [
                    {
                        "concept": "normal_subgroup",
                        "priority": "high",
                        "due": "next_session",
                        "scheduled_for": "2026-06-04",
                        "reason": "mastery 0",
                    }
                ],
            )
            schedule_text = (project / "02_learning_plan" / "review_schedule.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("## normal_subgroup", schedule_text)
            self.assertIn("- Reason: mastery 0", schedule_text)
            self.assertNotIn("## subgroup", schedule_text)

    def test_review_schedule_cli_treats_nonfinite_mastery_scores_as_weak(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            learning_state = project / "00_meta" / "learning_state.json"
            learning_state.write_text(
                "{\n"
                '  "concept_mastery": {\n'
                '    "normal_subgroup": NaN,\n'
                '    "quotient_group": Infinity,\n'
                '    "subgroup": 0.84\n'
                "  },\n"
                '  "proof_skills": {},\n'
                '  "misconceptions": {},\n'
                '  "review_schedule": []\n'
                "}\n",
                encoding="utf-8",
                newline="\n",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "schedule",
                    "--project",
                    str(project),
                    "--as-of",
                    "2026-06-04",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Scheduled 2 review items", result.stdout)
            state = json.loads(learning_state.read_text(encoding="utf-8"))
            self.assertEqual(
                state["review_schedule"],
                [
                    {
                        "concept": "normal_subgroup",
                        "priority": "high",
                        "due": "next_session",
                        "scheduled_for": "2026-06-04",
                        "reason": "mastery 0",
                    },
                    {
                        "concept": "quotient_group",
                        "priority": "high",
                        "due": "next_session",
                        "scheduled_for": "2026-06-04",
                        "reason": "mastery 0",
                    },
                ],
            )
            schedule_text = (project / "02_learning_plan" / "review_schedule.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("## normal_subgroup", schedule_text)
            self.assertIn("## quotient_group", schedule_text)
            self.assertNotIn("nan", schedule_text.casefold())
            self.assertNotIn("inf", schedule_text.casefold())

    def test_review_schedule_cli_treats_out_of_range_mastery_scores_as_weak(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            learning_state = project / "00_meta" / "learning_state.json"
            learning_state.write_text(
                json.dumps(
                    {
                        "concept_mastery": {
                            "normal_subgroup": 1.25,
                            "quotient_group": -0.2,
                            "subgroup": 0.84,
                        },
                        "proof_skills": {},
                        "misconceptions": {},
                        "review_schedule": [],
                    },
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
                    "review",
                    "schedule",
                    "--project",
                    str(project),
                    "--as-of",
                    "2026-06-04",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Scheduled 2 review items", result.stdout)
            state = json.loads(learning_state.read_text(encoding="utf-8"))
            self.assertEqual(
                state["review_schedule"],
                [
                    {
                        "concept": "normal_subgroup",
                        "priority": "high",
                        "due": "next_session",
                        "scheduled_for": "2026-06-04",
                        "reason": "mastery 0",
                    },
                    {
                        "concept": "quotient_group",
                        "priority": "high",
                        "due": "next_session",
                        "scheduled_for": "2026-06-04",
                        "reason": "mastery 0",
                    },
                ],
            )
            schedule_text = (project / "02_learning_plan" / "review_schedule.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("## normal_subgroup", schedule_text)
            self.assertIn("## quotient_group", schedule_text)
            self.assertNotIn("1.25", schedule_text)
            self.assertNotIn("-0.2", schedule_text)

    def test_review_schedule_cli_recovers_malformed_misconception_count(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            learning_state = project / "00_meta" / "learning_state.json"
            learning_state.write_text(
                json.dumps(
                    {
                        "concept_mastery": {},
                        "proof_skills": {},
                        "misconceptions": {
                            "normal_equals_central": {
                                "concept": "normal_subgroup",
                                "count": "many",
                                "status": "active",
                                "analysis": "Confuses normality with centrality.",
                                "repair_suggestion": "Compare conjugation invariance with centrality.",
                            }
                        },
                        "review_schedule": [],
                    },
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
                    "review",
                    "schedule",
                    "--project",
                    str(project),
                    "--as-of",
                    "2026-06-04",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Scheduled 1 review item", result.stdout)
            state = json.loads(learning_state.read_text(encoding="utf-8"))
            self.assertEqual(
                state["review_schedule"],
                [
                    {
                        "concept": "normal_subgroup",
                        "priority": "medium",
                        "due": "within_3_days",
                        "scheduled_for": "2026-06-07",
                        "reason": "active misconception normal_equals_central x1",
                        "repair_context": [
                            {
                                "misconception_id": "normal_equals_central",
                                "count": 1,
                                "analysis": "Confuses normality with centrality.",
                                "repair_suggestion": (
                                    "Compare conjugation invariance with centrality."
                                ),
                            }
                        ],
                    }
                ],
            )
            schedule_text = (project / "02_learning_plan" / "review_schedule.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("## normal_subgroup", schedule_text)
            self.assertIn("- Reason: active misconception normal_equals_central x1", schedule_text)
            self.assertIn(
                "- Misconception: normal_equals_central (x1)",
                schedule_text,
            )
            self.assertNotIn("many", schedule_text)

    def test_review_exercises_cli_can_generate_only_due_items(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "p"))
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(
                    concept_mastery={
                        "normal_subgroup": 0.4,
                        "quotient_group": 0.62,
                    }
                ),
            )
            build_review_schedule(context, as_of=date(2026, 6, 4))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "exercises",
                    "--project",
                    str(project),
                    "--due-by",
                    "2026-06-04",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Generated 1 targeted review exercise", result.stdout)
            self.assertTrue(
                (project / "05_exercises" / "generated" / "review_normal_subgroup_01.md").exists()
            )
            self.assertFalse(
                (project / "05_exercises" / "generated" / "review_quotient_group_01.md").exists()
            )

            priority_project = create_project(
                ProjectSpec(topic="Representation Theory", path=root / "priority")
            )
            priority_context = load_project(priority_project)
            update_learning_state(
                priority_context,
                LearningStatePatch(
                    concept_mastery={
                        "normal_subgroup": 0.4,
                        "quotient_group": 0.62,
                    }
                ),
            )
            build_review_schedule(priority_context, as_of=date(2026, 6, 4))
            high_priority = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "exercises",
                    "--project",
                    str(priority_project),
                    "--due-by",
                    "2026-06-07",
                    "--priority",
                    "high",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(high_priority.returncode, 0, high_priority.stderr)
            self.assertIn("Generated 1 targeted review exercise", high_priority.stdout)
            self.assertTrue(
                (
                    priority_project
                    / "05_exercises"
                    / "generated"
                    / "review_normal_subgroup_01.md"
                ).exists()
            )
            self.assertFalse(
                (
                    priority_project
                    / "05_exercises"
                    / "generated"
                    / "review_quotient_group_01.md"
                ).exists()
            )

    def test_review_exercises_json_reports_generated_due_items(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(
                    concept_mastery={
                        "normal_subgroup": 0.4,
                        "quotient_group": 0.62,
                    }
                ),
            )
            build_review_schedule(context, as_of=date(2026, 6, 4))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "exercises",
                    "--project",
                    str(project),
                    "--due-by",
                    "2026-06-04",
                    "--json",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(
                payload,
                {
                    "schema_version": 1,
                    "quality_boundary": "deterministic_review_exercise_writer",
                    "project": str(project),
                    "due_by": "2026-06-04",
                    "priority_filter": "all",
                    "generated_count": 1,
                    "generated_exercises": [
                        {
                            "id": "review_normal_subgroup_01",
                            "type": "targeted_review_exercise",
                            "difficulty": 3,
                            "path": "05_exercises/generated/review_normal_subgroup_01.md",
                        }
                    ],
                },
            )
            self.assertTrue(
                (project / "05_exercises" / "generated" / "review_normal_subgroup_01.md").exists()
            )
            self.assertFalse(
                (project / "05_exercises" / "generated" / "review_quotient_group_01.md").exists()
            )

    def test_review_exercises_json_preserves_priority_filter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(
                    concept_mastery={
                        "normal_subgroup": 0.4,
                        "quotient_group": 0.62,
                    }
                ),
            )
            build_review_schedule(context, as_of=date(2026, 6, 4))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "exercises",
                    "--project",
                    str(project),
                    "--due-by",
                    "2026-06-07",
                    "--priority",
                    "high",
                    "--json",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["quality_boundary"], "deterministic_review_exercise_writer")
            self.assertEqual(payload["project"], str(project))
            self.assertEqual(payload["due_by"], "2026-06-07")
            self.assertEqual(payload["priority_filter"], "high")
            self.assertEqual(payload["generated_count"], 1)
            self.assertEqual(
                payload["generated_exercises"],
                [
                    {
                        "id": "review_normal_subgroup_01",
                        "type": "targeted_review_exercise",
                        "difficulty": 3,
                        "path": "05_exercises/generated/review_normal_subgroup_01.md",
                    }
                ],
            )
            self.assertTrue(
                (project / "05_exercises" / "generated" / "review_normal_subgroup_01.md").exists()
            )
            self.assertFalse(
                (project / "05_exercises" / "generated" / "review_quotient_group_01.md").exists()
            )

    def test_review_exercises_dry_run_reports_preview_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(
                    concept_mastery={
                        "normal_subgroup": 0.4,
                        "quotient_group": 0.62,
                    }
                ),
            )
            build_review_schedule(context, as_of=date(2026, 6, 4))
            learning_state = project / "00_meta" / "learning_state.json"
            original_state = learning_state.read_text(encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "exercises",
                    "--project",
                    str(project),
                    "--due-by",
                    "2026-06-04",
                    "--dry-run",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(
                "Exercise preview: 1 targeted review exercise would be generated",
                result.stdout,
            )
            self.assertIn(
                "- review_normal_subgroup_01 | targeted_review_exercise | "
                "difficulty 3 | 05_exercises/generated/review_normal_subgroup_01.md",
                result.stdout,
            )
            self.assertNotIn("Generated 1 targeted review exercise", result.stdout)
            self.assertEqual(learning_state.read_text(encoding="utf-8"), original_state)
            self.assertFalse(
                (project / "05_exercises" / "generated" / "review_normal_subgroup_01.md").exists()
            )
            self.assertFalse(
                (project / "05_exercises" / "generated" / "review_quotient_group_01.md").exists()
            )

    def test_review_exercises_dry_run_json_reports_preview_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(
                    concept_mastery={
                        "normal_subgroup": 0.4,
                        "quotient_group": 0.62,
                    }
                ),
            )
            build_review_schedule(context, as_of=date(2026, 6, 4))
            learning_state = project / "00_meta" / "learning_state.json"
            original_state = learning_state.read_text(encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "exercises",
                    "--project",
                    str(project),
                    "--due-by",
                    "2026-06-07",
                    "--priority",
                    "high",
                    "--dry-run",
                    "--json",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(
                payload,
                {
                    "schema_version": 1,
                    "quality_boundary": "deterministic_review_exercise_preview",
                    "project": str(project),
                    "due_by": "2026-06-07",
                    "priority_filter": "high",
                    "dry_run": True,
                    "generated_count": 1,
                    "generated_exercises": [
                        {
                            "id": "review_normal_subgroup_01",
                            "type": "targeted_review_exercise",
                            "difficulty": 3,
                            "path": "05_exercises/generated/review_normal_subgroup_01.md",
                        }
                    ],
                },
            )
            self.assertEqual(learning_state.read_text(encoding="utf-8"), original_state)
            self.assertFalse(
                (project / "05_exercises" / "generated" / "review_normal_subgroup_01.md").exists()
            )
            self.assertFalse(
                (project / "05_exercises" / "generated" / "review_quotient_group_01.md").exists()
            )

    def test_review_exercises_cli_rejects_invalid_due_by_date(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "exercises",
                    "--project",
                    str(project),
                    "--due-by",
                    "not-a-date",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertIn(
                "error: invalid ISO date 'not-a-date'; expected YYYY-MM-DD",
                result.stderr,
            )
            self.assertNotIn("Traceback", result.stderr)

    def test_review_due_cli_lists_items_due_by_date(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(
                    concept_mastery={
                        "alpha_medium_review": 0.62,
                        "zeta_urgent_review": 0.4,
                    }
                ),
            )
            build_review_schedule(context, as_of=date(2026, 6, 4))

            today = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "due",
                    "--project",
                    str(project),
                    "--as-of",
                    "2026-06-04",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            later = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "due",
                    "--project",
                    str(project),
                    "--as-of",
                    "2026-06-07",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            high_priority = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "due",
                    "--project",
                    str(project),
                    "--as-of",
                    "2026-06-07",
                    "--priority",
                    "high",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(today.returncode, 0, today.stderr)
            self.assertIn("# Due Reviews", today.stdout)
            self.assertIn("- zeta_urgent_review | 2026-06-04 | high | mastery 0.4", today.stdout)
            self.assertNotIn("alpha_medium_review", today.stdout)
            self.assertEqual(later.returncode, 0, later.stderr)
            self.assertIn("- zeta_urgent_review | 2026-06-04 | high | mastery 0.4", later.stdout)
            self.assertIn("- alpha_medium_review | 2026-06-07 | medium | mastery 0.62", later.stdout)
            self.assertEqual(high_priority.returncode, 0, high_priority.stderr)
            self.assertIn(
                "- zeta_urgent_review | 2026-06-04 | high | mastery 0.4",
                high_priority.stdout,
            )
            self.assertNotIn("alpha_medium_review", high_priority.stdout)

    def test_review_due_json_lists_due_and_invalid_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(
                    concept_mastery={
                        "alpha_medium_review": 0.62,
                        "zeta_urgent_review": 0.4,
                    }
                ),
            )
            build_review_schedule(context, as_of=date(2026, 6, 4))
            state = json.loads(context.learning_state.read_text(encoding="utf-8"))
            state["review_schedule"].append(
                {
                    "concept": "broken_review",
                    "priority": "medium",
                    "due": "within_3_days",
                    "scheduled_for": "not-a-date",
                    "reason": "corrupt schedule fixture",
                }
            )
            context.learning_state.write_text(
                json.dumps(state, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "due",
                    "--project",
                    str(project),
                    "--as-of",
                    "2026-06-07",
                    "--json",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("# Due Reviews", result.stdout)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["quality_boundary"], "deterministic_due_review")
            self.assertEqual(payload["project"], str(project))
            self.assertEqual(payload["as_of"], "2026-06-07")
            self.assertEqual(payload["priority_filter"], "all")
            self.assertEqual(payload["due_count"], 2)
            self.assertEqual(payload["invalid_count"], 1)
            self.assertEqual(
                payload["due_reviews"],
                [
                    {
                        "concept": "zeta_urgent_review",
                        "scheduled_for": "2026-06-04",
                        "priority": "high",
                        "reason": "mastery 0.4",
                        "repair": "",
                    },
                    {
                        "concept": "alpha_medium_review",
                        "scheduled_for": "2026-06-07",
                        "priority": "medium",
                        "reason": "mastery 0.62",
                        "repair": "",
                    },
                ],
            )
            self.assertEqual(
                payload["invalid_reviews"],
                [
                    {
                        "concept": "broken_review",
                        "scheduled_for": "not-a-date",
                        "status": "invalid_scheduled_for",
                    }
                ],
            )

    def test_review_due_json_filters_priority_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(
                    concept_mastery={
                        "alpha_medium_review": 0.62,
                        "zeta_urgent_review": 0.4,
                    }
                ),
            )
            build_review_schedule(context, as_of=date(2026, 6, 4))
            state = json.loads(context.learning_state.read_text(encoding="utf-8"))
            state["review_schedule"].append(
                {
                    "concept": "broken_review",
                    "priority": "medium",
                    "due": "within_3_days",
                    "scheduled_for": "not-a-date",
                    "reason": "corrupt schedule fixture",
                }
            )
            context.learning_state.write_text(
                json.dumps(state, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            learning_state_before = context.learning_state.read_text(encoding="utf-8")
            project_log_before = context.project_log.read_text(encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "due",
                    "--project",
                    str(project),
                    "--as-of",
                    "2026-06-07",
                    "--priority",
                    "high",
                    "--json",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["priority_filter"], "high")
            self.assertEqual(payload["due_count"], 1)
            self.assertEqual(payload["invalid_count"], 1)
            self.assertEqual(
                [row["concept"] for row in payload["due_reviews"]],
                ["zeta_urgent_review"],
            )
            self.assertEqual(
                [row["concept"] for row in payload["invalid_reviews"]],
                ["broken_review"],
            )
            self.assertEqual(
                context.learning_state.read_text(encoding="utf-8"),
                learning_state_before,
            )
            self.assertEqual(context.project_log.read_text(encoding="utf-8"), project_log_before)
            self.assertEqual(list((project / "04_atomic_notes" / "drafts").iterdir()), [])

    def test_review_due_cli_shows_misconception_repair_suggestion(self) -> None:
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
                            repair_suggestion="Compare gNg^-1=N with gn=ng.",
                        )
                    ],
                ),
            )
            build_review_schedule(context, as_of=date(2026, 6, 4))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "due",
                    "--project",
                    str(project),
                    "--as-of",
                    "2026-06-07",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(
                (
                    "- normal_subgroup | 2026-06-07 | medium | "
                    "active misconception normal_equals_central x1 | "
                    "repair: Compare gNg^-1=N with gn=ng."
                ),
                result.stdout,
            )

    def test_review_due_cli_rejects_invalid_as_of_date(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "due",
                    "--project",
                    str(project),
                    "--as-of",
                    "not-a-date",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertIn(
                "error: invalid ISO date 'not-a-date'; expected YYYY-MM-DD",
                result.stderr,
            )
            self.assertNotIn("Traceback", result.stderr)

    def test_review_due_cli_reports_invalid_persisted_schedule_dates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            learning_state = project / "00_meta" / "learning_state.json"
            learning_state.write_text(
                json.dumps(
                    {
                        "concept_mastery": {},
                        "proof_skills": {},
                        "misconceptions": {},
                        "review_schedule": [
                            {
                                "concept": "normal_subgroup",
                                "priority": "high",
                                "due": "next_session",
                                "scheduled_for": "2026-06-04",
                                "reason": "mastery 0.4",
                            },
                            {
                                "concept": "broken_review",
                                "priority": "medium",
                                "due": "within_3_days",
                                "scheduled_for": "not-a-date",
                                "reason": "corrupt schedule fixture",
                            },
                        ],
                    },
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
                    "review",
                    "due",
                    "--project",
                    str(project),
                    "--as-of",
                    "2026-06-04",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("- normal_subgroup | 2026-06-04 | high | mastery 0.4", result.stdout)
            self.assertIn("## Invalid Review Schedule Items", result.stdout)
            self.assertIn("- broken_review | not-a-date | invalid scheduled_for", result.stdout)
            self.assertNotIn("Traceback", result.stderr)

    def test_review_due_cli_reports_corrupt_learning_state_json_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
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
                    "due",
                    "--project",
                    str(project),
                    "--as-of",
                    "2026-06-04",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertIn("error: invalid learning_state.json", result.stderr)
            self.assertIn("repair the JSON before listing due reviews", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertNotIn("Expecting property name", result.stderr)

    def test_review_exercises_cli_reports_corrupt_learning_state_json_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
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
                    "exercises",
                    "--project",
                    str(project),
                    "--due-by",
                    "2026-06-04",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertIn("error: invalid learning_state.json", result.stderr)
            self.assertIn("repair the JSON before generating review exercises", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertNotIn("Expecting property name", result.stderr)

    def test_review_repair_schedule_cli_fills_missing_and_invalid_dates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            learning_state = project / "00_meta" / "learning_state.json"
            learning_state.write_text(
                json.dumps(
                    {
                        "concept_mastery": {},
                        "proof_skills": {},
                        "misconceptions": {},
                        "review_schedule": [
                            {
                                "concept": "normal_subgroup",
                                "priority": "high",
                                "due": "next_session",
                                "scheduled_for": "not-a-date",
                                "reason": "mastery 0.4",
                            },
                            {
                                "concept": "quotient_group",
                                "priority": "medium",
                                "due": "within_3_days",
                                "reason": "mastery 0.62",
                            },
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )

            repair = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "repair-schedule",
                    "--project",
                    str(project),
                    "--as-of",
                    "2026-06-04",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(repair.returncode, 0, repair.stderr)
            self.assertIn("Repaired 2 review schedule items:", repair.stdout)
            repaired_state = json.loads(learning_state.read_text(encoding="utf-8"))
            self.assertEqual(
                repaired_state["review_schedule"],
                [
                    {
                        "concept": "normal_subgroup",
                        "priority": "high",
                        "due": "next_session",
                        "scheduled_for": "2026-06-04",
                        "reason": "mastery 0.4",
                    },
                    {
                        "concept": "quotient_group",
                        "priority": "medium",
                        "due": "within_3_days",
                        "scheduled_for": "2026-06-07",
                        "reason": "mastery 0.62",
                    },
                ],
            )
            schedule_text = (project / "02_learning_plan" / "review_schedule.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("- Scheduled for: 2026-06-04", schedule_text)
            self.assertIn("- Scheduled for: 2026-06-07", schedule_text)
            self.assertNotIn("not-a-date", schedule_text)

            due = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "due",
                    "--project",
                    str(project),
                    "--as-of",
                    "2026-06-04",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(due.returncode, 0, due.stderr)
            self.assertIn("- normal_subgroup | 2026-06-04 | high | mastery 0.4", due.stdout)
            self.assertNotIn("Invalid Review Schedule Items", due.stdout)
            self.assertNotIn("quotient_group", due.stdout)

    def test_review_repair_schedule_json_repairs_and_reports_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            learning_state = project / "00_meta" / "learning_state.json"
            learning_state.write_text(
                json.dumps(
                    {
                        "concept_mastery": {},
                        "proof_skills": {},
                        "misconceptions": {},
                        "review_schedule": [
                            {
                                "concept": "normal_subgroup",
                                "priority": "high",
                                "due": "next_session",
                                "scheduled_for": "not-a-date",
                                "reason": "mastery 0.4",
                            },
                            {
                                "concept": "quotient_group",
                                "priority": "medium",
                                "due": "within_3_days",
                                "reason": "mastery 0.62",
                            },
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )

            repair = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "repair-schedule",
                    "--project",
                    str(project),
                    "--as-of",
                    "2026-06-04",
                    "--json",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(repair.returncode, 0, repair.stderr)
            self.assertNotIn("Repaired 2 review schedule items:", repair.stdout)
            payload = json.loads(repair.stdout)
            schedule_path = project / "02_learning_plan" / "review_schedule.md"
            self.assertEqual(
                payload,
                {
                    "schema_version": 1,
                    "quality_boundary": "deterministic_review_schedule_repair_writer",
                    "project": str(project),
                    "as_of": "2026-06-04",
                    "repaired_count": 2,
                    "schedule_path": str(schedule_path),
                    "scheduled_reviews": [
                        {
                            "concept": "normal_subgroup",
                            "priority": "high",
                            "due": "next_session",
                            "scheduled_for": "2026-06-04",
                            "reason": "mastery 0.4",
                            "repair": "",
                        },
                        {
                            "concept": "quotient_group",
                            "priority": "medium",
                            "due": "within_3_days",
                            "scheduled_for": "2026-06-07",
                            "reason": "mastery 0.62",
                            "repair": "",
                        },
                    ],
                },
            )
            repaired_state = json.loads(learning_state.read_text(encoding="utf-8"))
            self.assertEqual(
                repaired_state["review_schedule"],
                [
                    {
                        "concept": "normal_subgroup",
                        "priority": "high",
                        "due": "next_session",
                        "scheduled_for": "2026-06-04",
                        "reason": "mastery 0.4",
                    },
                    {
                        "concept": "quotient_group",
                        "priority": "medium",
                        "due": "within_3_days",
                        "scheduled_for": "2026-06-07",
                        "reason": "mastery 0.62",
                    },
                ],
            )
            schedule_text = schedule_path.read_text(encoding="utf-8")
            self.assertIn("- Scheduled for: 2026-06-04", schedule_text)
            self.assertIn("- Scheduled for: 2026-06-07", schedule_text)
            self.assertNotIn("not-a-date", schedule_text)

    def test_review_repair_schedule_json_reports_noop_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            learning_state = project / "00_meta" / "learning_state.json"
            learning_state.write_text(
                json.dumps(
                    {
                        "concept_mastery": {},
                        "proof_skills": {},
                        "misconceptions": {},
                        "review_schedule": [
                            {
                                "concept": "normal_subgroup",
                                "priority": "high",
                                "due": "next_session",
                                "scheduled_for": "2026-06-04",
                                "reason": "mastery 0.4",
                                "repair_context": [
                                    {
                                        "misconception_id": "normal_equals_central",
                                        "count": 1,
                                        "repair_suggestion": "Compare normality with centrality.",
                                    }
                                ],
                            }
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )

            repair = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "repair-schedule",
                    "--project",
                    str(project),
                    "--as-of",
                    "2026-06-04",
                    "--json",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(repair.returncode, 0, repair.stderr)
            payload = json.loads(repair.stdout)
            schedule_path = project / "02_learning_plan" / "review_schedule.md"
            self.assertEqual(
                payload,
                {
                    "schema_version": 1,
                    "quality_boundary": "deterministic_review_schedule_repair_writer",
                    "project": str(project),
                    "as_of": "2026-06-04",
                    "repaired_count": 0,
                    "schedule_path": str(schedule_path),
                    "scheduled_reviews": [
                        {
                            "concept": "normal_subgroup",
                            "priority": "high",
                            "due": "next_session",
                            "scheduled_for": "2026-06-04",
                            "reason": "mastery 0.4",
                            "repair": "Compare normality with centrality.",
                        }
                    ],
                },
            )
            self.assertTrue(schedule_path.exists())
            self.assertIn("## normal_subgroup", schedule_path.read_text(encoding="utf-8"))

    def test_review_repair_schedule_dry_run_reports_preview_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            learning_state = project / "00_meta" / "learning_state.json"
            learning_state.write_text(
                json.dumps(
                    {
                        "concept_mastery": {},
                        "proof_skills": {},
                        "misconceptions": {},
                        "review_schedule": [
                            {
                                "concept": "normal_subgroup",
                                "priority": "high",
                                "due": "next_session",
                                "scheduled_for": "not-a-date",
                                "reason": "mastery 0.4",
                            },
                            {
                                "concept": "quotient_group",
                                "priority": "medium",
                                "due": "within_3_days",
                                "reason": "mastery 0.62",
                            },
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            original_state = learning_state.read_text(encoding="utf-8")
            schedule_path = project / "02_learning_plan" / "review_schedule.md"
            self.assertFalse(schedule_path.exists())

            preview = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "repair-schedule",
                    "--project",
                    str(project),
                    "--as-of",
                    "2026-06-04",
                    "--dry-run",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(preview.returncode, 0, preview.stderr)
            self.assertIn(
                "Repair preview: 2 review schedule items would be repaired",
                preview.stdout,
            )
            self.assertIn("- normal_subgroup | 2026-06-04 | high | mastery 0.4", preview.stdout)
            self.assertIn("- quotient_group | 2026-06-07 | medium | mastery 0.62", preview.stdout)
            self.assertNotIn("Repaired 2 review schedule items:", preview.stdout)
            self.assertEqual(learning_state.read_text(encoding="utf-8"), original_state)
            self.assertFalse(schedule_path.exists())

    def test_review_repair_schedule_dry_run_json_reports_preview_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            learning_state = project / "00_meta" / "learning_state.json"
            learning_state.write_text(
                json.dumps(
                    {
                        "concept_mastery": {},
                        "proof_skills": {},
                        "misconceptions": {},
                        "review_schedule": [
                            {
                                "concept": "normal_subgroup",
                                "priority": "high",
                                "due": "next_session",
                                "scheduled_for": "not-a-date",
                                "reason": "mastery 0.4",
                            },
                            {
                                "concept": "quotient_group",
                                "priority": "medium",
                                "due": "within_3_days",
                                "reason": "mastery 0.62",
                            },
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            original_state = learning_state.read_text(encoding="utf-8")
            schedule_path = project / "02_learning_plan" / "review_schedule.md"
            self.assertFalse(schedule_path.exists())

            preview = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "repair-schedule",
                    "--project",
                    str(project),
                    "--as-of",
                    "2026-06-04",
                    "--dry-run",
                    "--json",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(preview.returncode, 0, preview.stderr)
            payload = json.loads(preview.stdout)
            self.assertEqual(
                payload,
                {
                    "schema_version": 1,
                    "quality_boundary": "deterministic_review_schedule_repair_preview",
                    "project": str(project),
                    "as_of": "2026-06-04",
                    "dry_run": True,
                    "repaired_count": 2,
                    "scheduled_reviews": [
                        {
                            "concept": "normal_subgroup",
                            "priority": "high",
                            "due": "next_session",
                            "scheduled_for": "2026-06-04",
                            "reason": "mastery 0.4",
                            "repair": "",
                        },
                        {
                            "concept": "quotient_group",
                            "priority": "medium",
                            "due": "within_3_days",
                            "scheduled_for": "2026-06-07",
                            "reason": "mastery 0.62",
                            "repair": "",
                        },
                    ],
                },
            )
            self.assertEqual(learning_state.read_text(encoding="utf-8"), original_state)
            self.assertFalse(schedule_path.exists())

    def test_review_repair_schedule_cli_reports_corrupt_learning_state_json_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
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
                    "repair-schedule",
                    "--project",
                    str(project),
                    "--as-of",
                    "2026-06-04",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertIn("error: invalid learning_state.json", result.stderr)
            self.assertIn("repair the JSON before repairing review schedule", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertNotIn("Expecting property name", result.stderr)

    def test_review_repair_schedule_cli_rejects_invalid_as_of_date(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "review",
                    "repair-schedule",
                    "--project",
                    str(project),
                    "--as-of",
                    "not-a-date",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertIn(
                "error: invalid ISO date 'not-a-date'; expected YYYY-MM-DD",
                result.stderr,
            )
            self.assertNotIn("Traceback", result.stderr)

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

    def test_status_counts_misconception_notes_to_draft(self) -> None:
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
                        )
                    ],
                ),
            )

            status_result = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status_result.returncode, 0, status_result.stderr)
            self.assertIn("Misconception notes to draft: 1", status_result.stdout)

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

    def test_update_eval_report_rejects_nonfinite_score_without_writing_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            report_path = context.evals_dir / "tutoring_eval.md"
            original_text = report_path.read_text(encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Eval report score must be finite"):
                update_eval_report(
                    context,
                    EvalReportUpdate(
                        report="tutoring",
                        subject="session-001",
                        score=math.nan,
                        summary="This score should not be written.",
                    ),
                )

            self.assertEqual(report_path.read_text(encoding="utf-8"), original_text)
            self.assertNotIn("This score should not be written.", original_text)

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
