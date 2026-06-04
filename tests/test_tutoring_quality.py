from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from socrates.project import ProjectSpec, create_project
from socrates.tutoring import run_scripted_tutoring_session


REPO_ROOT = Path(__file__).resolve().parents[1]


class TutoringQualityTests(unittest.TestCase):
    def test_session_list_cli_shows_complete_and_incomplete_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            script = Path(temp_dir) / "session.script"
            script.write_text(
                "topic: Normal Subgroup\n"
                "goal: Distinguish normality from commutativity.\n"
                "question: What must be checked for normality?\n"
                "hint: Use conjugation invariance.\n"
                "hint: Compare gNg^-1=N with elementwise commutativity.\n"
                "attempt: I should check gNg^-1 = N.\n"
                "next: Try proving kernels are normal.\n",
                encoding="utf-8",
                newline="\n",
            )
            run_scripted_tutoring_session(project, script, session_id="session_0001")
            incomplete = project / "03_sessions" / "session_0002"
            incomplete.mkdir()
            (incomplete / "transcript.md").write_text(
                "# Tutoring Session: session_0002\n",
                encoding="utf-8",
                newline="\n",
            )

            all_sessions = subprocess.run(
                [sys.executable, "-m", "socrates", "session", "list", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            incomplete_sessions = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "session",
                    "list",
                    "--project",
                    str(project),
                    "--status",
                    "incomplete",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(all_sessions.returncode, 0, all_sessions.stderr)
            complete = "- session_0001 | complete | 03_sessions/session_0001"
            missing = "- session_0002 | incomplete | 03_sessions/session_0002"
            self.assertIn("# Tutoring Sessions", all_sessions.stdout)
            self.assertIn(complete, all_sessions.stdout)
            self.assertIn("  - missing: none", all_sessions.stdout)
            self.assertIn(missing, all_sessions.stdout)
            self.assertIn(
                (
                    "  - missing: tutor_notes.md, detected_misconceptions.md, "
                    "summary.md, next_actions.md"
                ),
                all_sessions.stdout,
            )
            self.assertLess(all_sessions.stdout.index(complete), all_sessions.stdout.index(missing))

            self.assertEqual(incomplete_sessions.returncode, 0, incomplete_sessions.stderr)
            self.assertIn(missing, incomplete_sessions.stdout)
            self.assertNotIn("session_0001", incomplete_sessions.stdout)

    def test_session_check_cli_writes_tutoring_quality_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            script = Path(temp_dir) / "session.script"
            script.write_text(
                "topic: Normal Subgroup\n"
                "goal: Distinguish normality from commutativity.\n"
                "question: What must be checked for normality?\n"
                "hint: Use conjugation invariance.\n"
                "hint: Compare gNg^-1=N with elementwise commutativity.\n"
                "attempt: I should check gNg^-1 = N.\n"
                "next: Try proving kernels are normal.\n",
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
                    "check",
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
            self.assertIn("Checked session session_0001: pass", result.stdout)
            self.assertIn("Tutoring quality manifest:", result.stdout)
            report = project / "08_evals" / "tutoring_eval.md"
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("# Tutoring Eval", report_text)
            self.assertIn("## Session Quality Check: session_0001", report_text)
            self.assertIn("- Status: pass", report_text)
            self.assertIn("- Missing artifacts: none", report_text)
            self.assertIn("- Tutor question present: yes", report_text)
            self.assertIn("- Hint count: 2", report_text)
            self.assertIn("- Student attempts: 1", report_text)
            self.assertIn("- Premature solution: no", report_text)
            self.assertIn("### Rubric", report_text)
            self.assertIn("- Required artifacts: 25/25", report_text)
            self.assertIn("- Tutor question: 25/25", report_text)
            self.assertIn("- Hint ladder: 25/25", report_text)
            self.assertIn("- Attempt before solution: 25/25", report_text)
            self.assertIn("- Total score: 100/100", report_text)
            manifest = json.loads(
                (project / "08_evals" / "tutoring_quality_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual(manifest["checked"], 1)
            self.assertEqual(manifest["passed"], 1)
            self.assertEqual(manifest["failed"], 0)
            session = manifest["sessions"][0]
            self.assertEqual(session["session_id"], "session_0001")
            self.assertEqual(session["path"], "03_sessions/session_0001")
            self.assertEqual(session["status"], "pass")
            self.assertEqual(session["missing_artifacts"], [])
            self.assertEqual(session["transcript_checks"]["has_tutor_question"], True)
            self.assertEqual(session["transcript_checks"]["hint_count"], 2)
            self.assertEqual(session["transcript_checks"]["student_attempt_count"], 1)
            self.assertEqual(session["transcript_checks"]["premature_solution"], False)
            self.assertEqual(session["rubric"]["Required artifacts"], 25)
            self.assertEqual(session["total_score"], 100)
            self.assertEqual(session["artifacts"]["transcript.md"]["exists"], True)

    def test_session_list_cli_shows_checked_quality_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            script = Path(temp_dir) / "session.script"
            script.write_text(
                "topic: Normal Subgroup\n"
                "goal: Distinguish normality from commutativity.\n"
                "question: What must be checked for normality?\n"
                "hint: Use conjugation invariance.\n"
                "hint: Compare gNg^-1=N with elementwise commutativity.\n"
                "attempt: I should check gNg^-1 = N.\n"
                "next: Try proving kernels are normal.\n",
                encoding="utf-8",
                newline="\n",
            )
            run_scripted_tutoring_session(project, script, session_id="session_0001")

            check = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "session",
                    "check",
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
            sessions = subprocess.run(
                [sys.executable, "-m", "socrates", "session", "list", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(check.returncode, 0, check.stderr)
            self.assertEqual(sessions.returncode, 0, sessions.stderr)
            self.assertIn("- session_0001 | complete | 03_sessions/session_0001", sessions.stdout)
            self.assertIn("  - quality: pass, score 100/100", sessions.stdout)

    def test_session_check_manifest_preserves_multiple_checked_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            script = Path(temp_dir) / "session.script"
            script.write_text(
                "topic: Normal Subgroup\n"
                "question: What must be checked for normality?\n"
                "hint: Use conjugation invariance.\n"
                "hint: Contrast normality with centrality.\n"
                "attempt: I should check gNg^-1 = N.\n",
                encoding="utf-8",
                newline="\n",
            )
            run_scripted_tutoring_session(project, script, session_id="session_0001")
            incomplete = project / "03_sessions" / "session_0002"
            incomplete.mkdir()
            (incomplete / "transcript.md").write_text(
                "# Tutoring Session: session_0002\n"
                "Tutor follow-up: Here is the full solution.\n",
                encoding="utf-8",
                newline="\n",
            )

            first = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "session",
                    "check",
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
            second = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "session",
                    "check",
                    "--project",
                    str(project),
                    "--session-id",
                    "session_0002",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertIn("Checked session session_0002: fail", second.stdout)
            manifest = json.loads(
                (project / "08_evals" / "tutoring_quality_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(manifest["checked"], 2)
            self.assertEqual(manifest["passed"], 1)
            self.assertEqual(manifest["failed"], 1)
            self.assertEqual(
                [session["session_id"] for session in manifest["sessions"]],
                ["session_0001", "session_0002"],
            )
            failed_session = manifest["sessions"][1]
            self.assertEqual(failed_session["status"], "fail")
            self.assertIn("missing required session artifacts", failed_session["issues"])
            self.assertIn("missing tutor question", failed_session["issues"])
            self.assertIn("missing first hint", failed_session["issues"])
            self.assertIn("premature full solution", failed_session["issues"])
            self.assertEqual(
                failed_session["missing_artifacts"],
                [
                    "tutor_notes.md",
                    "detected_misconceptions.md",
                    "summary.md",
                    "next_actions.md",
                ],
            )

    def test_session_check_requires_student_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            script = Path(temp_dir) / "session.script"
            script.write_text(
                "topic: Normal Subgroup\n"
                "goal: Distinguish normality from commutativity.\n"
                "question: What must be checked for normality?\n"
                "hint: Use conjugation invariance.\n"
                "next: Try proving kernels are normal.\n",
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
                    "check",
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
            self.assertIn("Checked session session_0001: fail", result.stdout)
            report_text = (project / "08_evals" / "tutoring_eval.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("- missing student attempt", report_text)
            self.assertIn("- Attempt before solution: 0/25", report_text)
            manifest = json.loads(
                (project / "08_evals" / "tutoring_quality_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            session = manifest["sessions"][0]
            self.assertEqual(session["status"], "fail")
            self.assertEqual(session["transcript_checks"]["student_attempt_count"], 0)
            self.assertIn("missing student attempt", session["issues"])
            self.assertEqual(session["rubric"]["Attempt before solution"], 0)

    def test_session_check_requires_multistep_hint_ladder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            script = Path(temp_dir) / "session.script"
            script.write_text(
                "topic: Normal Subgroup\n"
                "goal: Distinguish normality from commutativity.\n"
                "question: What must be checked for normality?\n"
                "hint: Use conjugation invariance.\n"
                "attempt: I should check gNg^-1 = N.\n"
                "next: Try proving kernels are normal.\n",
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
                    "check",
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
            self.assertIn("Checked session session_0001: fail", result.stdout)
            report_text = (project / "08_evals" / "tutoring_eval.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("- incomplete hint ladder", report_text)
            self.assertIn("- Hint ladder: 0/25", report_text)
            manifest = json.loads(
                (project / "08_evals" / "tutoring_quality_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            session = manifest["sessions"][0]
            self.assertEqual(session["status"], "fail")
            self.assertEqual(session["transcript_checks"]["hint_count"], 1)
            self.assertIn("incomplete hint ladder", session["issues"])
            self.assertEqual(session["rubric"]["Hint ladder"], 0)


if __name__ == "__main__":
    unittest.main()
