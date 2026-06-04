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
from socrates.tutoring import run_scripted_tutoring_session
from socrates.workflow import close_tutoring_session


REPO_ROOT = Path(__file__).resolve().parents[1]


class MultiSessionRegressionTests(unittest.TestCase):
    def test_lifecycle_regression_cli_records_passing_multi_session_loop(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = _create_multi_session_fixture(Path(temp_dir), include_next_session=True)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "lifecycle",
                    "regression",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Multi-session regression: pass", result.stdout)
            self.assertIn("Regression checks: 5/5", result.stdout)
            self.assertIn("Regression issues: none", result.stdout)
            manifest_path = project / "08_evals" / "multi_session_regression_manifest.json"
            report_path = project / "08_evals" / "multi_session_regression.md"
            self.assertTrue(report_path.exists())
            self.assertTrue(manifest_path.exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual(manifest["quality_boundary"], "deterministic_multi_session_regression")
            self.assertEqual(manifest["status"], "pass")
            self.assertEqual(manifest["closeout_session_id"], "session_0001")
            self.assertEqual(manifest["next_session_id"], "session_0002")
            self.assertEqual(manifest["passed_checks"], 5)
            self.assertEqual(manifest["total_checks"], 5)
            self.assertEqual(manifest["issues"], [])
            report_text = report_path.read_text(encoding="utf-8")
            self.assertIn("# Multi-Session Regression", report_text)
            self.assertIn("- Session closeout manifest: pass", report_text)
            self.assertIn("- Next session artifacts: pass", report_text)

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Multi-session regression: pass", status.stdout)
            self.assertIn("Multi-session regression checks: 5/5", status.stdout)
            self.assertIn("Multi-session regression issues: none", status.stdout)

    def test_lifecycle_regression_cli_fails_when_next_session_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = _create_multi_session_fixture(Path(temp_dir), include_next_session=False)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "lifecycle",
                    "regression",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("Multi-session regression: fail", result.stdout)
            self.assertIn("Regression checks: 4/5", result.stdout)
            self.assertIn("missing next session artifacts: session_0002", result.stdout)
            manifest = json.loads(
                (project / "08_evals" / "multi_session_regression_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(manifest["status"], "fail")
            self.assertEqual(manifest["issues"], ["missing next session artifacts: session_0002"])

    def test_status_reports_invalid_multi_session_regression_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            (project / "08_evals" / "multi_session_regression_manifest.json").write_text(
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
            self.assertIn("Multi-session regression: invalid", status.stdout)
            self.assertIn("Multi-session regression checks: invalid", status.stdout)
            self.assertIn("Multi-session regression issues: invalid", status.stdout)


def _create_multi_session_fixture(root: Path, *, include_next_session: bool) -> Path:
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
    run_scripted_tutoring_session(
        project,
        root / "session_0001.script",
        session_id="session_0001",
    )
    if include_next_session:
        _write_session_script(root / "session_0002.script", "session_0002")
        run_scripted_tutoring_session(
            project,
            root / "session_0002.script",
            session_id="session_0002",
        )
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
        f"goal: Continue multi-session loop {session_id}.\n"
        "question: What does normality require?\n"
        "hint: Check conjugation invariance.\n"
        "hint: Compare gNg^-1=N with elementwise commutativity.\n"
        "attempt: It requires gNg^-1=N.\n"
        "next: Prove kernels are normal.\n",
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    unittest.main()
