from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from socrates.artifacts import generate_atomic_note_draft, generate_exercise_drafts
from socrates.kb import build_reference_kb
from socrates.project import ProjectSpec, create_project
from socrates.reports import list_learning_reports
from socrates.tutoring import run_scripted_tutoring_session
from socrates.workflow import close_tutoring_session


REPO_ROOT = Path(__file__).resolve().parents[1]


class SessionCloseoutTests(unittest.TestCase):
    def test_closeout_api_scores_plans_and_refreshes_project_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = _create_passing_session_fixture(root)

            result = close_tutoring_session(
                project,
                session_id="session_0001",
                next_session_id="session_0002",
                as_of=date(2026, 6, 4),
            )

            self.assertEqual(result.status, "ready")
            self.assertEqual(result.session_score, 100)
            self.assertEqual(result.session_score_status, "pass")
            self.assertTrue(result.session_score_report_path.exists())
            self.assertTrue(result.next_session_plan_path.exists())
            self.assertTrue(result.project_summary_path.exists())
            self.assertTrue(result.manifest_path.exists())
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual(manifest["quality_boundary"], "deterministic_session_closeout")
            self.assertEqual(manifest["session_id"], "session_0001")
            self.assertEqual(manifest["next_session_id"], "session_0002")
            self.assertEqual(manifest["status"], "ready")
            self.assertEqual(manifest["session_score_status"], "pass")
            self.assertEqual(manifest["session_score"], 100)
            self.assertEqual(manifest["session_score_manifest_path"], "08_evals/session_score_manifest.json")
            self.assertEqual(
                manifest["next_session_plan_manifest_path"],
                "02_learning_plan/next_session_plan_manifest.json",
            )
            self.assertEqual(manifest["project_summary_path"], "07_exports/reports/project_summary.md")
            summary_text = result.project_summary_path.read_text(encoding="utf-8")
            self.assertIn("## Session Score Snapshot", summary_text)
            self.assertIn("## Next Session Handoff Snapshot", summary_text)
            self.assertIn("## Priority Actions", summary_text)
            self.assertIn("workflow:multi_session_regression", summary_text)
            stale_reports = list_learning_reports(project, status="stale")
            self.assertEqual(
                [report.report_id for report in stale_reports if report.report_id == "project-summary"],
                [],
            )

    def test_closeout_cli_writes_manifest_when_score_needs_attention(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "p"))
            script = root / "session.script"
            script.write_text(
                "topic: Normal Subgroup\n"
                "question: What does normality require?\n"
                "attempt: It requires conjugation invariance.\n",
                encoding="utf-8",
                newline="\n",
            )
            run_scripted_tutoring_session(project, script, session_id="session_0001")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "session",
                    "closeout",
                    "--project",
                    str(project),
                    "--session-id",
                    "session_0001",
                    "--next-session-id",
                    "session_0002",
                    "--as-of",
                    "2026-06-04",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Session closeout: needs_attention", result.stdout)
            self.assertIn("Session score: 0/100 (fail)", result.stdout)
            manifest_path = project / "08_evals" / "session_closeout_manifest.json"
            self.assertTrue(manifest_path.exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "needs_attention")
            self.assertEqual(manifest["session_score_status"], "fail")
            self.assertEqual(manifest["session_score"], 0)
            self.assertTrue((project / "02_learning_plan" / "session_0002_plan.md").exists())
            self.assertTrue((project / "07_exports" / "reports" / "project_summary.md").exists())

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Session closeout: needs_attention", status.stdout)
            self.assertIn("Session closeout sessions: session_0001 -> session_0002", status.stdout)
            self.assertIn("Session closeout score: 0/100 (fail)", status.stdout)

    def test_status_rejects_ready_closeout_with_failed_score_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = _create_passing_session_fixture(root)
            result = close_tutoring_session(
                project,
                session_id="session_0001",
                next_session_id="session_0002",
                as_of=date(2026, 6, 4),
            )
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            manifest["session_score_status"] = "fail"
            result.manifest_path.write_text(
                json.dumps(manifest, indent=2) + "\n",
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
            self.assertIn("Session closeout: invalid", status.stdout)
            self.assertIn("Session closeout sessions: invalid", status.stdout)
            self.assertIn("Session closeout score: invalid", status.stdout)


def _create_passing_session_fixture(root: Path) -> Path:
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
    script = root / "session.script"
    script.write_text(
        "topic: Normal Subgroup\n"
        "goal: Understand normality.\n"
        "question: What does normality require?\n"
        "hint: Check conjugation invariance.\n"
        "hint: Compare gNg^-1=N with elementwise commutativity.\n"
        "attempt: It requires gNg^-1=N.\n"
        "next: Prove kernels are normal.\n",
        encoding="utf-8",
        newline="\n",
    )
    run_scripted_tutoring_session(project, script, session_id="session_0001")
    return project


if __name__ == "__main__":
    unittest.main()
