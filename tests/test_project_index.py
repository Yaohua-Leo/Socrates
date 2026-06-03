from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
