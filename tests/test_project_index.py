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
                    "A normal subgroup is stable under conjugation.\n\n"
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
                    "A group representation is an action by linear maps.\n\n"
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
                    "A group representation is a homomorphism into linear automorphisms.\n\n"
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
