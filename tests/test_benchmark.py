from __future__ import annotations

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


class BenchmarkTests(unittest.TestCase):
    def test_benchmark_run_cli_writes_project_quality_summary(self) -> None:
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
                    "benchmark",
                    "run",
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
            self.assertIn("Benchmark passed 4/4 gates", result.stdout)
            report = project / "08_evals" / "benchmark_report.md"
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("# Benchmark Report", report_text)
            self.assertIn("- Ingestion: pass", report_text)
            self.assertIn("- Note quality: pass", report_text)
            self.assertIn("- Exercise quality: pass", report_text)
            self.assertIn("- Tutoring quality: pass", report_text)


if __name__ == "__main__":
    unittest.main()
