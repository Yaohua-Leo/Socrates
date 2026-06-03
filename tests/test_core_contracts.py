from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from socrates.context import ProjectContext, append_project_log, load_project
from socrates.contracts import SourceRecord
from socrates.project import ProjectSpec, create_project


class CoreContractsTests(unittest.TestCase):
    def test_load_project_exposes_canonical_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(
                ProjectSpec(
                    topic="Group Theory",
                    path=Path(temp_dir) / "group_theory",
                    goal="Prepare for representation theory.",
                )
            )

            context = load_project(project)

            self.assertIsInstance(context, ProjectContext)
            self.assertEqual(context.root, project)
            self.assertEqual(context.project_file, project / "project.yaml")
            self.assertEqual(
                context.source_registry,
                project / "01_references" / "source_registry.yaml",
            )
            self.assertEqual(
                context.learning_state,
                project / "00_meta" / "learning_state.json",
            )
            self.assertEqual(context.sessions_dir, project / "03_sessions")

    def test_load_project_rejects_missing_project_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(FileNotFoundError):
                load_project(Path(temp_dir))

    def test_source_record_round_trips_to_registry_yaml(self) -> None:
        record = SourceRecord(
            id="dummit_foote",
            type="pdf",
            title="Abstract Algebra",
            role="main_textbook",
            priority=1,
            status="raw_imported",
            local_path="01_references/raw/books/dummit_foote.pdf",
            processed_paths={"markdown": None, "curated": None},
            notes="User supplied main reference.",
        )

        yaml_text = record.to_registry_yaml()

        self.assertIn("- id: dummit_foote", yaml_text)
        self.assertIn('title: "Abstract Algebra"', yaml_text)
        self.assertIn("markdown: null", yaml_text)
        self.assertIn('notes: "User supplied main reference."', yaml_text)

    def test_append_project_log_uses_stable_bullet_format(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)

            append_project_log(context, "Imported source dummit_foote.")

            log_text = (project / "00_meta" / "project_log.md").read_text(encoding="utf-8")
            self.assertIn("- Imported source dummit_foote.", log_text)


if __name__ == "__main__":
    unittest.main()
