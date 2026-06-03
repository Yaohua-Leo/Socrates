"""Draft note and exercise artifact generation for Socrates projects."""

from __future__ import annotations

from collections.abc import Iterable
import json
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
    related_concepts = _kb_related_concepts(context.root, concept)
    related_links = [f"[[{_concept_title(item)}]]" for item in related_concepts]
    note_body = body.rstrip()
    if related_links:
        note_body += "\n\n## Related Concepts\n\n" + _bullet_list(related_links).rstrip()

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
                "tags": _note_tags(note_type, concept, related_concepts),
                "related": related_links,
            }
        )
        + f"# {concept}\n\n{note_body}\n",
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
        if isinstance(value, list):
            lines.append(f"{key}:")
            if value:
                lines.extend(f"  - {_yaml_list_item(item)}" for item in value)
            else:
                lines.append("  []")
            continue
        lines.append(f"{key}: {yaml_scalar(value)}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def _yaml_list_item(value: object) -> str:
    text = str(value)
    if any(character in text for character in "[]:{}#"):
        return yaml_scalar(text)
    return text


def _bullet_list(items: Iterable[str]) -> str:
    values = list(items)
    if not values:
        return "- None recorded.\n"
    return "".join(f"- {item}\n" for item in values)


def _kb_related_concepts(project_root: Path, concept: str) -> list[str]:
    index_path = project_root / "06_kb" / "chunks" / "reference_index.json"
    if not index_path.exists():
        return []
    index = json.loads(index_path.read_text(encoding="utf-8"))
    concept_id = slugify_topic(concept)
    for item in index.get("objects", []):
        if not isinstance(item, dict):
            continue
        if item.get("id") == concept_id or str(item.get("title", "")).casefold() == concept.casefold():
            return [str(value) for value in item.get("dependencies", [])]
    return []


def _note_tags(note_type: str, concept: str, related_concepts: list[str]) -> list[str]:
    tags = [note_type, slugify_topic(concept).replace("_", "-")]
    tags.extend(slugify_topic(item).replace("_", "-") for item in related_concepts)
    return tags


def _concept_title(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").title()


def _as_posix(path: Path) -> str:
    return path.as_posix()
