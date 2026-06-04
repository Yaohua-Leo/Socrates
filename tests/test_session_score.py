from __future__ import annotations

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


REPO_ROOT = Path(__file__).resolve().parents[1]


class SessionScoreTests(unittest.TestCase):
    def test_session_score_cli_writes_report_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
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

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "session",
                    "score",
                    "--project",
                    str(project),
                    "--session-id",
                    "session_0001",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Scored session session_0001: 100/100", result.stdout)
            self.assertIn("Session score gates: 5/5", result.stdout)
            self.assertIn("Session score manifest:", result.stdout)
            report = project / "08_evals" / "session_score_report.md"
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("# Session Score Report", report_text)
            self.assertIn("- Session: session_0001", report_text)
            self.assertIn("- Session score: 100/100", report_text)
            self.assertIn("- Gates passed: 5/5", report_text)
            self.assertIn("- Ingestion: pass", report_text)
            self.assertIn("- Note quality: pass", report_text)
            self.assertIn("- Exercise quality: pass", report_text)
            self.assertIn("- Exercise validation: pass", report_text)
            self.assertIn("- Tutoring quality: pass", report_text)
            manifest = json.loads(
                (project / "08_evals" / "session_score_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual(manifest["session_id"], "session_0001")
            self.assertEqual(manifest["status"], "pass")
            self.assertEqual(manifest["score"], 100)
            self.assertEqual(manifest["passed_gates"], 5)
            self.assertEqual(manifest["total_gates"], 5)
            self.assertEqual(
                [gate["name"] for gate in manifest["gates"]],
                [
                    "Ingestion",
                    "Note quality",
                    "Exercise quality",
                    "Exercise validation",
                    "Tutoring quality",
                ],
            )
            self.assertTrue(all(gate["passed"] for gate in manifest["gates"]))
            self.assertEqual(
                manifest["gates"][0]["manifest_path"],
                "08_evals/ingestion_quality_manifest.json",
            )
            self.assertEqual(
                manifest["gates"][3]["manifest_path"],
                "08_evals/exercise_validation_manifest.json",
            )
            self.assertEqual(manifest["gates"][4]["session_id"], "session_0001")
            self.assertEqual(manifest["quality_boundary"], "advisory_checklist")

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Session score: 100/100", status.stdout)
            self.assertIn("Session score gates: 5/5", status.stdout)
            self.assertIn("Session score failed gates: none", status.stdout)

    def test_session_score_cli_records_failed_gates_without_failing_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(ProjectSpec(topic="Group Theory", path=root / "p"))
            incomplete = project / "03_sessions" / "session_0001"
            incomplete.mkdir()
            (incomplete / "transcript.md").write_text(
                "# Tutoring Session: session_0001\n"
                "Tutor follow-up: Here is the full solution.\n",
                encoding="utf-8",
                newline="\n",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "session",
                    "score",
                    "--project",
                    str(project),
                    "--session-id",
                    "session_0001",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Scored session session_0001: 0/100", result.stdout)
            self.assertIn("Session score gates: 0/5", result.stdout)
            manifest = json.loads(
                (project / "08_evals" / "session_score_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(manifest["status"], "fail")
            self.assertEqual(manifest["score"], 0)
            self.assertEqual(manifest["passed_gates"], 0)
            self.assertEqual(
                [gate["name"] for gate in manifest["gates"] if not gate["passed"]],
                [
                    "Ingestion",
                    "Note quality",
                    "Exercise quality",
                    "Exercise validation",
                    "Tutoring quality",
                ],
            )


if __name__ == "__main__":
    unittest.main()
