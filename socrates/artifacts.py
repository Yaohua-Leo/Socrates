"""Draft note and exercise artifact generation for Socrates projects."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from socrates.context import load_project, write_text
from socrates.contracts import AtomicNoteDraft, ExerciseDraft, yaml_scalar
from socrates.project import slugify_topic


def generate_atomic_note_draft(
    project_path: Path | str,
    *,
    concept: str,
    note_type: str,
    body: str,
    source_id: str,
    source_title: str | None = None,
    source_location: str | None = None,
) -> AtomicNoteDraft:
    """Write one Obsidian-compatible draft atomic note."""

    context = load_project(project_path)
    note_id = slugify_topic(concept)
    relative_path = Path("04_atomic_notes") / "drafts" / f"{note_id}.md"
    note_path = context.root / relative_path

    write_text(
        note_path,
        _frontmatter(
            {
                "status": "draft",
                "review_status": "needs_review",
                "reviewed_by_user": False,
                "type": note_type,
                "concept": concept,
                "source_id": source_id,
                "source_title": source_title,
                "source_location": source_location,
            }
        )
        + f"# {concept}\n\n{body.rstrip()}\n",
    )

    return AtomicNoteDraft(
        id=note_id,
        type=note_type,
        concept=concept,
        path=_as_posix(relative_path),
    )


def generate_exercise_drafts(
    project_path: Path | str,
    *,
    concept: str,
    source_id: str,
    prerequisites: Iterable[str] = (),
    count: int = 5,
) -> list[ExerciseDraft]:
    """Write at least five review-ready generated exercise drafts."""

    context = load_project(project_path)
    base_id = slugify_topic(concept)
    prerequisite_list = list(prerequisites)
    exercise_count = max(5, count)
    drafts: list[ExerciseDraft] = []

    for index in range(1, exercise_count + 1):
        exercise_id = f"{base_id}_{index:02d}"
        difficulty = min(5, index)
        relative_path = Path("05_exercises") / "generated" / f"{exercise_id}.md"
        write_text(
            context.root / relative_path,
            _exercise_text(
                concept=concept,
                source_id=source_id,
                prerequisites=prerequisite_list,
                index=index,
                difficulty=difficulty,
            ),
        )
        drafts.append(
            ExerciseDraft(
                id=exercise_id,
                type="generated",
                difficulty=difficulty,
                path=_as_posix(relative_path),
            )
        )

    return drafts


def _exercise_text(
    *,
    concept: str,
    source_id: str,
    prerequisites: list[str],
    index: int,
    difficulty: int,
) -> str:
    prerequisites_block = _bullet_list(prerequisites)
    return (
        _frontmatter(
            {
                "status": "draft",
                "review_status": "needs_review",
                "type": "generated_exercise",
                "concept": concept,
                "source_id": source_id,
                "difficulty": difficulty,
            }
        )
        + f"# {concept} Exercise {index:02d}\n\n"
        + "## Statement\n\n"
        + f"Work out a focused problem about {concept}.\n\n"
        + "## Concepts\n\n"
        + _bullet_list([concept])
        + "\n## Prerequisites\n\n"
        + prerequisites_block
        + "\n## Hints\n\n"
        + "- Identify the definitions that apply directly.\n"
        + "- Check each required condition separately.\n\n"
        + "## Solution Outline\n\n"
        + "- State the relevant definition.\n"
        + "- Verify the required properties in order.\n"
        + "- Conclude by connecting the computation back to the concept.\n\n"
        + "## Rubric\n\n"
        + "- Correctly identifies the target concept.\n"
        + "- Uses prerequisites without circular reasoning.\n"
        + "- Provides a complete justification for each step.\n\n"
        + "## Common Mistakes\n\n"
        + "- Skipping one condition in the definition.\n"
        + "- Confusing examples with a proof of the general statement.\n"
    )


def _frontmatter(values: dict[str, object]) -> str:
    lines = ["---"]
    for key, value in values.items():
        lines.append(f"{key}: {yaml_scalar(value)}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def _bullet_list(items: Iterable[str]) -> str:
    values = list(items)
    if not values:
        return "- None recorded.\n"
    return "".join(f"- {item}\n" for item in values)


def _as_posix(path: Path) -> str:
    return path.as_posix()
