from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


class V01CliFlowTests(unittest.TestCase):
    def test_group_theory_learning_loop_from_cli(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "group_theory"
            reference = root / "normal_subgroups.md"
            script = root / "session_script.md"
            reference.write_text("# Normal Subgroups\nA normal subgroup is invariant under conjugation.\n", encoding="utf-8")
            script.write_text(
                "\n".join(
                    [
                        "topic: Normal Subgroup",
                        "goal: Understand normality as conjugation invariance.",
                        "question: What must be checked to prove N is normal in G?",
                        "hint: Compare gNg^-1 with N.",
                        "attempt: I should show gng^-1 stays inside N for every g and n.",
                        "misconception: normal_equals_central",
                        "next: Try proving kernels are normal subgroups.",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            self._run_cli(
                "init",
                "--topic",
                "Group Theory",
                "--path",
                str(project),
                "--goal",
                "Prepare for representation theory.",
            )
            self._run_cli(
                "import",
                "--project",
                str(project),
                str(reference),
                "--role",
                "lecture_notes",
                "--title",
                "Normal Subgroups Notes",
            )
            self._run_cli("plan", "--project", str(project))
            self._run_cli(
                "teach",
                "--project",
                str(project),
                "--session-id",
                "session_0001",
                "--script",
                str(script),
            )
            status = self._run_cli("status", "--project", str(project))

            self.assertIn("Current phase: tutoring_complete", status.stdout)
            self.assertIn("Imported sources: 1", status.stdout)
            self.assertIn("Latest session: session_0001", status.stdout)
            self.assertIn("Pending draft notes: 1", status.stdout)
            self.assertIn("Generated exercises: 5", status.stdout)

            self.assertTrue((project / "02_learning_plan" / "session_0001_plan.md").exists())
            self.assertTrue((project / "03_sessions" / "session_0001" / "transcript.md").exists())
            self.assertTrue((project / "04_atomic_notes" / "drafts" / "normal_subgroup.md").exists())
            exercises = list((project / "05_exercises" / "generated").glob("normal_subgroup_*.md"))
            self.assertEqual(len(exercises), 5)
            self.assertIn("normal_equals_central", (project / "05_exercises" / "mistake_bank.md").read_text(encoding="utf-8"))

            learning_state = json.loads(
                (project / "00_meta" / "learning_state.json").read_text(encoding="utf-8")
            )
            self.assertIn("normal_subgroup", learning_state["concept_mastery"])
            self.assertEqual(
                learning_state["misconceptions"]["normal_equals_central"]["count"],
                1,
            )

    def test_teach_detects_common_misconception_without_script_label(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "group_theory"
            script = root / "session_script.md"
            script.write_text(
                "\n".join(
                    [
                        "topic: Normal Subgroup",
                        "goal: Distinguish normality from centrality.",
                        "question: What does normality require?",
                        "hint: Compare conjugation invariance with commutativity.",
                        "attempt: A normal subgroup means every element commutes with everything.",
                        "next: Contrast gNg^-1=N with gn=ng.",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            self._run_cli(
                "init",
                "--topic",
                "Group Theory",
                "--path",
                str(project),
            )
            self._run_cli(
                "teach",
                "--project",
                str(project),
                "--session-id",
                "session_0001",
                "--script",
                str(script),
            )

            learning_state = json.loads(
                (project / "00_meta" / "learning_state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                learning_state["misconceptions"]["normal_equals_central"]["count"],
                1,
            )
            mistake_bank = (project / "05_exercises" / "mistake_bank.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("- Misconception: normal_equals_central", mistake_bank)
            self.assertIn("Confuses normality with commutativity or centrality.", mistake_bank)

    def _run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, "-m", "socrates", *args],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result


if __name__ == "__main__":
    unittest.main()
