from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from socrates.project import ProjectSpec, create_project


REPO_ROOT = Path(__file__).resolve().parents[1]


class ResumeCommandTests(unittest.TestCase):
    def test_resume_reports_missing_brief_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            project_log = project / "00_meta" / "project_log.md"

            result = self._run_socrates("resume", "--project", str(project))

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("# Resume Project", result.stdout)
            self.assertIn("- Resume state: refresh_brief", result.stdout)
            self.assertIn("- Study brief: not_run", result.stdout)
            self.assertIn("- Study brief path: 07_exports/briefs/study_brief.md", result.stdout)
            self.assertIn("- Current next action: none", result.stdout)
            self.assertIn(
                f'- Recommended command: python -m socrates brief generate --project "{project}"',
                result.stdout,
            )
            self.assertFalse((project / "07_exports" / "briefs" / "study_brief.md").exists())
            self.assertFalse(
                (project / "07_exports" / "briefs" / "study_brief_manifest.json").exists()
            )
            self.assertNotIn(
                "Generated study brief.",
                project_log.read_text(encoding="utf-8"),
            )

    def test_resume_json_reports_missing_brief_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            project_log = project / "00_meta" / "project_log.md"

            result = self._run_socrates("resume", "--project", str(project), "--json")

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["quality_boundary"], "deterministic_project_resume")
            self.assertEqual(payload["project"], "Group Theory")
            self.assertEqual(payload["root"], str(project))
            self.assertEqual(payload["resume_state"], "refresh_brief")
            self.assertEqual(payload["study_brief"], "not_run")
            self.assertEqual(payload["study_brief_path"], "07_exports/briefs/study_brief.md")
            self.assertEqual(payload["current_next_action"], "none")
            self.assertEqual(
                payload["recommended_command"],
                f'python -m socrates brief generate --project "{project}"',
            )
            self.assertFalse((project / "07_exports" / "briefs" / "study_brief.md").exists())
            self.assertFalse(
                (project / "07_exports" / "briefs" / "study_brief_manifest.json").exists()
            )
            self.assertNotIn(
                "Generated study brief.",
                project_log.read_text(encoding="utf-8"),
            )

    def test_resume_reports_current_brief_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            draft = project / "04_atomic_notes" / "drafts" / "normal_subgroup.md"
            draft.write_text("# Normal Subgroup\n\nDraft note.\n", encoding="utf-8", newline="\n")
            next_action = "notes:normal_subgroup | 04_atomic_notes/drafts/normal_subgroup.md"

            generated = self._run_socrates("brief", "generate", "--project", str(project))
            result = self._run_socrates("resume", "--project", str(project))

            self.assertEqual(generated.returncode, 0, generated.stderr)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("- Resume state: ready", result.stdout)
            self.assertIn("- Study brief: current", result.stdout)
            self.assertIn(f"- Current next action: {next_action}", result.stdout)
            self.assertIn("- Recommended command: none", result.stdout)

    def test_resume_json_reports_current_brief_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            draft = project / "04_atomic_notes" / "drafts" / "normal_subgroup.md"
            draft.write_text("# Normal Subgroup\n\nDraft note.\n", encoding="utf-8", newline="\n")
            next_action = "notes:normal_subgroup | 04_atomic_notes/drafts/normal_subgroup.md"

            generated = self._run_socrates("brief", "generate", "--project", str(project))
            markdown = self._run_socrates("resume", "--project", str(project))
            result = self._run_socrates("resume", "--project", str(project), "--json")

            self.assertEqual(generated.returncode, 0, generated.stderr)
            self.assertEqual(markdown.returncode, 0, markdown.stderr)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["quality_boundary"], "deterministic_project_resume")
            self.assertEqual(payload["resume_state"], "ready")
            self.assertEqual(payload["study_brief"], "current")
            self.assertEqual(payload["current_next_action"], next_action)
            self.assertEqual(payload["recommended_command"], "none")
            self.assertIn(f"- Current next action: {next_action}", markdown.stdout)

    def test_resume_reports_stale_brief_refresh_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))

            generated = self._run_socrates("brief", "generate", "--project", str(project))
            draft = project / "04_atomic_notes" / "drafts" / "normal_subgroup.md"
            draft.write_text("# Normal Subgroup\n\nDraft note.\n", encoding="utf-8", newline="\n")
            next_action = "notes:normal_subgroup | 04_atomic_notes/drafts/normal_subgroup.md"
            result = self._run_socrates("resume", "--project", str(project))

            self.assertEqual(generated.returncode, 0, generated.stderr)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("- Resume state: refresh_brief", result.stdout)
            self.assertIn("- Study brief: stale", result.stdout)
            self.assertIn(f"- Current next action: {next_action}", result.stdout)
            self.assertIn(
                f'- Recommended command: python -m socrates brief generate --project "{project}"',
                result.stdout,
            )

    def _run_socrates(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "socrates", *args],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )


if __name__ == "__main__":
    unittest.main()
