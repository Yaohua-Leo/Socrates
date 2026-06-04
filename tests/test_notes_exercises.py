from __future__ import annotations

import importlib
import importlib.util
from datetime import date
from pathlib import Path
import tempfile
import unittest

from socrates.contracts import AtomicNoteDraft, ExerciseDraft
from socrates.kb import build_reference_kb
from socrates.context import load_project
from socrates.exercises import approve_exercise_draft
from socrates.project import ProjectSpec, create_project
from socrates.state import (
    LearningStatePatch,
    MistakeRecord,
    build_review_schedule,
    update_learning_state,
)


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
            self.assertIn('topic: "group_theory"', text)
            self.assertIn('created_by: "socrates"', text)
            self.assertIn('source_id: "df-1"', text)
            self.assertIn('source_title: "Dummit and Foote"', text)
            self.assertIn('source_location: "Section 1.7"', text)
            self.assertIn("# Group Action", text)
            self.assertIn("A group action is a map", text)
            self.assertIn("## Key Examples", text)
            self.assertIn("## Non-Examples", text)
            self.assertIn("## Common Mistakes", text)

    def test_atomic_note_draft_uses_kb_dependencies_for_related_links_and_tags(self) -> None:
        artifacts = self._load_artifacts_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "normal_subgroups.curated.md"
            curated.write_text(
                "### Definition 3.1: Normal Subgroup\n"
                "A normal subgroup is stable under conjugation.\n"
                "Depends: subgroup, conjugation\n",
                encoding="utf-8",
                newline="\n",
            )
            build_reference_kb(project)

            note = artifacts.generate_atomic_note_draft(
                project,
                concept="Normal Subgroup",
                note_type="definition",
                body="A normal subgroup is stable under conjugation.",
                source_id="df-1",
            )

            text = (project / note.path).read_text(encoding="utf-8")
            self.assertIn("tags:\n  - definition\n  - normal-subgroup", text)
            self.assertIn("related:\n  - \"[[Subgroup]]\"\n  - \"[[Conjugation]]\"", text)
            self.assertIn("## Related Concepts\n\n- [[Subgroup]]\n- [[Conjugation]]", text)

    def test_atomic_note_draft_uses_body_wikilinks_for_related_links(self) -> None:
        artifacts = self._load_artifacts_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))

            note = artifacts.generate_atomic_note_draft(
                project,
                concept="Normal Subgroup",
                note_type="definition",
                body="A normal subgroup refines [[Subgroup]] and supports [[Quotient Group]].",
                source_id="df-1",
            )

            text = (project / note.path).read_text(encoding="utf-8")
            self.assertIn("related:\n  - \"[[Subgroup]]\"\n  - \"[[Quotient Group]]\"", text)
            self.assertIn("## Related Concepts\n\n- [[Subgroup]]\n- [[Quotient Group]]", text)

    def test_atomic_note_draft_includes_kb_reference_context(self) -> None:
        artifacts = self._load_artifacts_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "normal_subgroups.curated.md"
            curated.write_text(
                "# Chapter 3: Quotient Groups\n"
                "## Section 3.1 Normal Subgroups\n"
                "### Definition 3.1: Normal Subgroup\n"
                "Page: 82\n"
                "A subgroup N of G is normal if gNg^{-1}=N for every g in G.\n"
                "Depends: subgroup, conjugation\n",
                encoding="utf-8",
                newline="\n",
            )
            build_reference_kb(project)

            note = artifacts.generate_atomic_note_draft(
                project,
                concept="Normal Subgroup",
                note_type="definition",
                body=(
                    "Normality is conjugation invariance.\n\n"
                    "## Review Questions\n\n"
                    "- How does this differ from commutativity?\n"
                ),
                source_id="df-1",
            )

            text = (project / note.path).read_text(encoding="utf-8")
            self.assertIn("## Reference Context", text)
            self.assertIn("- Object: definition 3.1 Normal Subgroup", text)
            self.assertIn("- Source: 01_references/curated/normal_subgroups.curated.md", text)
            self.assertIn("- Line: 3", text)
            self.assertIn("- Page: 82", text)
            self.assertIn(
                "A subgroup N of G is normal if gNg^{-1}=N for every g in G.",
                text,
            )

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
                "## Target Training Point",
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
                self.assertIn("Hint 1", text)
                self.assertIn("Hint 2", text)
                self.assertIn("Hint 3", text)
                self.assertIn("Step 1:", text)
                self.assertIn("Step 2:", text)
                self.assertIn("Step 3:", text)
                self.assertIn("Total: 10 pts", text)
                self.assertIn("3 pts", text)
                self.assertIn("4 pts", text)

    def test_generate_exercise_drafts_fills_prerequisite_fallback(self) -> None:
        artifacts = self._load_artifacts_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))

            exercises = artifacts.generate_exercise_drafts(
                project,
                concept="Group Action",
                source_id="df-1",
                count=5,
            )

            text = (project / exercises[0].path).read_text(encoding="utf-8")
            self.assertIn("## Prerequisites\n\n- Current definition of Group Action", text)
            self.assertNotIn("- None recorded.", text)

    def test_generate_exercise_drafts_uses_kb_reference_context(self) -> None:
        artifacts = self._load_artifacts_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "normality.curated.md"
            curated.write_text(
                "# Chapter 3: Quotient Groups\n"
                "## Section 3.1 Normal Subgroups\n"
                "### Definition 3.1: Normal Subgroup\n"
                "Page: 82\n"
                "A subgroup N of G is normal if gNg^{-1}=N for every g in G.\n"
                "Depends: subgroup, conjugation\n",
                encoding="utf-8",
                newline="\n",
            )
            build_reference_kb(project)

            exercises = artifacts.generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="normality_notes",
                count=5,
            )

            text = (project / exercises[0].path).read_text(encoding="utf-8")
            self.assertIn("## Reference Context", text)
            self.assertIn("- Object: definition 3.1 Normal Subgroup", text)
            self.assertIn("- Source: 01_references/curated/normality.curated.md", text)
            self.assertIn("- Line: 3", text)
            self.assertIn("- Page: 82", text)
            self.assertIn(
                "A subgroup N of G is normal if gNg^{-1}=N for every g in G.",
                text,
            )
            self.assertIn("- subgroup", text)
            self.assertIn("- conjugation", text)

    def test_generate_targeted_review_exercises_uses_review_schedule(self) -> None:
        artifacts = self._load_artifacts_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(concept_mastery={"normal_subgroup": 0.43}),
            )
            build_review_schedule(context, as_of=date(2026, 6, 4))

            exercises = artifacts.generate_targeted_review_exercise_drafts(project)

            self.assertEqual(len(exercises), 1)
            self.assertEqual(exercises[0].id, "review_normal_subgroup_01")
            self.assertEqual(
                exercises[0].path,
                "05_exercises/generated/review_normal_subgroup_01.md",
            )
            text = (project / exercises[0].path).read_text(encoding="utf-8")
            self.assertIn('type: "targeted_review_exercise"', text)
            self.assertIn('concept: "normal_subgroup"', text)
            self.assertIn("difficulty: 3", text)
            self.assertIn('priority: "high"', text)
            self.assertIn('due: "next_session"', text)
            self.assertIn('scheduled_for: "2026-06-04"', text)
            self.assertIn("## Target Weakness\n\nmastery 0.43", text)
            self.assertIn("## Target Training Point", text)
            self.assertIn("## Concepts\n\n- normal_subgroup", text)
            self.assertIn("## Prerequisites", text)
            self.assertIn("## Review Prompt", text)
            self.assertIn("Hint 1", text)
            self.assertIn("Hint 2", text)
            self.assertIn("Hint 3", text)
            self.assertIn("Step 1:", text)
            self.assertIn("Step 2:", text)
            self.assertIn("Step 3:", text)
            self.assertIn("Total: 10 pts", text)
            self.assertIn("## Common Mistakes", text)

    def test_targeted_review_exercises_include_kb_reference_context(self) -> None:
        artifacts = self._load_artifacts_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            curated = project / "01_references" / "curated" / "normality.curated.md"
            curated.write_text(
                "# Chapter 3: Quotient Groups\n"
                "## Section 3.1 Normal Subgroups\n"
                "### Definition 3.1: Normal Subgroup\n"
                "Page: 82\n"
                "A subgroup N of G is normal if gNg^{-1}=N for every g in G.\n"
                "Depends: subgroup, conjugation\n",
                encoding="utf-8",
                newline="\n",
            )
            build_reference_kb(project)
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(concept_mastery={"normal_subgroup": 0.43}),
            )
            build_review_schedule(context)

            exercises = artifacts.generate_targeted_review_exercise_drafts(project)

            text = (project / exercises[0].path).read_text(encoding="utf-8")
            self.assertIn("## Reference Context", text)
            self.assertIn("- Object: definition 3.1 Normal Subgroup", text)
            self.assertIn("- Source: 01_references/curated/normality.curated.md", text)
            self.assertIn("- Page: 82", text)
            self.assertIn(
                "A subgroup N of G is normal if gNg^{-1}=N for every g in G.",
                text,
            )

    def test_targeted_review_exercises_include_misconception_repair_context(self) -> None:
        artifacts = self._load_artifacts_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(
                    mistakes=[
                        MistakeRecord(
                            session_id="session-001",
                            concept="normal_subgroup",
                            misconception_id="normal_equals_central",
                            user_answer="Normal means central.",
                            analysis="Confuses normality with centrality.",
                            repair_suggestion="Compare gNg^-1=N with gn=ng.",
                            follow_up_exercises=["normal_subgroup_review_01"],
                        )
                    ],
                ),
            )
            build_review_schedule(context, as_of=date(2026, 6, 4))

            exercises = artifacts.generate_targeted_review_exercise_drafts(project)

            text = (project / exercises[0].path).read_text(encoding="utf-8")
            self.assertIn("## Repair Context", text)
            self.assertIn("- Misconception: normal_equals_central (x1)", text)
            self.assertIn("  - Last session: session-001", text)
            self.assertIn("  - Analysis: Confuses normality with centrality.", text)
            self.assertIn("  - Repair suggestion: Compare gNg^-1=N with gn=ng.", text)
            self.assertIn("  - Follow-up exercises: normal_subgroup_review_01", text)
            self.assertIn(
                "Repair normal_subgroup by addressing the recorded misconception before adding new examples.",
                text,
            )

    def test_generate_targeted_review_exercises_preserves_reviewed_existing_files(self) -> None:
        artifacts = self._load_artifacts_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(concept_mastery={"normal_subgroup": 0.43}),
            )
            build_review_schedule(context)
            artifacts.generate_targeted_review_exercise_drafts(project)
            approve_exercise_draft(project, "review_normal_subgroup_01")

            exercises = artifacts.generate_targeted_review_exercise_drafts(project)

            self.assertEqual(len(exercises), 1)
            text = (project / "05_exercises" / "generated" / "review_normal_subgroup_01.md").read_text(
                encoding="utf-8"
            )
            self.assertIn('status: "approved"', text)
            self.assertIn('review_status: "approved"', text)
            self.assertIn("reviewed_by_user: true", text)

    def test_generate_targeted_review_exercise_ids_are_stable_per_concept(self) -> None:
        artifacts = self._load_artifacts_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(
                    concept_mastery={
                        "normal_subgroup": 0.43,
                        "quotient_group": 0.44,
                    },
                ),
            )
            build_review_schedule(context)

            exercises = artifacts.generate_targeted_review_exercise_drafts(project)

            self.assertEqual(
                [exercise.id for exercise in exercises],
                ["review_normal_subgroup_01", "review_quotient_group_01"],
            )
            self.assertTrue(
                (project / "05_exercises" / "generated" / "review_quotient_group_01.md").exists()
            )
            self.assertFalse(
                (project / "05_exercises" / "generated" / "review_quotient_group_02.md").exists()
            )

    def test_targeted_review_exercises_can_filter_by_due_date(self) -> None:
        artifacts = self._load_artifacts_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p"))
            context = load_project(project)
            update_learning_state(
                context,
                LearningStatePatch(
                    concept_mastery={
                        "normal_subgroup": 0.4,
                        "quotient_group": 0.62,
                    },
                ),
            )
            build_review_schedule(context, as_of=date(2026, 6, 4))

            exercises = artifacts.generate_targeted_review_exercise_drafts(
                project,
                due_by=date(2026, 6, 4),
            )

            self.assertEqual([exercise.id for exercise in exercises], ["review_normal_subgroup_01"])
            self.assertTrue(
                (project / "05_exercises" / "generated" / "review_normal_subgroup_01.md").exists()
            )
            self.assertFalse(
                (project / "05_exercises" / "generated" / "review_quotient_group_01.md").exists()
            )

    def _load_artifacts_module(self):
        spec = importlib.util.find_spec("socrates.artifacts")
        self.assertIsNotNone(spec, "socrates.artifacts module should exist")
        return importlib.import_module("socrates.artifacts")


if __name__ == "__main__":
    unittest.main()
