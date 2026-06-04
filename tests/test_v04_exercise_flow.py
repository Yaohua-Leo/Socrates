from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from socrates.artifacts import generate_atomic_note_draft, generate_exercise_drafts
from socrates.exercises import approve_exercise_draft
from socrates.kb import build_reference_kb
from socrates.project import ProjectSpec, create_project
from socrates.tutoring import run_scripted_tutoring_session


REPO_ROOT = Path(__file__).resolve().parents[1]


class V04ExerciseFlowTests(unittest.TestCase):
    def test_v04_exercise_validation_bank_and_benchmark_flow(self) -> None:
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
                "Depends: subgroup, conjugation\n\n"
                "### Counterexample: Non-normal Subgroup\n"
                "A subgroup can fail to be stable under conjugation.\n"
                "Counterexample to: normal_subgroup\n",
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
            approve_exercise_draft(project, "normal_subgroup_01")
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

            validate = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "exercise",
                    "validate",
                    "--project",
                    str(project),
                    "--all",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            bank = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "exercise",
                    "bank",
                    "build",
                    "--project",
                    str(project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            benchmark = subprocess.run(
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

            self.assertEqual(validate.returncode, 0, validate.stderr)
            self.assertIn("Validated 5 exercise drafts: 5 passed, 0 failed", validate.stdout)
            self.assertEqual(bank.returncode, 0, bank.stderr)
            self.assertIn("Exercise bank entries: 1", bank.stdout)
            self.assertEqual(benchmark.returncode, 0, benchmark.stderr)
            self.assertIn("Benchmark passed 5/5 gates", benchmark.stdout)
            self.assertTrue((project / "05_exercises" / "exercise_bank_manifest.json").exists())
            self.assertTrue((project / "08_evals" / "exercise_validation_manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
