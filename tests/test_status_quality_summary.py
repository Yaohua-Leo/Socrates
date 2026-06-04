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


class StatusQualitySummaryTests(unittest.TestCase):
    def test_status_cli_summarizes_artifact_quality_manifests(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "normal_subgroups.curated.md"
            curated.write_text(
                "# Group Theory\n"
                "## Source Metadata\n"
                "- source_id: normality_notes\n"
                "- title: Normality Notes\n"
                "- role: lecture_notes\n"
                "## Normal Subgroups\n"
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
                    "- How is normality different from commutativity?\n"
                ),
                source_id="normality_notes",
            )
            generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="normality_notes",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )
            script = Path(temp_dir) / "session.script"
            script.write_text(
                "topic: Normal Subgroup\n"
                "goal: Distinguish normality from commutativity.\n"
                "question: What must be checked for normality?\n"
                "hint: Use conjugation invariance.\n"
                "hint: Compare gNg^-1=N with elementwise commutativity.\n"
                "attempt: I should check gNg^-1 = N.\n",
                encoding="utf-8",
                newline="\n",
            )
            run_scripted_tutoring_session(project, script, session_id="session_0001")

            for command in (
                ["kb", "check", "--project", str(project)],
                ["note", "check", "--project", str(project)],
                ["exercise", "check", "--project", str(project)],
                ["session", "check", "--project", str(project), "--session-id", "session_0001"],
            ):
                result = subprocess.run(
                    [sys.executable, "-m", "socrates", *command],
                    cwd=REPO_ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Ingestion quality check: pass (1/1 passed, 0 failed)", status.stdout)
            self.assertIn("Note quality check: pass (1/1 passed, 0 failed)", status.stdout)
            self.assertIn("Exercise quality check: pass (5/5 passed, 0 failed)", status.stdout)
            self.assertIn("Tutoring quality check: pass (1/1 passed, 0 failed)", status.stdout)

    def test_status_cli_counts_quality_checks_to_fix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            (project / "08_evals" / "note_quality_manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "checked": 1,
                        "passed": 0,
                        "failed": 1,
                        "notes": [
                            {
                                "id": "normal_subgroup",
                                "path": "04_atomic_notes/drafts/normal_subgroup.md",
                                "quality_status": "fail",
                                "issues": ["missing section Review Questions"],
                            }
                        ],
                    },
                    indent=2,
                )
                + "\n",
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
            self.assertIn("Note quality check: fail (0/1 passed, 1 failed)", status.stdout)
            self.assertIn("Quality checks to fix: 1", status.stdout)


if __name__ == "__main__":
    unittest.main()
