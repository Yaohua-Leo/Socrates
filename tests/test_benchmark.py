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
            self.assertIn("Benchmark score: 100/100", result.stdout)
            self.assertIn("Benchmark manifest:", result.stdout)
            report = project / "08_evals" / "benchmark_report.md"
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("# Benchmark Report", report_text)
            self.assertIn("## Summary", report_text)
            self.assertIn("- Gates passed: 4/4", report_text)
            self.assertIn("- Benchmark score: 100/100", report_text)
            self.assertIn("- Ingestion: pass", report_text)
            self.assertIn("- Note quality: pass", report_text)
            self.assertIn("- Exercise quality: pass", report_text)
            self.assertIn("- Tutoring quality: pass", report_text)
            manifest = json.loads(
                (project / "08_evals" / "benchmark_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual(manifest["score"], 100)
            self.assertEqual(manifest["passed_gates"], 4)
            self.assertEqual(manifest["total_gates"], 4)
            gates = manifest["gates"]
            self.assertEqual(
                [gate["name"] for gate in gates],
                [
                    "Ingestion",
                    "Note quality",
                    "Exercise quality",
                    "Tutoring quality",
                ],
            )
            self.assertTrue(all(gate["passed"] for gate in gates))
            self.assertEqual(gates[0]["checked"], 1)
            self.assertEqual(gates[0]["failed"], 0)
            self.assertEqual(gates[0]["report_path"], "08_evals/ingestion_eval.md")
            self.assertEqual(
                gates[0]["manifest_path"],
                "08_evals/ingestion_quality_manifest.json",
            )
            self.assertEqual(
                gates[1]["manifest_path"],
                "08_evals/note_quality_manifest.json",
            )
            self.assertEqual(
                gates[2]["manifest_path"],
                "08_evals/exercise_quality_manifest.json",
            )
            self.assertEqual(
                gates[3]["manifest_path"],
                "08_evals/tutoring_quality_manifest.json",
            )
            self.assertEqual(gates[3]["session_id"], "session_0001")
            self.assertEqual(gates[3]["status"], "pass")

            status = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "status",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Current phase: benchmark_ready", status.stdout)
            self.assertIn("Benchmark score: 100/100", status.stdout)
            self.assertIn("Benchmark gates: 4/4", status.stdout)
            self.assertIn("Benchmark failed gates: none", status.stdout)

            benchmark_status = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "benchmark",
                    "status",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(benchmark_status.returncode, 0, benchmark_status.stderr)
            self.assertIn("# Benchmark Status", benchmark_status.stdout)
            self.assertIn("- Score: 100/100", benchmark_status.stdout)
            self.assertIn("- Gates passed: 4/4", benchmark_status.stdout)
            self.assertIn("- Failed gates: none", benchmark_status.stdout)
            self.assertIn(
                "- Ingestion: pass | checked 1 | failed 0",
                benchmark_status.stdout,
            )
            self.assertIn("  - report: 08_evals/ingestion_eval.md", benchmark_status.stdout)
            self.assertIn(
                "  - manifest: 08_evals/ingestion_quality_manifest.json",
                benchmark_status.stdout,
            )

    def test_benchmark_status_cli_reports_not_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(
                ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p")
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "benchmark",
                    "status",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("# Benchmark Status", result.stdout)
            self.assertIn("- not run", result.stdout)
            self.assertIn("- manifest: 08_evals/benchmark_manifest.json", result.stdout)

    def test_status_lists_failed_benchmark_gates_from_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(
                ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p")
            )
            manifest_path = project / "08_evals" / "benchmark_manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
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
                    },
                    indent=2,
                ),
                encoding="utf-8",
                newline="\n",
            )

            status = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "status",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Current phase: benchmark_ready", status.stdout)
            self.assertIn("Benchmark score: 75/100", status.stdout)
            self.assertIn("Benchmark gates: 3/4", status.stdout)
            self.assertIn("Benchmark failed gates: Tutoring quality", status.stdout)

            benchmark_status = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "benchmark",
                    "status",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(benchmark_status.returncode, 0, benchmark_status.stderr)
            self.assertIn("- Score: 75/100", benchmark_status.stdout)
            self.assertIn("- Gates passed: 3/4", benchmark_status.stdout)
            self.assertIn("- Failed gates: Tutoring quality", benchmark_status.stdout)
            self.assertIn(
                "- Tutoring quality: fail | checked unknown | failed unknown",
                benchmark_status.stdout,
            )


if __name__ == "__main__":
    unittest.main()
