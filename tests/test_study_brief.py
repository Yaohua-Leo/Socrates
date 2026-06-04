from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from socrates.project import ProjectSpec, create_project


REPO_ROOT = Path(__file__).resolve().parents[1]


class StudyBriefTests(unittest.TestCase):
    def test_brief_cli_writes_startup_brief_from_dashboard_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            draft = project / "04_atomic_notes" / "drafts" / "normal_subgroup.md"
            draft.write_text("# Normal Subgroup\n\nDraft note.\n", encoding="utf-8", newline="\n")

            result = subprocess.run(
                [sys.executable, "-m", "socrates", "brief", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Wrote study brief:", result.stdout)
            brief = project / "07_exports" / "briefs" / "study_brief.md"
            self.assertTrue(brief.exists())
            text = brief.read_text(encoding="utf-8")
            self.assertIn("# Study Brief", text)
            self.assertIn("## Start Here", text)
            self.assertIn("- Project: Group Theory", text)
            self.assertIn(
                "- Next action: notes:normal_subgroup | "
                "04_atomic_notes/drafts/normal_subgroup.md",
                text,
            )
            self.assertIn("- Action type: human_review", text)
            self.assertIn("## Dashboard Evidence", text)
            self.assertIn("## Study Dashboard", text)
            self.assertIn("### Action Summary", text)
            self.assertIn("### Top Priority Actions", text)
            self.assertIn("### Report Health", text)
            self.assertIn("## Boundary", text)
            self.assertIn("does not run repairs", text)
            project_log = project / "00_meta" / "project_log.md"
            self.assertIn("Generated study brief.", project_log.read_text(encoding="utf-8"))

    def test_brief_cli_handles_clear_project_without_fake_action(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))

            result = subprocess.run(
                [sys.executable, "-m", "socrates", "brief", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            brief = project / "07_exports" / "briefs" / "study_brief.md"
            text = brief.read_text(encoding="utf-8")
            self.assertIn("- Next action: none", text)
            self.assertIn("- Action type: none", text)
            self.assertIn("### Top Priority Actions", text)
            self.assertIn("- none", text)

    def test_brief_cli_writes_structured_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            draft = project / "04_atomic_notes" / "drafts" / "normal_subgroup.md"
            draft.write_text("# Normal Subgroup\n\nDraft note.\n", encoding="utf-8", newline="\n")

            result = self._run_socrates("brief", "--project", str(project))

            self.assertEqual(result.returncode, 0, result.stderr)
            manifest_path = project / "07_exports" / "briefs" / "study_brief_manifest.json"
            self.assertTrue(manifest_path.exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual(manifest["quality_boundary"], "deterministic_study_brief")
            self.assertEqual(manifest["status"], "generated")
            self.assertEqual(manifest["brief_path"], "07_exports/briefs/study_brief.md")
            self.assertEqual(
                manifest["recorded_next_action"],
                "notes:normal_subgroup | 04_atomic_notes/drafts/normal_subgroup.md",
            )
            self.assertEqual(manifest["action_type"], "human_review")

    def test_brief_status_cli_reports_missing_brief_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            project_log = project / "00_meta" / "project_log.md"

            result = self._run_socrates("brief", "status", "--project", str(project))

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Study brief: not_run", result.stdout)
            self.assertIn("Study brief path: 07_exports/briefs/study_brief.md", result.stdout)
            self.assertIn("Study brief recorded next action: none", result.stdout)
            self.assertIn("Study brief current next action: none", result.stdout)
            self.assertFalse((project / "07_exports" / "briefs" / "study_brief.md").exists())
            self.assertFalse(
                (project / "07_exports" / "briefs" / "study_brief_manifest.json").exists()
            )
            self.assertNotIn(
                "Generated study brief.",
                project_log.read_text(encoding="utf-8"),
            )

    def test_brief_generate_cli_writes_then_status_reports_current(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            draft = project / "04_atomic_notes" / "drafts" / "normal_subgroup.md"
            draft.write_text("# Normal Subgroup\n\nDraft note.\n", encoding="utf-8", newline="\n")
            next_action = "notes:normal_subgroup | 04_atomic_notes/drafts/normal_subgroup.md"

            generated = self._run_socrates("brief", "generate", "--project", str(project))
            status = self._run_socrates("brief", "status", "--project", str(project))

            self.assertEqual(generated.returncode, 0, generated.stderr)
            self.assertIn("Wrote study brief:", generated.stdout)
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Study brief: current", status.stdout)
            self.assertIn("Study brief path: 07_exports/briefs/study_brief.md", status.stdout)
            self.assertIn(f"Study brief recorded next action: {next_action}", status.stdout)
            self.assertIn(f"Study brief current next action: {next_action}", status.stdout)

    def test_brief_status_cli_marks_corrupt_manifest_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            draft = project / "04_atomic_notes" / "drafts" / "normal_subgroup.md"
            draft.write_text("# Normal Subgroup\n\nDraft note.\n", encoding="utf-8", newline="\n")

            generated = self._run_socrates("brief", "generate", "--project", str(project))
            self.assertEqual(generated.returncode, 0, generated.stderr)
            manifest_path = project / "07_exports" / "briefs" / "study_brief_manifest.json"
            manifest_path.write_text("{not valid json\n", encoding="utf-8", newline="\n")
            status = self._run_socrates("brief", "status", "--project", str(project))

            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Study brief: invalid", status.stdout)
            self.assertIn("Study brief recorded next action: invalid", status.stdout)

    def test_dashboard_and_status_mark_corrupt_study_brief_manifest_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            draft = project / "04_atomic_notes" / "drafts" / "normal_subgroup.md"
            draft.write_text("# Normal Subgroup\n\nDraft note.\n", encoding="utf-8", newline="\n")
            brief = self._run_socrates("brief", "--project", str(project))
            manifest_path = project / "07_exports" / "briefs" / "study_brief_manifest.json"
            manifest_path.write_text("{not valid json\n", encoding="utf-8", newline="\n")

            dashboard = self._run_socrates("dashboard", "--project", str(project))
            status = self._run_socrates("status", "--project", str(project))

            self.assertEqual(brief.returncode, 0, brief.stderr)
            self.assertEqual(dashboard.returncode, 0, dashboard.stderr)
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("- Study brief: invalid", dashboard.stdout)
            self.assertIn("Study brief: invalid", status.stdout)

    def test_dashboard_and_status_fall_back_to_legacy_markdown_brief(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            draft = project / "04_atomic_notes" / "drafts" / "normal_subgroup.md"
            draft.write_text("# Normal Subgroup\n\nDraft note.\n", encoding="utf-8", newline="\n")
            next_action = "notes:normal_subgroup | 04_atomic_notes/drafts/normal_subgroup.md"
            brief = self._run_socrates("brief", "--project", str(project))
            manifest_path = project / "07_exports" / "briefs" / "study_brief_manifest.json"
            manifest_path.unlink()

            dashboard = self._run_socrates("dashboard", "--project", str(project))
            status = self._run_socrates("status", "--project", str(project))

            self.assertEqual(brief.returncode, 0, brief.stderr)
            self.assertEqual(dashboard.returncode, 0, dashboard.stderr)
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("- Study brief: current", dashboard.stdout)
            self.assertIn(f"- Study brief recorded next action: {next_action}", dashboard.stdout)
            self.assertIn("Study brief: current", status.stdout)
            self.assertIn(f"Study brief recorded next action: {next_action}", status.stdout)

    def test_dashboard_and_status_show_missing_study_brief(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))

            dashboard = self._run_socrates("dashboard", "--project", str(project))
            status = self._run_socrates("status", "--project", str(project))

            self.assertEqual(dashboard.returncode, 0, dashboard.stderr)
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("- Study brief: not_run", dashboard.stdout)
            self.assertIn("- Study brief recorded next action: none", dashboard.stdout)
            self.assertIn("- Study brief current next action: none", dashboard.stdout)
            self.assertIn("Study brief: not_run", status.stdout)
            self.assertIn("Study brief recorded next action: none", status.stdout)
            self.assertIn("Study brief current next action: none", status.stdout)

    def test_dashboard_and_status_show_current_study_brief(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            draft = project / "04_atomic_notes" / "drafts" / "normal_subgroup.md"
            draft.write_text("# Normal Subgroup\n\nDraft note.\n", encoding="utf-8", newline="\n")
            next_action = "notes:normal_subgroup | 04_atomic_notes/drafts/normal_subgroup.md"

            brief = self._run_socrates("brief", "--project", str(project))
            dashboard = self._run_socrates("dashboard", "--project", str(project))
            status = self._run_socrates("status", "--project", str(project))

            self.assertEqual(brief.returncode, 0, brief.stderr)
            self.assertEqual(dashboard.returncode, 0, dashboard.stderr)
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("- Study brief: current", dashboard.stdout)
            self.assertIn(f"- Study brief recorded next action: {next_action}", dashboard.stdout)
            self.assertIn(f"- Study brief current next action: {next_action}", dashboard.stdout)
            self.assertIn("Study brief: current", status.stdout)
            self.assertIn(f"Study brief recorded next action: {next_action}", status.stdout)
            self.assertIn(f"Study brief current next action: {next_action}", status.stdout)

    def test_dashboard_and_status_mark_study_brief_stale_after_queue_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))

            brief = self._run_socrates("brief", "--project", str(project))
            draft = project / "04_atomic_notes" / "drafts" / "normal_subgroup.md"
            draft.write_text("# Normal Subgroup\n\nDraft note.\n", encoding="utf-8", newline="\n")
            next_action = "notes:normal_subgroup | 04_atomic_notes/drafts/normal_subgroup.md"
            dashboard = self._run_socrates("dashboard", "--project", str(project))
            status = self._run_socrates("status", "--project", str(project))

            self.assertEqual(brief.returncode, 0, brief.stderr)
            self.assertEqual(dashboard.returncode, 0, dashboard.stderr)
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("- Study brief: stale", dashboard.stdout)
            self.assertIn("- Study brief recorded next action: none", dashboard.stdout)
            self.assertIn(f"- Study brief current next action: {next_action}", dashboard.stdout)
            self.assertIn("Study brief: stale", status.stdout)
            self.assertIn("Study brief recorded next action: none", status.stdout)
            self.assertIn(f"Study brief current next action: {next_action}", status.stdout)

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
