from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

from socrates.contracts import AtomicNoteDraft, ExerciseDraft
from socrates.project import ProjectSpec, create_project


class NotesExercisesTests(unittest.TestCase):
    def test_generate_atomic_note_draft_writes_obsidian_frontmatter(self) -> None:
        artifacts = self._load_artifacts_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))

            note = artifacts.generate_atomic_note_draft(
                project,
                concept="Group Action",
                note_type="definition",
                body="A group action is a map G x X -> X satisfying identity and compatibility.",
                source_id="df-1",
                source_title="Dummit and Foote",
                source_location="Section 1.7",
            )

            self.assertIsInstance(note, AtomicNoteDraft)
            self.assertEqual(note.id, "group_action")
            self.assertEqual(note.type, "definition")
            self.assertEqual(note.concept, "Group Action")
            self.assertEqual(note.path, "04_atomic_notes/drafts/group_action.md")

            note_path = project / note.path
            self.assertTrue(note_path.exists())
            text = note_path.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\n"))
            self.assertIn('status: "draft"', text)
            self.assertIn('review_status: "needs_review"', text)
            self.assertIn('source_id: "df-1"', text)
            self.assertIn('source_title: "Dummit and Foote"', text)
            self.assertIn('source_location: "Section 1.7"', text)
            self.assertIn("# Group Action", text)
            self.assertIn("A group action is a map", text)

    def test_generate_exercise_drafts_writes_required_sections(self) -> None:
        artifacts = self._load_artifacts_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))

            exercises = artifacts.generate_exercise_drafts(
                project,
                concept="Group Action",
                source_id="df-1",
                prerequisites=["group", "set"],
                count=5,
            )

            self.assertGreaterEqual(len(exercises), 5)
            self.assertTrue(all(isinstance(exercise, ExerciseDraft) for exercise in exercises))
            required_sections = [
                "## Statement",
                "## Concepts",
                "## Prerequisites",
                "## Hints",
                "## Solution Outline",
                "## Rubric",
                "## Common Mistakes",
            ]
            for index, exercise in enumerate(exercises, start=1):
                self.assertEqual(exercise.id, f"group_action_{index:02d}")
                self.assertEqual(exercise.type, "generated")
                self.assertGreaterEqual(exercise.difficulty, 1)
                self.assertLessEqual(exercise.difficulty, 5)
                self.assertEqual(
                    exercise.path,
                    f"05_exercises/generated/group_action_{index:02d}.md",
                )

                exercise_path = project / exercise.path
                self.assertTrue(exercise_path.exists())
                text = exercise_path.read_text(encoding="utf-8")
                self.assertIn('status: "draft"', text)
                self.assertIn('review_status: "needs_review"', text)
                self.assertIn('source_id: "df-1"', text)
                for section in required_sections:
                    self.assertIn(section, text)
                self.assertIn("- Group Action", text)
                self.assertIn("- group", text)
                self.assertIn("- set", text)

    def _load_artifacts_module(self):
        spec = importlib.util.find_spec("socrates.artifacts")
        self.assertIsNotNone(spec, "socrates.artifacts module should exist")
        return importlib.import_module("socrates.artifacts")


if __name__ == "__main__":
    unittest.main()
