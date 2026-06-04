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
from socrates.exercises import approve_exercise_draft, grade_exercise_attempt, record_exercise_attempt
from socrates.kb import build_reference_kb
from socrates.notes import export_reviewed_notes_to_obsidian, review_atomic_note
from socrates.project import ProjectSpec, create_project
from socrates.state import (
    LearningStatePatch,
    MistakeRecord,
    build_review_schedule,
    update_learning_state,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class ReportTests(unittest.TestCase):
    def test_report_list_cli_shows_generated_and_missing_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = self._create_report_fixture(root)

            weekly = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "report",
                    "weekly",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            summary = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "report",
                    "project-summary",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            all_reports = subprocess.run(
                [sys.executable, "-m", "socrates", "report", "list", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            missing_reports = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "report",
                    "list",
                    "--project",
                    str(project),
                    "--status",
                    "missing",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(weekly.returncode, 0, weekly.stderr)
            self.assertEqual(summary.returncode, 0, summary.stderr)
            self.assertEqual(all_reports.returncode, 0, all_reports.stderr)
            weekly_line = (
                "- weekly | generated | Weekly Learning Report | "
                "07_exports/reports/weekly_report.md"
            )
            monthly_line = (
                "- monthly | missing | Monthly Learning Report | "
                "07_exports/reports/monthly_report.md"
            )
            summary_line = (
                "- project-summary | generated | Project Summary | "
                "07_exports/reports/project_summary.md"
            )
            self.assertIn("# Learning Reports", all_reports.stdout)
            self.assertIn(weekly_line, all_reports.stdout)
            self.assertIn(monthly_line, all_reports.stdout)
            self.assertIn(summary_line, all_reports.stdout)
            self.assertLess(all_reports.stdout.index(weekly_line), all_reports.stdout.index(monthly_line))
            self.assertLess(all_reports.stdout.index(monthly_line), all_reports.stdout.index(summary_line))

            self.assertEqual(missing_reports.returncode, 0, missing_reports.stderr)
            self.assertIn(monthly_line, missing_reports.stdout)
            self.assertNotIn("weekly_report.md", missing_reports.stdout)
            self.assertNotIn("project_summary.md", missing_reports.stdout)

    def test_report_list_marks_project_summary_stale_after_benchmark_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = self._create_report_fixture(root)

            summary = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "report",
                    "project-summary",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            manifest_path = project / "08_evals" / "benchmark_manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "score": 75,
                        "passed_gates": 3,
                        "total_gates": 4,
                        "gates": [{"name": "Tutoring quality", "passed": False}],
                    },
                    indent=2,
                ),
                encoding="utf-8",
                newline="\n",
            )
            stale_reports = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "report",
                    "list",
                    "--project",
                    str(project),
                    "--status",
                    "stale",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(summary.returncode, 0, summary.stderr)
            self.assertEqual(stale_reports.returncode, 0, stale_reports.stderr)
            self.assertIn(
                "- project-summary | stale | Project Summary | "
                "07_exports/reports/project_summary.md",
                stale_reports.stdout,
            )
            self.assertNotIn("weekly_report.md", stale_reports.stdout)

    def test_report_list_marks_project_summary_stale_after_tool_verification_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = self._create_report_fixture(root)

            summary = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "report",
                    "project-summary",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            report_path = project / "07_exports" / "reports" / "project_summary.md"
            manifest_path = project / "08_evals" / "tool_verification" / "manifest.json"
            os.utime(report_path, (1_000_000, 1_000_000))
            os.utime(manifest_path, (1_000_100, 1_000_100))

            stale_reports = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "report",
                    "list",
                    "--project",
                    str(project),
                    "--status",
                    "stale",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(summary.returncode, 0, summary.stderr)
            self.assertEqual(stale_reports.returncode, 0, stale_reports.stderr)
            self.assertIn(
                "- project-summary | stale | Project Summary | "
                "07_exports/reports/project_summary.md",
                stale_reports.stdout,
            )
            self.assertNotIn("weekly_report.md", stale_reports.stdout)

    def test_report_list_marks_weekly_report_stale_after_learning_state_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = self._create_report_fixture(root)

            weekly = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "report",
                    "weekly",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            report_path = project / "07_exports" / "reports" / "weekly_report.md"
            os.utime(report_path, (1_000_000, 1_000_000))
            os.utime(project / "00_meta" / "learning_state.json", (1_000_100, 1_000_100))

            stale_reports = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "report",
                    "list",
                    "--project",
                    str(project),
                    "--status",
                    "stale",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(weekly.returncode, 0, weekly.stderr)
            self.assertEqual(stale_reports.returncode, 0, stale_reports.stderr)
            self.assertIn(
                "- weekly | stale | Weekly Learning Report | "
                "07_exports/reports/weekly_report.md",
                stale_reports.stdout,
            )
            self.assertNotIn("monthly_report.md", stale_reports.stdout)

    def test_report_list_marks_monthly_report_stale_after_note_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = self._create_report_fixture(root)

            weekly = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "report",
                    "weekly",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            monthly = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "report",
                    "monthly",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            report_path = project / "07_exports" / "reports" / "monthly_report.md"
            draft = project / "04_atomic_notes" / "drafts" / "new_draft.md"
            draft.write_text("# New Draft\n", encoding="utf-8", newline="\n")
            os.utime(report_path, (1_000_000, 1_000_000))
            os.utime(draft, (1_000_100, 1_000_100))

            stale_reports = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "report",
                    "list",
                    "--project",
                    str(project),
                    "--status",
                    "stale",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(weekly.returncode, 0, weekly.stderr)
            self.assertEqual(monthly.returncode, 0, monthly.stderr)
            self.assertEqual(stale_reports.returncode, 0, stale_reports.stderr)
            self.assertIn(
                "- monthly | stale | Monthly Learning Report | "
                "07_exports/reports/monthly_report.md",
                stale_reports.stdout,
            )
            self.assertNotIn("weekly_report.md", stale_reports.stdout)

    def test_weekly_report_cli_summarizes_learning_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = self._create_report_fixture(root)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "report",
                    "weekly",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Wrote weekly report", result.stdout)
            report = project / "07_exports" / "reports" / "weekly_report.md"
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("# Weekly Learning Report", report_text)
            self.assertIn("- Sessions completed: 1", report_text)
            self.assertIn("- Reviewed notes: 1", report_text)
            self.assertIn("- Generated exercises: 5", report_text)
            self.assertIn("- Graded exercises: 1", report_text)
            self.assertIn("## Learning State", report_text)
            self.assertIn("- normal_subgroup: 0.8", report_text)
            self.assertIn("## Scheduled Review", report_text)
            self.assertIn("- quotient_group: high, next_session", report_text)

    def test_project_summary_cli_writes_lifecycle_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = self._create_report_fixture(root)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "report",
                    "project-summary",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Wrote project summary", result.stdout)
            report = project / "07_exports" / "reports" / "project_summary.md"
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("# Project Summary", report_text)
            self.assertIn("- Title: Group Theory", report_text)
            self.assertIn("## Artifact Inventory", report_text)
            self.assertIn("- KB objects: 1", report_text)
            self.assertIn("- Reference KB status: current", report_text)
            self.assertIn("- Sessions completed: 1", report_text)
            self.assertIn("- Reviewed notes: 1", report_text)
            self.assertIn("- Obsidian exports: 1", report_text)
            self.assertIn("- Generated exercises: 5", report_text)
            self.assertIn("- Approved exercises: 1", report_text)
            self.assertIn("- Attempted exercises: 1", report_text)
            self.assertIn("- Graded exercises: 1", report_text)
            self.assertIn("- Tool verification records: 1", report_text)
            self.assertIn("## Benchmark Snapshot", report_text)
            self.assertIn("- not run", report_text)
            self.assertIn("## Tool Verification Snapshot", report_text)
            self.assertIn("- Check: not run", report_text)
            self.assertIn(
                "- kernel_normality: unchecked_skeleton, lean_statement_skeleton -> "
                "08_evals/tool_verification/kernel_normality_statement.lean",
                report_text,
            )
            self.assertIn("## Reference KB Snapshot", report_text)
            self.assertIn(
                "- Definition 3.1: Normal Subgroup - Normality Notes (lecture_notes) [normality_notes]",
                report_text,
            )
            self.assertIn(
                "  Source: 01_references/curated/normality.curated.md:p82:10",
                report_text,
            )
            self.assertIn("## Current Learning State", report_text)
            self.assertIn("- normal_subgroup: 0.8", report_text)
            self.assertIn("## Next Review Items", report_text)
            self.assertIn("- quotient_group: high, next_session", report_text)

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Current phase: report_ready", status.stdout)
            self.assertIn("Learning reports: 1", status.stdout)
            self.assertIn("Tool verification check: not run", status.stdout)

    def test_project_summary_marks_stale_reference_kb_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = self._create_report_fixture(root)
            curated = project / "01_references" / "curated" / "normality.curated.md"
            index_path = project / "06_kb" / "chunks" / "reference_index.json"
            index_time_ns = index_path.stat().st_mtime_ns
            curated.write_text(
                curated.read_text(encoding="utf-8")
                + "\n### Remark: Fresh Curated Comment\n"
                + "This remark has not been rebuilt into the reference KB yet.\n",
                encoding="utf-8",
                newline="\n",
            )
            os.utime(
                curated,
                ns=(index_time_ns + 1_000_000_000, index_time_ns + 1_000_000_000),
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "report",
                    "project-summary",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = project / "07_exports" / "reports" / "project_summary.md"
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("- Reference KB status: stale", report_text)
            self.assertIn("## Reference KB Snapshot", report_text)

    def test_project_summary_counts_obsidian_manifest_backlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "p"))
            curated = project / "01_references" / "curated" / "normality.curated.md"
            curated.write_text(
                "### Definition: Normal Subgroup\n"
                "A normal subgroup is stable under conjugation.\n"
                "Depends: subgroup\n\n"
                "### Definition: Quotient Group\n"
                "A quotient group uses cosets of a normal subgroup.\n"
                "Depends: normal_subgroup\n",
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
                    "- What conjugation condition must be checked?\n"
                ),
                source_id="df",
            )
            generate_atomic_note_draft(
                project,
                concept="Quotient Group",
                note_type="definition",
                body=(
                    "A quotient group packages cosets of a normal subgroup.\n\n"
                    "## Review Questions\n\n"
                    "- Why is normality required for multiplication of cosets?\n"
                ),
                source_id="df",
            )
            review_atomic_note(project, "normal_subgroup")
            review_atomic_note(project, "quotient_group")
            export_reviewed_notes_to_obsidian(project)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "report",
                    "project-summary",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = project / "07_exports" / "reports" / "project_summary.md"
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("- Obsidian exports: 2", report_text)
            self.assertIn("- Obsidian backlinks: 1", report_text)

    def test_report_list_marks_project_summary_stale_after_tool_quality_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = self._create_report_fixture(root)

            summary = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "report",
                    "project-summary",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            report_path = project / "07_exports" / "reports" / "project_summary.md"
            quality_manifest = project / "08_evals" / "tool_verification_quality_manifest.json"
            quality_manifest.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "status": "pass",
                        "checked": 1,
                        "passed": 1,
                        "failed": 0,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            os.utime(report_path, (1_000_000, 1_000_000))
            os.utime(quality_manifest, (1_000_100, 1_000_100))

            stale_reports = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "report",
                    "list",
                    "--project",
                    str(project),
                    "--status",
                    "stale",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(summary.returncode, 0, summary.stderr)
            self.assertEqual(stale_reports.returncode, 0, stale_reports.stderr)
            self.assertIn(
                "- project-summary | stale | Project Summary | "
                "07_exports/reports/project_summary.md",
                stale_reports.stdout,
            )
            self.assertNotIn("weekly_report.md", stale_reports.stdout)

    def test_project_summary_includes_benchmark_snapshot_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = self._create_report_fixture(root)
            manifest = {
                "schema_version": 1,
                "score": 75,
                "passed_gates": 3,
                "total_gates": 4,
                "gates": [
                    {"name": "Ingestion", "passed": True},
                    {"name": "Note quality", "passed": True},
                    {"name": "Exercise quality", "passed": True},
                    {"name": "Tutoring quality", "passed": False},
                ],
            }
            (project / "08_evals" / "benchmark_manifest.json").write_text(
                json.dumps(manifest, indent=2),
                encoding="utf-8",
                newline="\n",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "report",
                    "project-summary",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report_text = (
                project / "07_exports" / "reports" / "project_summary.md"
            ).read_text(encoding="utf-8")
            self.assertIn("## Benchmark Snapshot", report_text)
            self.assertIn("- Score: 75/100", report_text)
            self.assertIn("- Gates passed: 3/4", report_text)
            self.assertIn("- Failed gates: Tutoring quality", report_text)
            self.assertIn("- Manifest: 08_evals/benchmark_manifest.json", report_text)

    def test_monthly_report_cli_highlights_weaknesses_and_next_steps(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = self._create_report_fixture(root)
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(
                    mistakes=[
                        MistakeRecord(
                            session_id="session_0001",
                            concept="normal_subgroup",
                            misconception_id="normal_equals_central",
                            user_answer="Normal subgroups are central.",
                            analysis="Confuses invariance under conjugation with centrality.",
                            repair_suggestion="Compare N normal with N contained in Z(G).",
                        )
                    ],
                ),
            )
            build_review_schedule(context)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "report",
                    "monthly",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Wrote monthly report", result.stdout)
            report = project / "07_exports" / "reports" / "monthly_report.md"
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("# Monthly Learning Report", report_text)
            self.assertIn("## Concepts Studied", report_text)
            self.assertIn("- normal_subgroup: 0.8", report_text)
            self.assertIn("- quotient_group: 0.42", report_text)
            self.assertIn("## Notes And Exercises", report_text)
            self.assertIn("- Reviewed notes: 1", report_text)
            self.assertIn("- Obsidian exports: 1", report_text)
            self.assertIn("- Generated exercises: 5", report_text)
            self.assertIn("- Graded exercises: 1", report_text)
            self.assertIn("## Misconceptions", report_text)
            self.assertIn("- normal_equals_central: normal_subgroup, active x1", report_text)
            self.assertIn("## Weak Concepts", report_text)
            self.assertIn("- quotient_group: 0.42", report_text)
            self.assertIn("## Recommended Next Steps", report_text)
            self.assertIn("- quotient_group: high, next_session", report_text)
            self.assertIn("- normal_subgroup: medium, within_3_days", report_text)
            self.assertIn(
                "  - Repair suggestion: Compare N normal with N contained in Z(G).",
                report_text,
            )

    def _create_report_fixture(self, root: Path) -> Path:
        project = create_project(ProjectSpec(topic="Group Theory", path=root / "p"))
        curated = project / "01_references" / "curated" / "normality.curated.md"
        curated.write_text(
            "# Curated Reference: Normality Notes\n\n"
            "## Source Metadata\n\n"
            "- source_id: normality_notes\n"
            "- title: Normality Notes\n"
            "- role: lecture_notes\n"
            "- raw_path: 01_references/raw/markdown/normality.md\n\n"
            "### Definition 3.1: Normal Subgroup\n"
            "Page: 82\n"
            "A normal subgroup is stable under conjugation.\n"
            "Depends: subgroup, conjugation\n",
            encoding="utf-8",
            newline="\n",
        )
        build_reference_kb(project)
        session = project / "03_sessions" / "session_0001"
        session.mkdir()
        (session / "summary.md").write_text(
            "# Summary\n\nNormal subgroups were practiced through conjugation.\n",
            encoding="utf-8",
            newline="\n",
        )
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
            context=context,
            patch=LearningStatePatch(concept_mastery={"quotient_group": 0.42}),
        )
        build_review_schedule(context)
        tool_verification_dir = project / "08_evals" / "tool_verification"
        tool_verification_dir.mkdir(exist_ok=True)
        (tool_verification_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "records": [
                        {
                            "kind": "lean_statement_skeleton",
                            "object_id": "kernel_normality",
                            "object_type": "theorem",
                            "title": "Kernel Normality",
                            "status": "unchecked_skeleton",
                            "skeleton_path": (
                                "08_evals/tool_verification/"
                                "kernel_normality_statement.lean"
                            ),
                            "report_path": (
                                "08_evals/tool_verification/"
                                "kernel_normality_statement_report.md"
                            ),
                        }
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
            newline="\n",
        )
        return project


if __name__ == "__main__":
    unittest.main()
