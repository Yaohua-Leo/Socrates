from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from socrates.project import ProjectSpec, create_project
from socrates.tutoring import run_scripted_tutoring_session


REPO_ROOT = Path(__file__).resolve().parents[1]


class TutoringQualityTests(unittest.TestCase):
    def test_session_check_cli_writes_tutoring_quality_report(self) -> None:
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
            self.assertIn("Checked session session_0001: pass", result.stdout)
            report = project / "08_evals" / "tutoring_eval.md"
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("# Tutoring Eval", report_text)
            self.assertIn("## Session Quality Check: session_0001", report_text)
            self.assertIn("- Status: pass", report_text)
            self.assertIn("- Missing artifacts: none", report_text)
            self.assertIn("- Premature solution: no", report_text)
            self.assertIn("### Rubric", report_text)
            self.assertIn("- Required artifacts: 25/25", report_text)
            self.assertIn("- Tutor question: 25/25", report_text)
            self.assertIn("- Hint ladder: 25/25", report_text)
            self.assertIn("- Attempt before solution: 25/25", report_text)
            self.assertIn("- Total score: 100/100", report_text)


if __name__ == "__main__":
    unittest.main()
