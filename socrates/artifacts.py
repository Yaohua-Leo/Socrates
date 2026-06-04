"""Draft note and exercise artifact generation for Socrates projects."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
import json
from pathlib import Path
import re

from socrates.context import load_project, write_text
from socrates.contracts import AtomicNoteDraft, ExerciseDraft, yaml_scalar
from socrates.project import slugify_topic
from socrates.state import MisconceptionSummary, list_misconceptions


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
    reference_object = _kb_reference_object(context.root, concept)
    related_concepts = _unique_concepts(
        [
            *_kb_related_concepts(reference_object),
            *_body_related_concepts(body, concept=concept),
        ]
    )
    related_links = [f"[[{_concept_title(item)}]]" for item in related_concepts]
    note_body = _with_required_note_sections(body.rstrip(), concept)
    reference_context = _reference_context_section(reference_object)
    if reference_context:
        note_body += "\n\n" + reference_context.rstrip()
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
                "topic": _project_id(context.root),
                "concept": concept,
                "created_by": "socrates",
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


def generate_misconception_note_drafts(
    project_path: Path | str,
    *,
    status: str = "active",
) -> list[AtomicNoteDraft]:
    """Write misconception-note drafts from the persisted learning state."""

    context = load_project(project_path)
    drafts: list[AtomicNoteDraft] = []
    for misconception in list_misconceptions(context, status=status):
        drafts.append(
            generate_atomic_note_draft(
                context.root,
                concept=misconception.misconception_id,
                note_type="misconception",
                body=_misconception_note_body(misconception),
                source_id="learning_state",
                source_title="Socrates learning state",
                source_location=f"misconception:{misconception.misconception_id}",
            )
        )
    return drafts


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
    reference_object = _kb_reference_object(context.root, concept)
    prerequisite_list = (
        list(prerequisites)
        or _kb_related_concepts(reference_object)
        or _exercise_prerequisite_fallback(concept)
    )
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
                reference_object=reference_object,
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


def generate_targeted_review_exercise_drafts(
    project_path: Path | str,
    *,
    due_by: date | None = None,
) -> list[ExerciseDraft]:
    """Write exercises targeted at the current review schedule."""

    context = load_project(project_path)
    state = json.loads(context.learning_state.read_text(encoding="utf-8"))
    schedule = state.get("review_schedule", []) if isinstance(state, dict) else []
    if not isinstance(schedule, list):
        return []

    drafts: list[ExerciseDraft] = []
    concept_counts: dict[str, int] = {}
    for item in schedule:
        if not isinstance(item, dict):
            continue
        if due_by is not None and not _is_due_review_item(item, due_by):
            continue
        concept = str(item.get("concept", "review"))
        reference_object = _kb_reference_object(context.root, concept)
        concept_id = slugify_topic(concept)
        concept_counts[concept_id] = concept_counts.get(concept_id, 0) + 1
        exercise_id = f"review_{concept_id}_{concept_counts[concept_id]:02d}"
        relative_path = Path("05_exercises") / "generated" / f"{exercise_id}.md"
        exercise_path = context.root / relative_path
        if not exercise_path.exists():
            difficulty = _review_exercise_difficulty(str(item.get("priority", "medium")))
            write_text(
                exercise_path,
                _targeted_review_exercise_text(
                    concept=concept,
                    reason=str(item.get("reason", "review scheduled")),
                    priority=str(item.get("priority", "medium")),
                    difficulty=difficulty,
                    due=str(item.get("due", "within_3_days")),
                    scheduled_for=str(item.get("scheduled_for", "")),
                    repair_context=item.get("repair_context", []),
                    reference_object=reference_object,
                ),
            )
        else:
            difficulty = _review_exercise_difficulty(str(item.get("priority", "medium")))
        drafts.append(
            ExerciseDraft(
                id=exercise_id,
                type="targeted_review",
                difficulty=difficulty,
                path=_as_posix(relative_path),
            )
        )
    return drafts


def _is_due_review_item(item: dict[str, object], due_by: date) -> bool:
    scheduled_for = str(item.get("scheduled_for", "")).strip()
    if not scheduled_for:
        return False
    try:
        scheduled_date = date.fromisoformat(scheduled_for)
    except ValueError:
        return False
    return scheduled_date <= due_by


def _exercise_text(
    *,
    concept: str,
    source_id: str,
    prerequisites: list[str],
    reference_object: dict[str, object] | None,
    index: int,
    difficulty: int,
) -> str:
    prerequisites_block = _bullet_list(prerequisites)
    reference_context = _reference_context_section(reference_object)
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
        + "## Target Training Point\n\n"
        + f"Practice applying {concept} by checking each defining condition explicitly.\n\n"
        + "## Concepts\n\n"
        + _bullet_list([concept])
        + "\n## Prerequisites\n\n"
        + prerequisites_block
        + ("\n" + reference_context if reference_context else "")
        + "\n## Hints\n\n"
        + "- Hint 1 (definition): Identify the definitions that apply directly.\n"
        + "- Hint 2 (structure): Check each required condition separately.\n"
        + "- Hint 3 (local step): Write one verification before trying to finish the whole proof.\n\n"
        + "## Solution Outline\n\n"
        + "- Step 1: State the relevant definition.\n"
        + "- Step 2: Verify the required properties in order.\n"
        + "- Step 3: Conclude by connecting the computation back to the concept.\n\n"
        + "## Rubric\n\n"
        + "- Total: 10 pts\n"
        + "- Definition setup: 3 pts\n"
        + "- Correct verification: 4 pts\n"
        + "- Complete conclusion: 3 pts\n\n"
        + "## Common Mistakes\n\n"
        + "- Skipping one condition in the definition.\n"
        + "- Confusing examples with a proof of the general statement.\n"
    )


def _targeted_review_exercise_text(
    *,
    concept: str,
    reason: str,
    priority: str,
    difficulty: int,
    due: str,
    scheduled_for: str,
    repair_context: object,
    reference_object: dict[str, object] | None,
) -> str:
    reference_context = _reference_context_section(reference_object)
    repair_context_section = _repair_context_section(repair_context)
    prerequisites = _review_exercise_prerequisites(reference_object, concept)
    return (
        _frontmatter(
            {
                "status": "draft",
                "review_status": "needs_review",
                "type": "targeted_review_exercise",
                "concept": concept,
                "difficulty": difficulty,
                "priority": priority,
                "due": due,
                "scheduled_for": scheduled_for,
            }
        )
        + f"# Review Exercise: {concept}\n\n"
        + "## Target Weakness\n\n"
        + f"{reason}\n\n"
        + (repair_context_section + "\n" if repair_context_section else "")
        + (reference_context + "\n" if reference_context else "")
        + "## Target Training Point\n\n"
        + _targeted_review_training_point(concept, bool(repair_context_section))
        + "\n\n"
        + "## Concepts\n\n"
        + _bullet_list([concept])
        + "\n## Prerequisites\n\n"
        + _bullet_list(prerequisites)
        + "\n"
        + "## Review Prompt\n\n"
        + f"State the relevant definition of {concept}, then give one example and one non-example.\n\n"
        + "## Hints\n\n"
        + "- Hint 1 (definition): Start from the exact definition rather than a remembered slogan.\n"
        + "- Hint 2 (example): Test the definition against a borderline example.\n"
        + "- Hint 3 (local step): Explain exactly which condition succeeds or fails.\n\n"
        + "## Solution Outline\n\n"
        + "- Step 1: Write the formal condition.\n"
        + "- Step 2: Explain why the example satisfies every condition.\n"
        + "- Step 3: Explain exactly which condition fails in the non-example.\n\n"
        + "## Rubric\n\n"
        + "- Total: 10 pts\n"
        + "- Accurate definition: 3 pts\n"
        + "- Justified example and non-example: 4 pts\n"
        + "- Addresses scheduled weakness: 3 pts\n"
        + "\n## Common Mistakes\n\n"
        + "- Repeating the weak slogan without checking the definition.\n"
        + "- Giving an example without explaining the failing condition in the non-example.\n"
    )


def _repair_context_section(value: object) -> str:
    if not isinstance(value, list):
        return ""
    lines = ["## Repair Context", ""]
    has_context = False
    for raw_context in value:
        if not isinstance(raw_context, dict):
            continue
        misconception_id = str(raw_context.get("misconception_id", "")).strip()
        if not misconception_id:
            continue
        count = _safe_positive_int(raw_context.get("count", 1))
        lines.append(f"- Misconception: {misconception_id} (x{count})")
        for key, label in (
            ("last_session_id", "Last session"),
            ("analysis", "Analysis"),
            ("repair_suggestion", "Repair suggestion"),
        ):
            text = str(raw_context.get(key, "")).strip()
            if text:
                lines.append(f"  - {label}: {text}")
        follow_up_exercises = raw_context.get("follow_up_exercises", [])
        if isinstance(follow_up_exercises, list) and follow_up_exercises:
            lines.append(
                "  - Follow-up exercises: "
                + ", ".join(str(item) for item in follow_up_exercises)
            )
        has_context = True
    return "\n".join(lines) + "\n" if has_context else ""


def _targeted_review_training_point(concept: str, has_repair_context: bool) -> str:
    if has_repair_context:
        return (
            f"Repair {concept} by addressing the recorded misconception before adding new examples."
        )
    return (
        f"Repair the scheduled weakness in {concept} by contrasting the definition with a borderline case."
    )


def _misconception_note_body(misconception: MisconceptionSummary) -> str:
    concept_title = _concept_title(misconception.concept)
    lines = [
        f"This note records a misconception about [[{concept_title}]].",
        "",
        "## Misconception Pattern",
        "",
        f"- Misconception id: `{misconception.misconception_id}`",
        f"- Status: {misconception.status}",
        f"- Occurrences: {misconception.count}",
    ]
    if misconception.last_session_id:
        lines.append(f"- Last session: {misconception.last_session_id}")
    lines.extend(
        [
            "",
            "## Diagnosis",
            "",
            _or_placeholder(
                misconception.analysis,
                "Add the user-specific analysis before approving this note.",
            ),
            "",
            "## Repair Plan",
            "",
            "- "
            + _or_placeholder(
                misconception.repair_suggestion,
                f"Re-state the exact definition of [[{concept_title}]] and compare it with the mistaken pattern.",
            ),
        ]
    )
    if misconception.follow_up_exercises:
        lines.extend(["", "## Follow-Up Exercises", ""])
        lines.extend(f"- {item}" for item in misconception.follow_up_exercises)
    lines.extend(
        [
            "",
            "## Key Examples",
            "",
            f"- A correct use of [[{concept_title}]] where every defining condition is checked.",
            "",
            "## Non-Examples",
            "",
            f"- A case where `{misconception.misconception_id}` sounds plausible but fails the definition.",
            "",
            "## Common Mistakes",
            "",
            f"- Replacing [[{concept_title}]] with the shortcut `{misconception.misconception_id}`.",
            "",
            "## Review Questions",
            "",
            f"- How does the definition of [[{concept_title}]] block this misconception?",
        ]
    )
    return "\n".join(lines)


def _or_placeholder(value: str, placeholder: str) -> str:
    text = value.strip()
    return text if text else placeholder


def _safe_positive_int(value: object) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError):
        return 1
    return count if count > 0 else 1


def _review_exercise_difficulty(priority: str) -> int:
    return 3 if priority == "high" else 2


def _review_exercise_prerequisites(
    reference_object: dict[str, object] | None,
    concept: str,
) -> list[str]:
    dependencies = _kb_related_concepts(reference_object)
    if dependencies:
        return dependencies
    return [f"current weakness record for {concept}"]


def _exercise_prerequisite_fallback(concept: str) -> list[str]:
    return [f"Current definition of {concept}"]


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


def _project_id(project_root: Path) -> str:
    project_file = project_root / "project.yaml"
    in_project_section = False
    for line in project_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped == "project:":
            in_project_section = True
            continue
        if not line.startswith(" ") and stripped.endswith(":"):
            in_project_section = False
        if in_project_section and stripped.startswith("id:"):
            value = stripped.removeprefix("id:").strip().strip('"')
            if value:
                return value
    return slugify_topic(project_root.name)


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


def _kb_reference_object(project_root: Path, concept: str) -> dict[str, object] | None:
    index_path = project_root / "06_kb" / "chunks" / "reference_index.json"
    if not index_path.exists():
        return None
    index = json.loads(index_path.read_text(encoding="utf-8"))
    concept_id = slugify_topic(concept)
    for item in index.get("objects", []):
        if not isinstance(item, dict):
            continue
        if item.get("id") == concept_id or str(item.get("title", "")).casefold() == concept.casefold():
            return item
    return None


def _kb_related_concepts(reference_object: dict[str, object] | None) -> list[str]:
    if reference_object is None:
        return []
    return [str(value) for value in reference_object.get("dependencies", [])]


def _body_related_concepts(body: str, *, concept: str) -> list[str]:
    values: list[str] = []
    own_id = slugify_topic(concept)
    for match in re.finditer(r"\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]", body):
        value = match.group(1).strip()
        if value and slugify_topic(value) != own_id:
            values.append(value)
    return values


def _unique_concepts(values: Iterable[str]) -> list[str]:
    concepts: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        key = slugify_topic(text)
        if not text or key in seen:
            continue
        seen.add(key)
        concepts.append(text)
    return concepts


def _reference_context_section(reference_object: dict[str, object] | None) -> str:
    if reference_object is None:
        return ""

    source = reference_object.get("source", {})
    if not isinstance(source, dict):
        source = {}

    object_type = str(reference_object.get("type", "object"))
    title = str(reference_object.get("title", "Untitled"))
    lines = [
        "## Reference Context",
        "",
        f"- Object: {_reference_object_label(reference_object, object_type, title)}",
        f"- Source: {source.get('path', 'unknown')}",
    ]
    if source.get("line"):
        lines.append(f"- Line: {source['line']}")
    if source.get("page"):
        lines.append(f"- Page: {source['page']}")
    if source.get("chapter"):
        lines.append(f"- Chapter: {source['chapter']}")
    if source.get("section"):
        lines.append(f"- Section: {source['section']}")

    statement = str(reference_object.get("statement", "")).strip()
    if statement:
        lines.extend(["", statement])
    return "\n".join(lines) + "\n"


def _reference_object_label(
    reference_object: dict[str, object],
    object_type: str,
    title: str,
) -> str:
    number = str(reference_object.get("number", "")).strip()
    if number:
        return f"{object_type} {number} {title}"
    return f"{object_type} {title}"


def _with_required_note_sections(body: str, concept: str) -> str:
    note_body = body.rstrip()
    additions: list[str] = []
    if "## Key Examples" not in note_body:
        additions.append(
            "## Key Examples\n\n"
            f"- Add a user-checked example illustrating {concept}."
        )
    if "## Non-Examples" not in note_body and "## Counterexamples" not in note_body:
        additions.append(
            "## Non-Examples\n\n"
            f"- Add a contrasting case where the defining condition of {concept} fails."
        )
    if "## Common Mistakes" not in note_body:
        additions.append(
            "## Common Mistakes\n\n"
            "- Record one misconception or skipped condition to watch for during review."
        )
    if "## Review Questions" not in note_body:
        additions.append(
            "## Review Questions\n\n"
            f"- What must be checked before applying {concept}?"
        )
    if not additions:
        return note_body
    separator = "\n\n" if note_body else ""
    return note_body + separator + "\n\n".join(additions)


def _note_tags(note_type: str, concept: str, related_concepts: list[str]) -> list[str]:
    tags = [note_type, slugify_topic(concept).replace("_", "-")]
    tags.extend(slugify_topic(item).replace("_", "-") for item in related_concepts)
    return tags


def _concept_title(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").title()


def _as_posix(path: Path) -> str:
    return path.as_posix()
