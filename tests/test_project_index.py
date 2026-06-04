from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from socrates.artifacts import generate_atomic_note_draft
from socrates.notes import review_atomic_note
from socrates.project import ProjectSpec, create_project


REPO_ROOT = Path(__file__).resolve().parents[1]


class ProjectIndexTests(unittest.TestCase):
    def test_projects_scan_writes_index_for_multiple_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "SocratesProjects"
            create_project(ProjectSpec(topic="Group Theory", path=root / "group_theory"))
            create_project(
                ProjectSpec(
                    topic="Homological Algebra",
                    path=root / "homological_algebra",
                    goal="Prepare for derived categories.",
                )
            )
            (root / "loose_notes").mkdir()

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "projects",
                    "scan",
                    "--root",
                    str(root),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Indexed 2 projects", result.stdout)
            index_path = root / "socrates_projects.json"
            index = json.loads(index_path.read_text(encoding="utf-8"))
            self.assertEqual(index["version"], 1)
            self.assertEqual(
                [project["id"] for project in index["projects"]],
                ["group_theory", "homological_algebra"],
            )
            self.assertEqual(index["projects"][0]["title"], "Group Theory")
            self.assertEqual(index["projects"][0]["status"], "active")
            self.assertEqual(index["projects"][0]["path"], "group_theory")
            self.assertNotIn("loose_notes", json.dumps(index, ensure_ascii=False))

    def test_projects_list_reads_index_or_scans_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "SocratesProjects"
            create_project(ProjectSpec(topic="Group Theory", path=root / "group_theory"))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "projects",
                    "list",
                    "--root",
                    str(root),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("group_theory | Group Theory | active | group_theory", result.stdout)

    def test_projects_list_rescans_when_cached_index_is_corrupt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "SocratesProjects"
            root.mkdir()
            create_project(ProjectSpec(topic="Group Theory", path=root / "group_theory"))
            (root / "socrates_projects.json").write_text(
                "{not valid json",
                encoding="utf-8",
                newline="\n",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "projects",
                    "list",
                    "--root",
                    str(root),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("group_theory | Group Theory | active | group_theory", result.stdout)
            self.assertNotIn("Expecting property name", result.stderr)

    def test_projects_list_rescans_when_cached_index_schema_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "SocratesProjects"
            root.mkdir()
            create_project(ProjectSpec(topic="Group Theory", path=root / "group_theory"))
            (root / "socrates_projects.json").write_text(
                json.dumps({"version": 1, "projects": "not a list"}),
                encoding="utf-8",
                newline="\n",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "projects",
                    "list",
                    "--root",
                    str(root),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("group_theory | Group Theory | active | group_theory", result.stdout)
            self.assertNotIn("No Socrates projects found", result.stdout)

    def test_projects_resume_lists_per_project_resume_state_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "SocratesProjects"
            ready_project = create_project(
                ProjectSpec(topic="Group Theory", path=root / "group_theory")
            )
            fresh_project = create_project(
                ProjectSpec(topic="Ring Theory", path=root / "ring_theory")
            )
            draft = ready_project / "04_atomic_notes" / "drafts" / "normal_subgroup.md"
            draft.write_text("# Normal Subgroup\n\nDraft note.\n", encoding="utf-8", newline="\n")
            next_action = "notes:normal_subgroup | 04_atomic_notes/drafts/normal_subgroup.md"
            generated = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "brief",
                    "generate",
                    "--project",
                    str(ready_project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "projects",
                    "resume",
                    "--root",
                    str(root),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(generated.returncode, 0, generated.stderr)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("# Project Resume Index", result.stdout)
            self.assertIn("- Projects: 2", result.stdout)
            self.assertIn("- Ready: 1", result.stdout)
            self.assertIn("- Refresh brief: 1", result.stdout)
            self.assertIn(
                f"group_theory | Group Theory | ready | current | {next_action} | none",
                result.stdout,
            )
            self.assertIn(
                (
                    "ring_theory | Ring Theory | refresh_brief | not_run | none | "
                    f'python -m socrates brief generate --project "{fresh_project}"'
                ),
                result.stdout,
            )
            self.assertFalse(
                (fresh_project / "07_exports" / "briefs" / "study_brief.md").exists()
            )
            self.assertFalse(
                (fresh_project / "07_exports" / "briefs" / "study_brief_manifest.json").exists()
            )
            self.assertNotIn(
                "Generated study brief.",
                (fresh_project / "00_meta" / "project_log.md").read_text(encoding="utf-8"),
            )

    def test_projects_resume_json_reports_collection_state_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "SocratesProjects"
            ready_project = create_project(
                ProjectSpec(topic="Group Theory", path=root / "group_theory")
            )
            fresh_project = create_project(
                ProjectSpec(topic="Ring Theory", path=root / "ring_theory")
            )
            draft = ready_project / "04_atomic_notes" / "drafts" / "normal_subgroup.md"
            draft.write_text("# Normal Subgroup\n\nDraft note.\n", encoding="utf-8", newline="\n")
            next_action = "notes:normal_subgroup | 04_atomic_notes/drafts/normal_subgroup.md"
            generated = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "brief",
                    "generate",
                    "--project",
                    str(ready_project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "projects",
                    "resume",
                    "--root",
                    str(root),
                    "--json",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(generated.returncode, 0, generated.stderr)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["quality_boundary"], "deterministic_project_resume_index")
            self.assertEqual(payload["root"], str(root.resolve()))
            self.assertEqual(payload["project_count"], 2)
            self.assertEqual(payload["ready_count"], 1)
            self.assertEqual(payload["refresh_brief_count"], 1)
            self.assertEqual(
                [project["id"] for project in payload["projects"]],
                ["group_theory", "ring_theory"],
            )
            self.assertEqual(
                payload["projects"][0],
                {
                    "id": "group_theory",
                    "title": "Group Theory",
                    "path": "group_theory",
                    "resume_state": "ready",
                    "study_brief": "current",
                    "study_brief_path": "07_exports/briefs/study_brief.md",
                    "current_next_action": next_action,
                    "recommended_command": "none",
                },
            )
            self.assertEqual(
                payload["projects"][1],
                {
                    "id": "ring_theory",
                    "title": "Ring Theory",
                    "path": "ring_theory",
                    "resume_state": "refresh_brief",
                    "study_brief": "not_run",
                    "study_brief_path": "07_exports/briefs/study_brief.md",
                    "current_next_action": "none",
                    "recommended_command": (
                        f'python -m socrates brief generate --project "{fresh_project}"'
                    ),
                },
            )
            self.assertFalse((root / "socrates_projects.json").exists())
            self.assertFalse(
                (fresh_project / "07_exports" / "briefs" / "study_brief.md").exists()
            )
            self.assertFalse(
                (fresh_project / "07_exports" / "briefs" / "study_brief_manifest.json").exists()
            )
            self.assertNotIn(
                "Generated study brief.",
                (fresh_project / "00_meta" / "project_log.md").read_text(encoding="utf-8"),
            )

    def test_projects_resume_state_filter_shows_refresh_brief_projects_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "SocratesProjects"
            ready_project = create_project(
                ProjectSpec(topic="Group Theory", path=root / "group_theory")
            )
            fresh_project = create_project(
                ProjectSpec(topic="Ring Theory", path=root / "ring_theory")
            )
            draft = ready_project / "04_atomic_notes" / "drafts" / "normal_subgroup.md"
            draft.write_text("# Normal Subgroup\n\nDraft note.\n", encoding="utf-8", newline="\n")
            generated = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "brief",
                    "generate",
                    "--project",
                    str(ready_project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "projects",
                    "resume",
                    "--root",
                    str(root),
                    "--state",
                    "refresh_brief",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(generated.returncode, 0, generated.stderr)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("- State filter: refresh_brief", result.stdout)
            self.assertIn("- Projects: 1", result.stdout)
            self.assertIn("- Ready: 0", result.stdout)
            self.assertIn("- Refresh brief: 1", result.stdout)
            self.assertIn("ring_theory | Ring Theory | refresh_brief | not_run", result.stdout)
            self.assertNotIn("group_theory | Group Theory | ready | current", result.stdout)
            self.assertFalse((root / "socrates_projects.json").exists())
            self.assertFalse(
                (fresh_project / "07_exports" / "briefs" / "study_brief.md").exists()
            )
            self.assertFalse(
                (fresh_project / "07_exports" / "briefs" / "study_brief_manifest.json").exists()
            )
            self.assertNotIn(
                "Generated study brief.",
                (fresh_project / "00_meta" / "project_log.md").read_text(encoding="utf-8"),
            )

    def test_projects_resume_json_state_filter_shows_ready_projects_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "SocratesProjects"
            ready_project = create_project(
                ProjectSpec(topic="Group Theory", path=root / "group_theory")
            )
            fresh_project = create_project(
                ProjectSpec(topic="Ring Theory", path=root / "ring_theory")
            )
            draft = ready_project / "04_atomic_notes" / "drafts" / "normal_subgroup.md"
            draft.write_text("# Normal Subgroup\n\nDraft note.\n", encoding="utf-8", newline="\n")
            generated = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "brief",
                    "generate",
                    "--project",
                    str(ready_project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "projects",
                    "resume",
                    "--root",
                    str(root),
                    "--state",
                    "ready",
                    "--json",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(generated.returncode, 0, generated.stderr)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["state_filter"], "ready")
            self.assertEqual(payload["project_count"], 1)
            self.assertEqual(payload["ready_count"], 1)
            self.assertEqual(payload["refresh_brief_count"], 0)
            self.assertEqual([project["id"] for project in payload["projects"]], ["group_theory"])
            self.assertFalse((root / "socrates_projects.json").exists())
            self.assertFalse(
                (fresh_project / "07_exports" / "briefs" / "study_brief.md").exists()
            )
            self.assertFalse(
                (fresh_project / "07_exports" / "briefs" / "study_brief_manifest.json").exists()
            )
            self.assertNotIn(
                "Generated study brief.",
                (fresh_project / "00_meta" / "project_log.md").read_text(encoding="utf-8"),
            )

    def test_projects_resume_state_filter_summarizes_recommended_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "SocratesProjects"
            ready_project = create_project(
                ProjectSpec(topic="Group Theory", path=root / "group_theory")
            )
            fresh_project = create_project(
                ProjectSpec(topic="Ring Theory", path=root / "ring_theory")
            )
            draft = ready_project / "04_atomic_notes" / "drafts" / "normal_subgroup.md"
            draft.write_text("# Normal Subgroup\n\nDraft note.\n", encoding="utf-8", newline="\n")
            generated = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "brief",
                    "generate",
                    "--project",
                    str(ready_project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "projects",
                    "resume",
                    "--root",
                    str(root),
                    "--state",
                    "refresh_brief",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(generated.returncode, 0, generated.stderr)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("- Recommended commands: 1", result.stdout)
            self.assertIn("## Recommended Commands", result.stdout)
            self.assertIn(
                (
                    "ring_theory | Ring Theory | refresh_brief | "
                    f'python -m socrates brief generate --project "{fresh_project}"'
                ),
                result.stdout,
            )
            self.assertNotIn("group_theory | Group Theory | ready | none", result.stdout)
            self.assertFalse((root / "socrates_projects.json").exists())
            self.assertFalse(
                (fresh_project / "07_exports" / "briefs" / "study_brief.md").exists()
            )
            self.assertFalse(
                (fresh_project / "07_exports" / "briefs" / "study_brief_manifest.json").exists()
            )
            self.assertNotIn(
                "Generated study brief.",
                (fresh_project / "00_meta" / "project_log.md").read_text(encoding="utf-8"),
            )

    def test_projects_resume_json_summarizes_filtered_recommended_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "SocratesProjects"
            ready_project = create_project(
                ProjectSpec(topic="Group Theory", path=root / "group_theory")
            )
            fresh_project = create_project(
                ProjectSpec(topic="Ring Theory", path=root / "ring_theory")
            )
            draft = ready_project / "04_atomic_notes" / "drafts" / "normal_subgroup.md"
            draft.write_text("# Normal Subgroup\n\nDraft note.\n", encoding="utf-8", newline="\n")
            generated = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "brief",
                    "generate",
                    "--project",
                    str(ready_project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            ready_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "projects",
                    "resume",
                    "--root",
                    str(root),
                    "--state",
                    "ready",
                    "--json",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            refresh_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "projects",
                    "resume",
                    "--root",
                    str(root),
                    "--state",
                    "refresh_brief",
                    "--json",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(generated.returncode, 0, generated.stderr)
            self.assertEqual(ready_result.returncode, 0, ready_result.stderr)
            self.assertEqual(refresh_result.returncode, 0, refresh_result.stderr)
            ready_payload = json.loads(ready_result.stdout)
            self.assertEqual(ready_payload["recommended_command_count"], 0)
            self.assertEqual(ready_payload["recommended_commands"], [])
            refresh_payload = json.loads(refresh_result.stdout)
            self.assertEqual(refresh_payload["recommended_command_count"], 1)
            self.assertEqual(
                refresh_payload["recommended_commands"],
                [
                    {
                        "project_id": "ring_theory",
                        "project_title": "Ring Theory",
                        "resume_state": "refresh_brief",
                        "command": (
                            f'python -m socrates brief generate --project "{fresh_project}"'
                        ),
                    }
                ],
            )
            self.assertFalse((root / "socrates_projects.json").exists())
            self.assertFalse(
                (fresh_project / "07_exports" / "briefs" / "study_brief.md").exists()
            )
            self.assertFalse(
                (fresh_project / "07_exports" / "briefs" / "study_brief_manifest.json").exists()
            )
            self.assertNotIn(
                "Generated study brief.",
                (fresh_project / "00_meta" / "project_log.md").read_text(encoding="utf-8"),
            )

    def test_projects_resume_commands_prints_only_filtered_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "SocratesProjects"
            ready_project = create_project(
                ProjectSpec(topic="Group Theory", path=root / "group_theory")
            )
            fresh_project = create_project(
                ProjectSpec(topic="Ring Theory", path=root / "ring_theory")
            )
            draft = ready_project / "04_atomic_notes" / "drafts" / "normal_subgroup.md"
            draft.write_text("# Normal Subgroup\n\nDraft note.\n", encoding="utf-8", newline="\n")
            generated = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "brief",
                    "generate",
                    "--project",
                    str(ready_project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "projects",
                    "resume",
                    "--root",
                    str(root),
                    "--state",
                    "refresh_brief",
                    "--commands",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(generated.returncode, 0, generated.stderr)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                result.stdout,
                f'python -m socrates brief generate --project "{fresh_project}"\n',
            )
            self.assertNotIn("# Project Resume Index", result.stdout)
            self.assertNotIn("Recommended commands", result.stdout)
            self.assertNotIn("ring_theory |", result.stdout)
            self.assertNotIn("This project resume index", result.stdout)
            self.assertFalse((root / "socrates_projects.json").exists())
            self.assertFalse(
                (fresh_project / "07_exports" / "briefs" / "study_brief.md").exists()
            )
            self.assertFalse(
                (fresh_project / "07_exports" / "briefs" / "study_brief_manifest.json").exists()
            )
            self.assertNotIn(
                "Generated study brief.",
                (fresh_project / "00_meta" / "project_log.md").read_text(encoding="utf-8"),
            )

    def test_projects_resume_commands_prints_empty_output_when_no_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "SocratesProjects"
            ready_project = create_project(
                ProjectSpec(topic="Group Theory", path=root / "group_theory")
            )
            fresh_project = create_project(
                ProjectSpec(topic="Ring Theory", path=root / "ring_theory")
            )
            draft = ready_project / "04_atomic_notes" / "drafts" / "normal_subgroup.md"
            draft.write_text("# Normal Subgroup\n\nDraft note.\n", encoding="utf-8", newline="\n")
            generated = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "brief",
                    "generate",
                    "--project",
                    str(ready_project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "projects",
                    "resume",
                    "--root",
                    str(root),
                    "--state",
                    "ready",
                    "--commands",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(generated.returncode, 0, generated.stderr)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")
            self.assertFalse((root / "socrates_projects.json").exists())
            self.assertFalse(
                (fresh_project / "07_exports" / "briefs" / "study_brief.md").exists()
            )
            self.assertFalse(
                (fresh_project / "07_exports" / "briefs" / "study_brief_manifest.json").exists()
            )
            self.assertNotIn(
                "Generated study brief.",
                (fresh_project / "00_meta" / "project_log.md").read_text(encoding="utf-8"),
            )

    def test_projects_resume_json_and_commands_are_mutually_exclusive(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "SocratesProjects"
            create_project(ProjectSpec(topic="Group Theory", path=root / "group_theory"))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "projects",
                    "resume",
                    "--root",
                    str(root),
                    "--json",
                    "--commands",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not allowed with argument", result.stderr)
            self.assertFalse((root / "socrates_projects.json").exists())

    def test_projects_refresh_briefs_writes_only_refresh_needed_projects(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "SocratesProjects"
            ready_project = create_project(
                ProjectSpec(topic="Group Theory", path=root / "group_theory")
            )
            fresh_project = create_project(
                ProjectSpec(topic="Ring Theory", path=root / "ring_theory")
            )
            draft = ready_project / "04_atomic_notes" / "drafts" / "normal_subgroup.md"
            draft.write_text("# Normal Subgroup\n\nDraft note.\n", encoding="utf-8", newline="\n")
            generated = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "brief",
                    "generate",
                    "--project",
                    str(ready_project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "projects",
                    "refresh-briefs",
                    "--root",
                    str(root),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(generated.returncode, 0, generated.stderr)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("# Project Brief Refresh", result.stdout)
            self.assertIn("- Refreshed: 1", result.stdout)
            self.assertIn("- Skipped: 1", result.stdout)
            self.assertIn(
                "ring_theory | Ring Theory | 07_exports/briefs/study_brief.md",
                result.stdout,
            )
            self.assertIn(
                "group_theory | Group Theory | ready | resume_state_ready",
                result.stdout,
            )
            self.assertTrue(
                (fresh_project / "07_exports" / "briefs" / "study_brief.md").exists()
            )
            self.assertTrue(
                (fresh_project / "07_exports" / "briefs" / "study_brief_manifest.json").exists()
            )
            self.assertIn(
                "Generated study brief.",
                (fresh_project / "00_meta" / "project_log.md").read_text(encoding="utf-8"),
            )
            ready_log = (ready_project / "00_meta" / "project_log.md").read_text(
                encoding="utf-8"
            )
            self.assertEqual(ready_log.count("Generated study brief."), 1)
            self.assertFalse((root / "socrates_projects.json").exists())

    def test_projects_refresh_briefs_noops_when_all_projects_are_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "SocratesProjects"
            ready_project = create_project(
                ProjectSpec(topic="Group Theory", path=root / "group_theory")
            )
            draft = ready_project / "04_atomic_notes" / "drafts" / "normal_subgroup.md"
            draft.write_text("# Normal Subgroup\n\nDraft note.\n", encoding="utf-8", newline="\n")
            generated = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "brief",
                    "generate",
                    "--project",
                    str(ready_project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "projects",
                    "refresh-briefs",
                    "--root",
                    str(root),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(generated.returncode, 0, generated.stderr)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("- Refreshed: 0", result.stdout)
            self.assertIn("- Skipped: 1", result.stdout)
            self.assertIn("## Refreshed Projects\n\n- none", result.stdout)
            ready_log = (ready_project / "00_meta" / "project_log.md").read_text(
                encoding="utf-8"
            )
            self.assertEqual(ready_log.count("Generated study brief."), 1)
            self.assertFalse((root / "socrates_projects.json").exists())

    def test_projects_refresh_briefs_json_reports_written_and_skipped_projects(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "SocratesProjects"
            ready_project = create_project(
                ProjectSpec(topic="Group Theory", path=root / "group_theory")
            )
            fresh_project = create_project(
                ProjectSpec(topic="Ring Theory", path=root / "ring_theory")
            )
            draft = ready_project / "04_atomic_notes" / "drafts" / "normal_subgroup.md"
            draft.write_text("# Normal Subgroup\n\nDraft note.\n", encoding="utf-8", newline="\n")
            generated = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "brief",
                    "generate",
                    "--project",
                    str(ready_project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "projects",
                    "refresh-briefs",
                    "--root",
                    str(root),
                    "--json",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(generated.returncode, 0, generated.stderr)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(
                payload["quality_boundary"],
                "deterministic_project_brief_refresh",
            )
            self.assertEqual(payload["root"], str(root.resolve()))
            self.assertEqual(payload["mode"], "write")
            self.assertFalse(payload["dry_run"])
            self.assertEqual(payload["selected_count"], 1)
            self.assertEqual(payload["refreshed_count"], 1)
            self.assertEqual(payload["skipped_count"], 1)
            self.assertEqual(
                payload["refreshed"],
                [
                    {
                        "id": "ring_theory",
                        "title": "Ring Theory",
                        "path": "ring_theory",
                        "resume_state": "refresh_brief",
                        "brief_path": "07_exports/briefs/study_brief.md",
                    }
                ],
            )
            self.assertEqual(payload["selected"], payload["refreshed"])
            self.assertEqual(
                payload["skipped"],
                [
                    {
                        "id": "group_theory",
                        "title": "Group Theory",
                        "path": "group_theory",
                        "resume_state": "ready",
                        "reason": "resume_state_ready",
                    }
                ],
            )
            self.assertTrue(
                (fresh_project / "07_exports" / "briefs" / "study_brief.md").exists()
            )
            self.assertTrue(
                (fresh_project / "07_exports" / "briefs" / "study_brief_manifest.json").exists()
            )
            self.assertIn(
                "Generated study brief.",
                (fresh_project / "00_meta" / "project_log.md").read_text(encoding="utf-8"),
            )
            ready_log = (ready_project / "00_meta" / "project_log.md").read_text(
                encoding="utf-8"
            )
            self.assertEqual(ready_log.count("Generated study brief."), 1)
            self.assertFalse((root / "socrates_projects.json").exists())

    def test_projects_refresh_briefs_dry_run_reports_selected_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "SocratesProjects"
            ready_project = create_project(
                ProjectSpec(topic="Group Theory", path=root / "group_theory")
            )
            fresh_project = create_project(
                ProjectSpec(topic="Ring Theory", path=root / "ring_theory")
            )
            draft = ready_project / "04_atomic_notes" / "drafts" / "normal_subgroup.md"
            draft.write_text("# Normal Subgroup\n\nDraft note.\n", encoding="utf-8", newline="\n")
            generated = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "brief",
                    "generate",
                    "--project",
                    str(ready_project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "projects",
                    "refresh-briefs",
                    "--root",
                    str(root),
                    "--dry-run",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(generated.returncode, 0, generated.stderr)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("# Project Brief Refresh", result.stdout)
            self.assertIn("- Mode: dry_run", result.stdout)
            self.assertIn("- Selected: 1", result.stdout)
            self.assertIn("- Refreshed: 0", result.stdout)
            self.assertIn("- Skipped: 1", result.stdout)
            self.assertIn(
                (
                    "ring_theory | Ring Theory | refresh_brief | "
                    "07_exports/briefs/study_brief.md"
                ),
                result.stdout,
            )
            self.assertIn("## Refreshed Projects\n\n- none", result.stdout)
            self.assertIn(
                "group_theory | Group Theory | ready | resume_state_ready",
                result.stdout,
            )
            self.assertFalse(
                (fresh_project / "07_exports" / "briefs" / "study_brief.md").exists()
            )
            self.assertFalse(
                (fresh_project / "07_exports" / "briefs" / "study_brief_manifest.json").exists()
            )
            self.assertNotIn(
                "Generated study brief.",
                (fresh_project / "00_meta" / "project_log.md").read_text(encoding="utf-8"),
            )
            ready_log = (ready_project / "00_meta" / "project_log.md").read_text(
                encoding="utf-8"
            )
            self.assertEqual(ready_log.count("Generated study brief."), 1)
            self.assertFalse((root / "socrates_projects.json").exists())

    def test_projects_refresh_briefs_dry_run_json_reports_selected_without_writing(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "SocratesProjects"
            ready_project = create_project(
                ProjectSpec(topic="Group Theory", path=root / "group_theory")
            )
            fresh_project = create_project(
                ProjectSpec(topic="Ring Theory", path=root / "ring_theory")
            )
            draft = ready_project / "04_atomic_notes" / "drafts" / "normal_subgroup.md"
            draft.write_text("# Normal Subgroup\n\nDraft note.\n", encoding="utf-8", newline="\n")
            generated = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "brief",
                    "generate",
                    "--project",
                    str(ready_project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "projects",
                    "refresh-briefs",
                    "--root",
                    str(root),
                    "--dry-run",
                    "--json",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(generated.returncode, 0, generated.stderr)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(
                payload["quality_boundary"],
                "deterministic_project_brief_refresh",
            )
            self.assertEqual(payload["root"], str(root.resolve()))
            self.assertEqual(payload["mode"], "dry_run")
            self.assertTrue(payload["dry_run"])
            self.assertEqual(payload["selected_count"], 1)
            self.assertEqual(payload["refreshed_count"], 0)
            self.assertEqual(payload["skipped_count"], 1)
            self.assertEqual(
                payload["selected"],
                [
                    {
                        "id": "ring_theory",
                        "title": "Ring Theory",
                        "path": "ring_theory",
                        "resume_state": "refresh_brief",
                        "brief_path": "07_exports/briefs/study_brief.md",
                    }
                ],
            )
            self.assertEqual(payload["refreshed"], [])
            self.assertEqual(
                payload["skipped"],
                [
                    {
                        "id": "group_theory",
                        "title": "Group Theory",
                        "path": "group_theory",
                        "resume_state": "ready",
                        "reason": "resume_state_ready",
                    }
                ],
            )
            self.assertFalse(
                (fresh_project / "07_exports" / "briefs" / "study_brief.md").exists()
            )
            self.assertFalse(
                (fresh_project / "07_exports" / "briefs" / "study_brief_manifest.json").exists()
            )
            self.assertNotIn(
                "Generated study brief.",
                (fresh_project / "00_meta" / "project_log.md").read_text(encoding="utf-8"),
            )
            ready_log = (ready_project / "00_meta" / "project_log.md").read_text(
                encoding="utf-8"
            )
            self.assertEqual(ready_log.count("Generated study brief."), 1)
            self.assertFalse((root / "socrates_projects.json").exists())

    def test_projects_refresh_briefs_limit_json_writes_first_and_defers_rest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "SocratesProjects"
            ready_project = create_project(
                ProjectSpec(topic="Group Theory", path=root / "group_theory")
            )
            first_fresh_project = create_project(
                ProjectSpec(topic="Module Theory", path=root / "module_theory")
            )
            second_fresh_project = create_project(
                ProjectSpec(topic="Ring Theory", path=root / "ring_theory")
            )
            draft = ready_project / "04_atomic_notes" / "drafts" / "normal_subgroup.md"
            draft.write_text("# Normal Subgroup\n\nDraft note.\n", encoding="utf-8", newline="\n")
            generated = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "brief",
                    "generate",
                    "--project",
                    str(ready_project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "projects",
                    "refresh-briefs",
                    "--root",
                    str(root),
                    "--limit",
                    "1",
                    "--json",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(generated.returncode, 0, generated.stderr)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["mode"], "write")
            self.assertFalse(payload["dry_run"])
            self.assertEqual(payload["limit"], 1)
            self.assertEqual(payload["selected_count"], 1)
            self.assertEqual(payload["refreshed_count"], 1)
            self.assertEqual(payload["deferred_count"], 1)
            self.assertEqual(payload["skipped_count"], 1)
            self.assertEqual(
                payload["selected"],
                [
                    {
                        "id": "module_theory",
                        "title": "Module Theory",
                        "path": "module_theory",
                        "resume_state": "refresh_brief",
                        "brief_path": "07_exports/briefs/study_brief.md",
                    }
                ],
            )
            self.assertEqual(payload["refreshed"], payload["selected"])
            self.assertEqual(
                payload["deferred"],
                [
                    {
                        "id": "ring_theory",
                        "title": "Ring Theory",
                        "path": "ring_theory",
                        "resume_state": "refresh_brief",
                        "brief_path": "07_exports/briefs/study_brief.md",
                        "reason": "limit_reached",
                    }
                ],
            )
            self.assertEqual(
                payload["skipped"],
                [
                    {
                        "id": "group_theory",
                        "title": "Group Theory",
                        "path": "group_theory",
                        "resume_state": "ready",
                        "reason": "resume_state_ready",
                    }
                ],
            )
            self.assertTrue(
                (first_fresh_project / "07_exports" / "briefs" / "study_brief.md").exists()
            )
            self.assertTrue(
                (
                    first_fresh_project
                    / "07_exports"
                    / "briefs"
                    / "study_brief_manifest.json"
                ).exists()
            )
            self.assertIn(
                "Generated study brief.",
                (
                    first_fresh_project / "00_meta" / "project_log.md"
                ).read_text(encoding="utf-8"),
            )
            self.assertFalse(
                (second_fresh_project / "07_exports" / "briefs" / "study_brief.md").exists()
            )
            self.assertFalse(
                (
                    second_fresh_project
                    / "07_exports"
                    / "briefs"
                    / "study_brief_manifest.json"
                ).exists()
            )
            self.assertNotIn(
                "Generated study brief.",
                (
                    second_fresh_project / "00_meta" / "project_log.md"
                ).read_text(encoding="utf-8"),
            )
            ready_log = (ready_project / "00_meta" / "project_log.md").read_text(
                encoding="utf-8"
            )
            self.assertEqual(ready_log.count("Generated study brief."), 1)
            self.assertFalse((root / "socrates_projects.json").exists())

    def test_projects_refresh_briefs_dry_run_limit_reports_deferred_without_writing(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "SocratesProjects"
            ready_project = create_project(
                ProjectSpec(topic="Group Theory", path=root / "group_theory")
            )
            first_fresh_project = create_project(
                ProjectSpec(topic="Module Theory", path=root / "module_theory")
            )
            second_fresh_project = create_project(
                ProjectSpec(topic="Ring Theory", path=root / "ring_theory")
            )
            draft = ready_project / "04_atomic_notes" / "drafts" / "normal_subgroup.md"
            draft.write_text("# Normal Subgroup\n\nDraft note.\n", encoding="utf-8", newline="\n")
            generated = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "brief",
                    "generate",
                    "--project",
                    str(ready_project),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "projects",
                    "refresh-briefs",
                    "--root",
                    str(root),
                    "--dry-run",
                    "--limit",
                    "1",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(generated.returncode, 0, generated.stderr)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("- Mode: dry_run", result.stdout)
            self.assertIn("- Limit: 1", result.stdout)
            self.assertIn("- Selected: 1", result.stdout)
            self.assertIn("- Refreshed: 0", result.stdout)
            self.assertIn("- Deferred: 1", result.stdout)
            self.assertIn("- Skipped: 1", result.stdout)
            self.assertIn(
                (
                    "module_theory | Module Theory | refresh_brief | "
                    "07_exports/briefs/study_brief.md"
                ),
                result.stdout,
            )
            self.assertIn(
                (
                    "ring_theory | Ring Theory | refresh_brief | "
                    "07_exports/briefs/study_brief.md | limit_reached"
                ),
                result.stdout,
            )
            for project in (first_fresh_project, second_fresh_project):
                self.assertFalse(
                    (project / "07_exports" / "briefs" / "study_brief.md").exists()
                )
                self.assertFalse(
                    (
                        project
                        / "07_exports"
                        / "briefs"
                        / "study_brief_manifest.json"
                    ).exists()
                )
                self.assertNotIn(
                    "Generated study brief.",
                    (project / "00_meta" / "project_log.md").read_text(encoding="utf-8"),
                )
            ready_log = (ready_project / "00_meta" / "project_log.md").read_text(
                encoding="utf-8"
            )
            self.assertEqual(ready_log.count("Generated study brief."), 1)
            self.assertFalse((root / "socrates_projects.json").exists())

    def test_projects_refresh_briefs_limit_rejects_non_positive_value(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "SocratesProjects"
            create_project(ProjectSpec(topic="Group Theory", path=root / "group_theory"))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "projects",
                    "refresh-briefs",
                    "--root",
                    str(root),
                    "--limit",
                    "0",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("limit must be positive", result.stderr)
            self.assertFalse((root / "socrates_projects.json").exists())

    def test_projects_refs_finds_reviewed_notes_across_projects(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "SocratesProjects"
            group_project = create_project(
                ProjectSpec(topic="Group Theory", path=root / "group_theory")
            )
            representation_project = create_project(
                ProjectSpec(topic="Representation Theory", path=root / "representation_theory")
            )
            generate_atomic_note_draft(
                group_project,
                concept="Normal Subgroup",
                note_type="definition",
                body=(
                    "A normal subgroup is stable under conjugation; compare [[Subgroup]].\n\n"
                    "## Review Questions\n\n"
                    "- What condition distinguishes normality from centrality?\n"
                ),
                source_id="df",
            )
            generate_atomic_note_draft(
                representation_project,
                concept="Group Representation",
                note_type="definition",
                body=(
                    "A group representation is an action by linear maps; compare [[Group Action]].\n\n"
                    "## Review Questions\n\n"
                    "- What structure must each group element preserve?\n"
                ),
                source_id="serre",
            )
            review_atomic_note(group_project, "normal_subgroup")
            review_atomic_note(representation_project, "group_representation")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "projects",
                    "refs",
                    "--root",
                    str(root),
                    "--query",
                    "normal",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(
                (
                    "group_theory.normal_subgroup | Normal Subgroup | "
                    "definition | group_theory/04_atomic_notes/definitions/normal_subgroup.md"
                ),
                result.stdout,
            )
            self.assertNotIn("representation_theory.group_representation", result.stdout)

    def test_projects_graph_writes_cross_project_reference_edges(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "SocratesProjects"
            group_project = create_project(
                ProjectSpec(topic="Group Theory", path=root / "group_theory")
            )
            representation_project = create_project(
                ProjectSpec(topic="Representation Theory", path=root / "representation_theory")
            )
            generate_atomic_note_draft(
                group_project,
                concept="Normal Subgroup",
                note_type="definition",
                body=(
                    "Normal subgroups often appear before [[Group Representation]].\n\n"
                    "## Review Questions\n\n"
                    "- What conjugation condition must be checked?\n"
                ),
                source_id="df",
            )
            generate_atomic_note_draft(
                representation_project,
                concept="Group Representation",
                note_type="definition",
                body=(
                    "A group representation is a homomorphism into linear automorphisms; compare [[Group Action]].\n\n"
                    "## Review Questions\n\n"
                    "- Which vector space is carrying the action?\n"
                ),
                source_id="serre",
            )
            review_atomic_note(group_project, "normal_subgroup")
            review_atomic_note(representation_project, "group_representation")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "projects",
                    "graph",
                    "--root",
                    str(root),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Wrote cross-project graph with 1 edge", result.stdout)
            graph_path = root / "cross_project_references.json"
            graph = json.loads(graph_path.read_text(encoding="utf-8"))
            self.assertEqual(graph["version"], 1)
            self.assertEqual(
                graph["edges"],
                [
                    {
                        "source": "group_theory.normal_subgroup",
                        "target": "representation_theory.group_representation",
                        "label": "Group Representation",
                    }
                ],
            )


if __name__ == "__main__":
    unittest.main()
