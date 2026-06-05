from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from socrates.artifacts import generate_atomic_note_draft, generate_exercise_drafts
from socrates.context import load_project
from socrates.exercises import approve_exercise_draft, record_exercise_attempt
from socrates.kb import build_reference_kb
from socrates.notes import export_reviewed_notes_to_obsidian, review_atomic_note
from socrates.project import ProjectSpec, create_project
from socrates.state import (
    LearningStatePatch,
    MistakeRecord,
    build_review_schedule,
    resolve_active_misconceptions_for_concept,
    update_learning_state,
)
from socrates.tutoring import run_scripted_tutoring_session
from socrates.workflow import close_tutoring_session


REPO_ROOT = Path(__file__).resolve().parents[1]


class LearningQueueTests(unittest.TestCase):
    def test_queue_cli_lists_actionable_notes_and_exercises(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "p"))
            generate_atomic_note_draft(
                project,
                concept="Normal Subgroup",
                note_type="definition",
                body=(
                    "A normal subgroup is stable under conjugation; compare [[Subgroup]].\n\n"
                    "## Review Questions\n\n"
                    "- What condition distinguishes normality from centrality?\n"
                ),
                source_id="df",
            )
            generate_atomic_note_draft(
                project,
                concept="Group Action",
                note_type="definition",
                body=(
                    "A group action is a compatible map from a group into permutations.\n\n"
                    "## Review Questions\n\n"
                    "- What compatibility axiom must be checked?\n"
                ),
                source_id="df",
            )
            review_atomic_note(project, "normal_subgroup")
            generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="df",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )
            answer = root / "answer.md"
            answer.write_text("Use conjugation invariance.\n", encoding="utf-8", newline="\n")
            approve_exercise_draft(project, "normal_subgroup_01")
            approve_exercise_draft(project, "normal_subgroup_02")
            record_exercise_attempt(project, "normal_subgroup_01", answer)

            result = subprocess.run(
                [sys.executable, "-m", "socrates", "queue", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            notes_only = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "queue",
                    "--project",
                    str(project),
                    "--section",
                    "notes",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("## Notes To Review", result.stdout)
            self.assertIn("- group_action | 04_atomic_notes/drafts/group_action.md", result.stdout)
            self.assertNotIn("- normal_subgroup | 04_atomic_notes/drafts/normal_subgroup.md", result.stdout)
            self.assertIn("## Exercise Drafts To Approve", result.stdout)
            self.assertIn(
                "- normal_subgroup_03 | 05_exercises/generated/normal_subgroup_03.md",
                result.stdout,
            )
            self.assertIn("## Exercises To Attempt", result.stdout)
            self.assertIn("- normal_subgroup_02 | 05_exercises/generated/normal_subgroup_02.md", result.stdout)
            self.assertIn("## Attempts To Grade", result.stdout)
            self.assertIn(
                (
                    "- normal_subgroup_01_attempt_001 | "
                    "05_exercises/attempted/normal_subgroup_01_attempt_001.md"
                ),
                result.stdout,
            )

            self.assertEqual(notes_only.returncode, 0, notes_only.stderr)
            self.assertIn("## Notes To Review", notes_only.stdout)
            self.assertIn("- group_action | 04_atomic_notes/drafts/group_action.md", notes_only.stdout)
            self.assertNotIn("## Exercise Drafts To Approve", notes_only.stdout)
            self.assertNotIn("## Exercises To Attempt", notes_only.stdout)
            self.assertNotIn("## Attempts To Grade", notes_only.stdout)
            self.assertNotIn("normal_subgroup_03", notes_only.stdout)

    def test_queue_cli_json_summarizes_empty_project_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            project_files_before = _project_file_snapshot(project)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "queue",
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
            self.assertNotIn("# Learning Queue", result.stdout)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["quality_boundary"], "deterministic_learning_queue")
            self.assertEqual(payload["project"], "Group Theory")
            self.assertEqual(payload["root"], str(project))
            self.assertEqual(payload["section"], "all")
            self.assertEqual(
                payload["action_summary"],
                {
                    "completion": "clear",
                    "open_actions": 0,
                    "blockers": 0,
                    "can_continue_learning": 0,
                    "needs_human_review": 0,
                    "next_action": "none",
                },
            )
            self.assertEqual(
                payload["sections"],
                [
                    {"section": "repairs", "title": "Repair Paths", "count": 0, "items": []},
                    {"section": "priority", "title": "Priority Actions", "count": 0, "items": []},
                    {"section": "notes", "title": "Notes To Review", "count": 0, "items": []},
                    {
                        "section": "obsidian-exports",
                        "title": "Obsidian Exports To Run",
                        "count": 0,
                        "items": [],
                    },
                    {
                        "section": "misconceptions",
                        "title": "Misconception Notes To Draft",
                        "count": 0,
                        "items": [],
                    },
                    {"section": "reviews", "title": "Scheduled Reviews", "count": 0, "items": []},
                    {
                        "section": "exercise-drafts",
                        "title": "Exercise Drafts To Approve",
                        "count": 0,
                        "items": [],
                    },
                    {
                        "section": "exercises",
                        "title": "Exercises To Attempt",
                        "count": 0,
                        "items": [],
                    },
                    {"section": "attempts", "title": "Attempts To Grade", "count": 0, "items": []},
                    {"section": "workflow", "title": "Workflow Actions", "count": 0, "items": []},
                    {
                        "section": "quality-checks",
                        "title": "Quality Checks To Fix",
                        "count": 0,
                        "items": [],
                    },
                    {
                        "section": "tool-verifications",
                        "title": "Tool Verifications To Fix",
                        "count": 0,
                        "items": [],
                    },
                ],
            )
            self.assertEqual(_project_file_snapshot(project), project_files_before)

    def test_queue_cli_json_filters_priority_section_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = _create_ready_closeout_fixture(Path(temp_dir))
            project_files_before = _project_file_snapshot(project)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "queue",
                    "--project",
                    str(project),
                    "--section",
                    "priority",
                    "--json",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("# Learning Queue", result.stdout)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["quality_boundary"], "deterministic_learning_queue")
            self.assertEqual(payload["section"], "priority")
            self.assertEqual(payload["action_summary"]["completion"], "blocked")
            self.assertEqual(payload["action_summary"]["open_actions"], 7)
            self.assertEqual(payload["action_summary"]["blockers"], 1)
            self.assertEqual(
                payload["action_summary"]["next_action"],
                "workflow:multi_session_regression | "
                "08_evals/session_closeout_manifest.json | "
                "status: not_run; run with: socrates lifecycle regression --project <project>",
            )
            self.assertEqual(len(payload["sections"]), 1)
            priority = payload["sections"][0]
            self.assertEqual(priority["section"], "priority")
            self.assertEqual(priority["title"], "Priority Actions")
            self.assertEqual(priority["count"], 7)
            self.assertEqual(
                priority["items"][0],
                {
                    "item_id": "workflow:multi_session_regression",
                    "path": "08_evals/session_closeout_manifest.json",
                    "detail": (
                        "status: not_run; "
                        "run with: socrates lifecycle regression --project <project>"
                    ),
                },
            )
            self.assertIn(
                {
                    "item_id": "notes:normal_subgroup",
                    "path": "04_atomic_notes/drafts/normal_subgroup.md",
                    "detail": "",
                },
                priority["items"],
            )
            self.assertEqual(_project_file_snapshot(project), project_files_before)

    def test_queue_cli_lists_reviewed_notes_pending_obsidian_export(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            generate_atomic_note_draft(
                project,
                concept="Normal Subgroup",
                note_type="definition",
                body=(
                    "A normal subgroup is stable under conjugation; compare [[Subgroup]].\n\n"
                    "## Review Questions\n\n"
                    "- What condition distinguishes normality from centrality?\n"
                ),
                source_id="df",
            )
            review_atomic_note(project, "normal_subgroup")
            export_reviewed_notes_to_obsidian(project)
            generate_atomic_note_draft(
                project,
                concept="Quotient Group",
                note_type="definition",
                body=(
                    "A quotient group packages cosets of a [[Normal Subgroup]].\n\n"
                    "## Review Questions\n\n"
                    "- Why is normality needed for multiplication of cosets?\n"
                ),
                source_id="df",
            )
            review_atomic_note(project, "quotient_group")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "queue",
                    "--project",
                    str(project),
                    "--section",
                    "obsidian-exports",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("## Obsidian Exports To Run", result.stdout)
            self.assertIn(
                (
                    "- quotient_group | 04_atomic_notes/definitions/quotient_group.md | "
                    "export with: socrates note export-obsidian --project <project>"
                ),
                result.stdout,
            )
            self.assertNotIn("normal_subgroup", result.stdout)

    def test_queue_cli_lists_scheduled_reviews(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(concept_mastery={"normal_subgroup": 0.4}),
            )
            build_review_schedule(context, as_of=date(2026, 6, 4))

            result = subprocess.run(
                [sys.executable, "-m", "socrates", "queue", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("## Scheduled Reviews", result.stdout)
            self.assertIn(
                "- normal_subgroup | 02_learning_plan/review_schedule.md | scheduled for 2026-06-04",
                result.stdout,
            )

    def test_queue_cli_shows_scheduled_review_reason_and_repair_suggestion(self) -> None:
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
                [sys.executable, "-m", "socrates", "queue", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(
                (
                    "- normal_subgroup | 02_learning_plan/review_schedule.md | "
                    "scheduled for 2026-06-07; "
                    "reason: active misconception normal_equals_central x1; "
                    "repair: Compare gNg^-1=N with gn=ng."
                ),
                result.stdout,
            )

    def test_queue_cli_lists_misconception_notes_to_draft(self) -> None:
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

            result = subprocess.run(
                [sys.executable, "-m", "socrates", "queue", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("## Misconception Notes To Draft", result.stdout)
            self.assertIn(
                (
                    "- normal_equals_central | 00_meta/learning_state.json | "
                    "concept: normal_subgroup; status: active; "
                    "draft with: socrates note draft-misconceptions --status all"
                ),
                result.stdout,
            )

    def test_queue_cli_lists_resolved_misconception_notes_with_actionable_draft_command(self) -> None:
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
            resolve_active_misconceptions_for_concept(context, "normal_subgroup")

            result = subprocess.run(
                [sys.executable, "-m", "socrates", "queue", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(
                (
                    "- normal_equals_central | 00_meta/learning_state.json | "
                    "concept: normal_subgroup; status: resolved; "
                    "draft with: socrates note draft-misconceptions --status all"
                ),
                result.stdout,
            )

    def test_queue_cli_orders_scheduled_reviews_by_date(self) -> None:
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

            result = subprocess.run(
                [sys.executable, "-m", "socrates", "queue", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            urgent = (
                "- zeta_urgent_review | 02_learning_plan/review_schedule.md | "
                "scheduled for 2026-06-04"
            )
            medium = (
                "- alpha_medium_review | 02_learning_plan/review_schedule.md | "
                "scheduled for 2026-06-07"
            )
            self.assertIn(urgent, result.stdout)
            self.assertIn(medium, result.stdout)
            self.assertLess(result.stdout.index(urgent), result.stdout.index(medium))

    def test_queue_cli_lists_failed_tool_verification_records_to_fix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            verification_dir = project / "08_evals" / "tool_verification"
            verification_dir.mkdir(parents=True, exist_ok=True)
            (verification_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "records": [
                            {
                                "kind": "lean_statement_skeleton",
                                "object_id": "missing_kernel",
                                "status": "unchecked_skeleton",
                                "skeleton_path": (
                                    "08_evals/tool_verification/missing_kernel.lean"
                                ),
                                "report_path": (
                                    "08_evals/tool_verification/missing_kernel_report.md"
                                ),
                            }
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "tool",
                    "check",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            result = subprocess.run(
                [sys.executable, "-m", "socrates", "queue", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("## Tool Verifications To Fix", result.stdout)
            self.assertIn(
                (
                    "- missing_kernel | 08_evals/tool_verification_eval.md | "
                    "quality: fail; status: unchecked_skeleton; "
                    "issues: missing artifact: "
                    "08_evals/tool_verification/missing_kernel.lean; "
                    "missing report: "
                    "08_evals/tool_verification/missing_kernel_report.md; "
                    "rerun with: socrates tool check --project <project>"
                ),
                result.stdout,
            )

    def test_queue_cli_lists_manifest_level_tool_verification_failures(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "tool",
                    "check",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            result = subprocess.run(
                [sys.executable, "-m", "socrates", "queue", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("## Tool Verifications To Fix", result.stdout)
            self.assertIn(
                (
                    "- tool_verification_manifest | 08_evals/tool_verification_eval.md | "
                    "quality: fail; issues: missing tool-verification manifest; "
                    "rerun with: socrates tool check --project <project>"
                ),
                result.stdout,
            )

    def test_queue_cli_lists_failed_artifact_quality_checks_to_fix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            evals = project / "08_evals"
            (evals / "note_quality_eval.md").write_text(
                "# Note Quality Eval\n\n- normal_subgroup: fail\n",
                encoding="utf-8",
                newline="\n",
            )
            (evals / "note_quality_manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "checked": 1,
                        "passed": 0,
                        "failed": 1,
                        "notes": [
                            {
                                "id": "normal_subgroup",
                                "path": "04_atomic_notes/drafts/normal_subgroup.md",
                                "quality_status": "fail",
                                "issues": ["missing section Review Questions"],
                            }
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
                    "queue",
                    "--project",
                    str(project),
                    "--section",
                    "quality-checks",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("## Quality Checks To Fix", result.stdout)
            self.assertIn(
                (
                    "- note_quality | 08_evals/note_quality_eval.md | "
                    "quality: fail; failed: 1/1; "
                    "issues: normal_subgroup: missing section Review Questions; "
                    "rerun with: socrates note check --project <project>"
                ),
                result.stdout,
            )

    def test_queue_cli_lists_corrupt_tool_quality_manifest_to_fix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            manifest_path = project / "08_evals" / "tool_verification_quality_manifest.json"
            manifest_path.write_text("{not valid json\n", encoding="utf-8", newline="\n")

            result = subprocess.run(
                [sys.executable, "-m", "socrates", "queue", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("## Tool Verifications To Fix", result.stdout)
            self.assertIn(
                (
                    "- tool_verification_quality_manifest | "
                    "08_evals/tool_verification_quality_manifest.json | "
                    "quality: fail; issues: invalid tool-verification quality manifest JSON; "
                    "rerun with: socrates tool check --project <project>"
                ),
                result.stdout,
            )

    def test_queue_cli_lists_invalid_tool_quality_manifest_schema_to_fix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            manifest_path = project / "08_evals" / "tool_verification_quality_manifest.json"
            manifest_path.write_text("[]\n", encoding="utf-8", newline="\n")

            result = subprocess.run(
                [sys.executable, "-m", "socrates", "queue", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("## Tool Verifications To Fix", result.stdout)
            self.assertIn(
                (
                    "- tool_verification_quality_manifest | "
                    "08_evals/tool_verification_quality_manifest.json | "
                    "quality: fail; issues: invalid tool-verification quality manifest schema; "
                    "rerun with: socrates tool check --project <project>"
                ),
                result.stdout,
            )

    def test_queue_cli_lists_invalid_tool_quality_manifest_records_to_fix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            manifest_path = project / "08_evals" / "tool_verification_quality_manifest.json"
            manifest_path.write_text(
                json.dumps({"schema_version": 1, "records": "not-a-list"}) + "\n",
                encoding="utf-8",
                newline="\n",
            )

            result = subprocess.run(
                [sys.executable, "-m", "socrates", "queue", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("## Tool Verifications To Fix", result.stdout)
            self.assertIn(
                (
                    "- tool_verification_quality_manifest | "
                    "08_evals/tool_verification_quality_manifest.json | "
                    "quality: fail; issues: invalid tool-verification quality manifest records; "
                    "rerun with: socrates tool check --project <project>"
                ),
                result.stdout,
            )

    def test_queue_cli_lists_invalid_tool_quality_manifest_record_rows_to_fix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            manifest_path = project / "08_evals" / "tool_verification_quality_manifest.json"
            manifest_path.write_text(
                json.dumps({"schema_version": 1, "records": ["not-a-record"]}) + "\n",
                encoding="utf-8",
                newline="\n",
            )

            result = subprocess.run(
                [sys.executable, "-m", "socrates", "queue", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("## Tool Verifications To Fix", result.stdout)
            self.assertIn(
                (
                    "- record_1 | 08_evals/tool_verification_quality_manifest.json | "
                    "quality: fail; status: invalid_record; "
                    "issues: invalid tool-verification quality manifest record; "
                    "rerun with: socrates tool check --project <project>"
                ),
                result.stdout,
            )

    def test_queue_cli_lists_tool_quality_records_with_missing_status_to_fix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            manifest_path = project / "08_evals" / "tool_verification_quality_manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "records": [
                            {
                                "object_id": "kernel_normality",
                                "record_status": "unchecked_skeleton",
                                "artifact_path": (
                                    "08_evals/tool_verification/kernel_normality_statement.lean"
                                ),
                                "report_path": (
                                    "08_evals/tool_verification/kernel_normality_statement_report.md"
                                ),
                            }
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )

            result = subprocess.run(
                [sys.executable, "-m", "socrates", "queue", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("## Tool Verifications To Fix", result.stdout)
            self.assertIn(
                (
                    "- kernel_normality | "
                    "08_evals/tool_verification_quality_manifest.json | "
                    "quality: fail; status: invalid_quality_status; "
                    "issues: missing tool-verification quality status; "
                    "rerun with: socrates tool check --project <project>"
                ),
                result.stdout,
            )

    def test_queue_cli_lists_tool_quality_records_with_unknown_status_to_fix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            manifest_path = project / "08_evals" / "tool_verification_quality_manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "records": [
                            {
                                "object_id": "kernel_normality",
                                "quality_status": "stale",
                                "record_status": "unchecked_skeleton",
                                "issues": ["source manifest fingerprint changed"],
                            }
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )

            result = subprocess.run(
                [sys.executable, "-m", "socrates", "queue", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("## Tool Verifications To Fix", result.stdout)
            self.assertIn(
                (
                    "- kernel_normality | "
                    "08_evals/tool_verification_quality_manifest.json | "
                    "quality: fail; status: invalid_quality_status; "
                    "issues: unexpected tool-verification quality status: stale; "
                    "source manifest fingerprint changed; "
                    "rerun with: socrates tool check --project <project>"
                ),
                result.stdout,
            )

    def test_queue_cli_lists_missing_multi_session_regression_action(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = _create_ready_closeout_fixture(Path(temp_dir))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "queue",
                    "--project",
                    str(project),
                    "--section",
                    "workflow",
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
            self.assertIn("## Workflow Actions", result.stdout)
            self.assertIn(
                (
                    "- multi_session_regression | 08_evals/session_closeout_manifest.json | "
                    "status: not_run; run with: socrates lifecycle regression --project <project>"
                ),
                result.stdout,
            )
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Workflow actions: 1", status.stdout)

    def test_queue_cli_lists_invalid_multi_session_regression_action(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            (project / "08_evals" / "multi_session_regression_manifest.json").write_text(
                "{not valid json\n",
                encoding="utf-8",
                newline="\n",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "queue",
                    "--project",
                    str(project),
                    "--section",
                    "workflow",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("## Workflow Actions", result.stdout)
            self.assertIn(
                (
                    "- multi_session_regression | "
                    "08_evals/multi_session_regression_manifest.json | "
                    "status: invalid; rerun with: socrates lifecycle regression --project <project>"
                ),
                result.stdout,
            )

    def test_queue_cli_includes_action_summary_for_all_sections(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = _create_ready_closeout_fixture(Path(temp_dir))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "queue",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("## Action Summary", result.stdout)
            self.assertLess(
                result.stdout.index("## Action Summary"),
                result.stdout.index("## Priority Actions"),
            )
            self.assertIn("- Completion: blocked", result.stdout)
            self.assertIn("- Open actions: 7", result.stdout)
            self.assertIn("- Blockers: 1", result.stdout)
            self.assertIn("- Can continue learning: 0", result.stdout)
            self.assertIn("- Needs human review: 6", result.stdout)
            self.assertIn(
                (
                    "- Next action: workflow:multi_session_regression | "
                    "08_evals/session_closeout_manifest.json | "
                    "status: not_run; run with: socrates lifecycle regression --project <project>"
                ),
                result.stdout,
            )

    def test_queue_cli_action_summary_section_can_be_selected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "queue",
                    "--project",
                    str(project),
                    "--section",
                    "summary",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("## Action Summary", result.stdout)
            self.assertNotIn("## Priority Actions", result.stdout)
            self.assertIn("- Completion: clear", result.stdout)
            self.assertIn("- Open actions: 0", result.stdout)
            self.assertIn("- Blockers: 0", result.stdout)
            self.assertIn("- Can continue learning: 0", result.stdout)
            self.assertIn("- Needs human review: 0", result.stdout)
            self.assertIn("- Next action: none", result.stdout)

    def test_queue_cli_action_summary_distinguishes_review_work_from_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            generate_atomic_note_draft(
                project,
                concept="Normal Subgroup",
                note_type="definition",
                body=(
                    "A normal subgroup is stable under conjugation.\n\n"
                    "## Review Questions\n\n"
                    "- What condition distinguishes normality from centrality?\n"
                ),
                source_id="df-1",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "queue",
                    "--project",
                    str(project),
                    "--section",
                    "summary",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("- Completion: in_progress", result.stdout)
            self.assertIn("- Open actions: 1", result.stdout)
            self.assertIn("- Blockers: 0", result.stdout)
            self.assertIn("- Can continue learning: 0", result.stdout)
            self.assertIn("- Needs human review: 1", result.stdout)
            self.assertIn(
                "- Next action: notes:normal_subgroup | 04_atomic_notes/drafts/normal_subgroup.md",
                result.stdout,
            )

    def test_queue_cli_includes_repair_paths_for_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = _create_ready_closeout_fixture(Path(temp_dir))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "queue",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("## Repair Paths", result.stdout)
            self.assertLess(
                result.stdout.index("## Action Summary"),
                result.stdout.index("## Repair Paths"),
            )
            self.assertLess(
                result.stdout.index("## Repair Paths"),
                result.stdout.index("## Priority Actions"),
            )
            self.assertIn(
                (
                    "- workflow:multi_session_regression | "
                    "08_evals/session_closeout_manifest.json | "
                    "status: not_run; run with: socrates lifecycle regression --project <project>"
                ),
                result.stdout,
            )
            self.assertNotIn(
                "- notes:normal_subgroup | 04_atomic_notes/drafts/normal_subgroup.md",
                result.stdout.split("## Priority Actions", 1)[0],
            )

    def test_queue_cli_repair_paths_section_is_empty_without_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "queue",
                    "--project",
                    str(project),
                    "--section",
                    "repairs",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("## Repair Paths", result.stdout)
            self.assertIn("- none", result.stdout)
            self.assertNotIn("## Priority Actions", result.stdout)
            self.assertNotIn("## Action Summary", result.stdout)

    def test_queue_cli_prioritizes_workflow_actions_before_note_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = _create_ready_closeout_fixture(Path(temp_dir))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "queue",
                    "--project",
                    str(project),
                    "--section",
                    "priority",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("## Priority Actions", result.stdout)
            workflow = (
                "- workflow:multi_session_regression | "
                "08_evals/session_closeout_manifest.json | "
                "status: not_run; run with: socrates lifecycle regression --project <project>"
            )
            note = "- notes:normal_subgroup | 04_atomic_notes/drafts/normal_subgroup.md"
            self.assertIn(workflow, result.stdout)
            self.assertIn(note, result.stdout)
            self.assertLess(result.stdout.index(workflow), result.stdout.index(note))

    def test_queue_cli_priority_section_is_empty_when_no_actions_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "queue",
                    "--project",
                    str(project),
                    "--section",
                    "priority",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("## Priority Actions", result.stdout)
            self.assertIn("- none", result.stdout)

def _create_ready_closeout_fixture(root: Path) -> Path:
    project = create_project(ProjectSpec(topic="Group Theory", path=root / "p"))
    curated = project / "01_references" / "curated" / "normal_subgroups.curated.md"
    curated.write_text(
        "# Group Theory\n"
        "## Source Metadata\n"
        "- source_id: df-1\n"
        "- title: Normal Subgroups\n"
        "- role: lecture_notes\n"
        "### Definition: Normal Subgroup\n"
        "A normal subgroup is stable under conjugation.\n"
        "Depends: subgroup, conjugation\n",
        encoding="utf-8",
        newline="\n",
    )
    build_reference_kb(project)
    generate_atomic_note_draft(
        project,
        concept="Normal Subgroup",
        note_type="definition",
        body=(
            "A normal subgroup is stable under conjugation.\n\n"
            "## Review Questions\n\n"
            "- What condition distinguishes normality from centrality?\n"
        ),
        source_id="df-1",
    )
    generate_exercise_drafts(
        project,
        concept="Normal Subgroup",
        source_id="df-1",
        prerequisites=["subgroup", "conjugation"],
        count=5,
    )
    _write_session_script(root / "session_0001.script", "session_0001")
    _write_session_script(root / "session_0002.script", "session_0002")
    run_scripted_tutoring_session(project, root / "session_0001.script", session_id="session_0001")
    run_scripted_tutoring_session(project, root / "session_0002.script", session_id="session_0002")
    close_tutoring_session(
        project,
        session_id="session_0001",
        next_session_id="session_0002",
        as_of=date(2026, 6, 4),
    )
    return project


def _write_session_script(path: Path, session_id: str) -> None:
    path.write_text(
        "topic: Normal Subgroup\n"
        f"goal: Continue workflow action loop {session_id}.\n"
        "question: What does normality require?\n"
        "hint: Check conjugation invariance.\n"
        "hint: Compare gNg^-1=N with elementwise commutativity.\n"
        "attempt: It requires gNg^-1=N.\n"
        "next: Prove kernels are normal.\n",
        encoding="utf-8",
        newline="\n",
    )


def _project_file_snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


if __name__ == "__main__":
    unittest.main()
