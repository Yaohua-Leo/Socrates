from pathlib import Path
import tempfile
import unittest

from socrates.artifacts import generate_exercise_drafts
from socrates.exercise_schema import parse_exercise_markdown, validate_exercise_spec
from socrates.project import ProjectSpec, create_project


class ExerciseSchemaTests(unittest.TestCase):
    def test_generated_exercise_parses_to_structured_spec(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = create_project(
                ProjectSpec(topic="Group Theory", path=Path(temp_dir) / "p")
            )
            draft = generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="df-1",
                prerequisites=["subgroup", "conjugation"],
                count=5,
            )[0]
            exercise_path = project / draft.path

            spec = parse_exercise_markdown(exercise_path)

            self.assertEqual(spec.exercise_id, "normal_subgroup_01")
            self.assertEqual(spec.schema_version, "v0.4")
            self.assertEqual(spec.status, "draft")
            self.assertEqual(spec.review_status, "needs_review")
            self.assertEqual(spec.exercise_type, "generated_exercise")
            self.assertEqual(spec.concept, "Normal Subgroup")
            self.assertEqual(spec.difficulty, 1)
            self.assertEqual(spec.rubric.total_points, 10)
            self.assertEqual(sum(item.points for item in spec.rubric.items), 10)
            self.assertGreaterEqual(len(spec.hints), 3)
            self.assertGreaterEqual(len(spec.solution_steps), 3)
            self.assertEqual(validate_exercise_spec(spec), [])

    def test_validator_reports_non_progressive_hints_and_bad_rubric_sum(self) -> None:
        text = (
            "---\n"
            "status: draft\n"
            "review_status: needs_review\n"
            "type: generated_exercise\n"
            "concept: Normal Subgroup\n"
            "source_id: df-1\n"
            "difficulty: 2\n"
            "---\n\n"
            "# Bad Exercise\n\n"
            "## Statement\n\nProve something about normal subgroups.\n\n"
            "## Target Training Point\n\nUse the definition explicitly.\n\n"
            "## Concepts\n\n- Normal Subgroup\n\n"
            "## Prerequisites\n\n- subgroup\n\n"
            "## Hints\n\n"
            "- Hint 2 (structure): Start in the middle.\n"
            "- Hint 2 (structure): Repeat the same level.\n\n"
            "## Solution Outline\n\n"
            "- Step 1: State the definition.\n"
            "- Step 2: Apply it.\n"
            "- Step 3: Conclude.\n\n"
            "## Rubric\n\n"
            "- Total: 10 pts\n"
            "- Definition setup: 3 pts\n"
            "- Correct verification: 3 pts\n"
            "- Complete conclusion: 3 pts\n\n"
            "## Common Mistakes\n\n- Skipping one condition.\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bad.md"
            path.write_text(text, encoding="utf-8", newline="\n")

            spec = parse_exercise_markdown(path)
            issues = validate_exercise_spec(spec)

            self.assertIn("non-progressive hint ladder", issues)
            self.assertIn("rubric point values do not sum to total", issues)


if __name__ == "__main__":
    unittest.main()
