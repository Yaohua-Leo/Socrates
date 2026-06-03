from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from socrates.artifacts import generate_atomic_note_draft, generate_exercise_drafts
from socrates.context import load_project
from socrates.exercises import (
    approve_exercise_draft,
    grade_exercise_attempt,
    record_exercise_attempt,
)
from socrates.kb import build_reference_kb
from socrates.notes import export_reviewed_notes_to_obsidian, review_atomic_note
from socrates.planning import create_learning_plan
from socrates.project import ProjectSpec, create_project
from socrates.quality import run_project_benchmark
from socrates.reports import (
    generate_monthly_report,
    generate_project_summary,
    generate_weekly_report,
)
from socrates.state import LearningStatePatch, build_review_schedule, update_learning_state
from socrates.tool_verification import generate_lean_statement_skeleton
from socrates.tutoring import run_scripted_tutoring_session


REPO_ROOT = Path(__file__).resolve().parents[1]


class LifecycleAuditTests(unittest.TestCase):
    def test_lifecycle_audit_cli_fails_when_required_artifacts_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "lifecycle",
                    "audit",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("Lifecycle audit passed 1/15 checks", result.stdout)
            report = project / "08_evals" / "lifecycle_eval.md"
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("- Project metadata: pass", report_text)
            self.assertIn("- Learning plans: fail", report_text)
            self.assertIn("- Obsidian export: fail", report_text)
            self.assertIn("- Benchmark report: fail", report_text)
            self.assertIn("- Benchmark manifest: fail", report_text)
            self.assertIn("- Tool verification records: fail", report_text)

    def test_lifecycle_audit_does_not_count_obsidian_utility_index_as_export(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            obsidian_dir = project / "07_exports" / "obsidian"
            (obsidian_dir / "_socrates_index.md").write_text(
                "# Socrates Obsidian Export\n\nNo reviewed notes exported.\n",
                encoding="utf-8",
                newline="\n",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "lifecycle",
                    "audit",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            report_text = (project / "08_evals" / "lifecycle_eval.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("- Obsidian export: fail", report_text)

    def test_lifecycle_audit_rejects_stale_benchmark_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            benchmark_report = project / "08_evals" / "benchmark_report.md"
            benchmark_report.write_text(
                "# Benchmark Report\n\n## Summary\n\n- Benchmark score: 100/100\n",
                encoding="utf-8",
                newline="\n",
            )
            os.utime(benchmark_report, (1_000_000, 1_000_000))
            exercise = project / "05_exercises" / "generated" / "new_exercise.md"
            exercise.write_text("# New Exercise\n", encoding="utf-8", newline="\n")
            os.utime(exercise, (1_000_100, 1_000_100))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "lifecycle",
                    "audit",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            report_text = (project / "08_evals" / "lifecycle_eval.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("- Benchmark report: fail", report_text)
            self.assertIn("- Benchmark manifest: fail", report_text)

    def test_lifecycle_audit_rejects_stale_benchmark_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            evals = project / "08_evals"
            artifact_names = (
                "ingestion_eval.md",
                "note_quality_eval.md",
                "exercise_quality_eval.md",
                "tutoring_eval.md",
                "ingestion_quality_manifest.json",
                "note_quality_manifest.json",
                "exercise_quality_manifest.json",
                "tutoring_quality_manifest.json",
            )
            for name in artifact_names:
                (evals / name).write_text("{}\n", encoding="utf-8", newline="\n")
                os.utime(evals / name, (1_000_200, 1_000_200))
            benchmark_report = evals / "benchmark_report.md"
            benchmark_report.write_text(
                "# Benchmark Report\n\n## Summary\n\n- Benchmark score: 100/100\n",
                encoding="utf-8",
                newline="\n",
            )
            os.utime(benchmark_report, (1_000_200, 1_000_200))
            benchmark_manifest = evals / "benchmark_manifest.json"
            benchmark_manifest.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "score": 100,
                        "passed_gates": 4,
                        "total_gates": 4,
                        "gates": [
                            {
                                "name": "Ingestion",
                                "passed": True,
                                "checked": 1,
                                "failed": 0,
                                "report_path": "08_evals/ingestion_eval.md",
                                "manifest_path": "08_evals/ingestion_quality_manifest.json",
                            },
                            {
                                "name": "Note quality",
                                "passed": True,
                                "checked": 1,
                                "failed": 0,
                                "report_path": "08_evals/note_quality_eval.md",
                                "manifest_path": "08_evals/note_quality_manifest.json",
                            },
                            {
                                "name": "Exercise quality",
                                "passed": True,
                                "checked": 5,
                                "failed": 0,
                                "report_path": "08_evals/exercise_quality_eval.md",
                                "manifest_path": "08_evals/exercise_quality_manifest.json",
                            },
                            {
                                "name": "Tutoring quality",
                                "passed": True,
                                "checked": 1,
                                "failed": 0,
                                "report_path": "08_evals/tutoring_eval.md",
                                "manifest_path": "08_evals/tutoring_quality_manifest.json",
                                "session_id": "session_0001",
                                "status": "pass",
                            },
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
                newline="\n",
            )
            os.utime(benchmark_manifest, (1_000_000, 1_000_000))
            exercise = project / "05_exercises" / "generated" / "new_exercise.md"
            exercise.write_text("# New Exercise\n", encoding="utf-8", newline="\n")
            os.utime(exercise, (1_000_100, 1_000_100))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "lifecycle",
                    "audit",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            report_text = (project / "08_evals" / "lifecycle_eval.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("- Benchmark report: pass", report_text)
            self.assertIn("- Benchmark manifest: fail", report_text)

    def test_lifecycle_audit_rejects_broken_tool_verification_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            manifest_path = project / "08_evals" / "tool_verification" / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "records": [
                            {
                                "kind": "lean_statement_skeleton",
                                "object_id": "normal_subgroup",
                                "status": "unchecked_skeleton",
                                "skeleton_path": (
                                    "08_evals/tool_verification/"
                                    "missing_statement.lean"
                                ),
                                "report_path": (
                                    "08_evals/tool_verification/"
                                    "missing_statement_report.md"
                                ),
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
                newline="\n",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "lifecycle",
                    "audit",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            report_text = (project / "08_evals" / "lifecycle_eval.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("- Tool verification records: fail", report_text)

    def test_lifecycle_audit_cli_reports_complete_learning_loop(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "p"))
            curated = project / "01_references" / "curated" / "normal_subgroups.curated.md"
            curated.write_text(
                "### Definition: Normal Subgroup\n"
                "A normal subgroup is stable under conjugation.\n"
                "Depends: subgroup, conjugation\n",
                encoding="utf-8",
                newline="\n",
            )
            build_reference_kb(project)
            create_learning_plan(project)
            script = root / "session.script"
            script.write_text(
                "topic: Normal Subgroup\n"
                "question: What must you check to prove normality?\n"
                "hint: Track conjugation invariance.\n"
                "hint: Compare normality with centrality.\n"
                "attempt: Show gNg^-1=N.\n"
                "next: Prove kernels are normal.\n",
                encoding="utf-8",
                newline="\n",
            )
            run_scripted_tutoring_session(project, script, session_id="session_0001")
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
            review_atomic_note(project, "normal_subgroup")
            export_reviewed_notes_to_obsidian(project)
            generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="df-1",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )
            answer = root / "answer.md"
            feedback = root / "feedback.md"
            answer.write_text("Use conjugation invariance.\n", encoding="utf-8", newline="\n")
            feedback.write_text("Good core idea.\n", encoding="utf-8", newline="\n")
            approve_exercise_draft(project, "normal_subgroup_01")
            record_exercise_attempt(project, "normal_subgroup_01", answer)
            grade_exercise_attempt(project, "normal_subgroup_01_attempt_001", 0.8, feedback)
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(concept_mastery={"quotient_group": 0.42}),
            )
            build_review_schedule(context)
            generate_lean_statement_skeleton(project, object_id="normal_subgroup")
            generate_weekly_report(project)
            generate_monthly_report(project)
            generate_project_summary(project)
            run_project_benchmark(project, session_id="session_0001")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "lifecycle",
                    "audit",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Lifecycle audit passed 15/15 checks", result.stdout)
            report = project / "08_evals" / "lifecycle_eval.md"
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("# Lifecycle Eval", report_text)
            self.assertIn("- Reference KB: pass", report_text)
            self.assertIn("- Tutoring session artifacts: pass", report_text)
            self.assertIn("- Obsidian export: pass", report_text)
            self.assertIn("- Learning reports: pass", report_text)
            self.assertIn("- Benchmark report: pass", report_text)
            self.assertIn("- Benchmark manifest: pass", report_text)
            self.assertIn("- Tool verification records: pass", report_text)

    def test_lifecycle_audit_accepts_completed_empty_review_schedule(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(concept_mastery={"normal_subgroup": 0.82}),
            )
            build_review_schedule(context)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "lifecycle",
                    "audit",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            report_text = (project / "08_evals" / "lifecycle_eval.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("- Review schedule: pass", report_text)


if __name__ == "__main__":
    unittest.main()
