"""Learning-plan generation for initialized Socrates projects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path

from socrates.context import append_project_log, load_project, write_json, write_text
from socrates.contracts import SessionPlan, yaml_scalar
from socrates.kb import reference_kb_status, read_reference_chapter_index
from socrates.learning_queue import LearningQueue, collect_learning_queue
from socrates.state import ensure_learning_state_readable


@dataclass(frozen=True)
class NextSessionPlanResult:
    """Filesystem result for one deterministic next-session handoff plan."""

    session_id: str
    plan_path: Path
    manifest_path: Path
    due_reviews: int
    previous_session_id: str | None


def create_learning_plan(project_path: Path | str) -> list[Path]:
    """Create the initial long-term, short-term, and first-session plans."""

    context = load_project(project_path)
    project = _read_project_metadata(context.project_file)
    source_titles = _read_source_titles(context.source_registry)
    reference_context = _read_reference_context(context.root, project["topic"])
    chapter_outline = _read_chapter_outline(context.root)
    kb_status = reference_kb_status(context.root)
    session = SessionPlan(
        session_id="session_0001",
        objective=f"Orient to {project['topic']} and convert the goal into a study map.",
        prerequisites=["Project has been initialized.", "Reference registry has been reviewed."],
        diagnostic_question=f"What do you already know that is closest to {project['topic']}?",
        target_concepts=[project["topic"]],
    )

    plans = {
        context.learning_plan_dir / "long_term_plan.md": _long_term_plan(
            project["topic"],
            project["goal"],
            source_titles,
            chapter_outline,
        ),
        context.learning_plan_dir / "short_term_plan.md": _short_term_plan(
            project["topic"], project["goal"], source_titles
        ),
        context.learning_plan_dir / "session_0001_plan.md": _session_plan(
            project["topic"],
            project["goal"],
            source_titles,
            reference_context,
            kb_status.status,
            session,
        ),
    }
    for path, content in plans.items():
        write_text(path, content)
    write_text(
        context.learning_plan_dir / "chapter_sequence.yaml",
        _chapter_sequence_yaml(chapter_outline),
    )
    write_text(
        context.learning_plan_dir / "checkpoints.yaml",
        _checkpoints_yaml(chapter_outline),
    )
    return list(plans)


def create_next_session_plan(
    project_path: Path | str,
    *,
    session_id: str,
    as_of: date | None = None,
) -> NextSessionPlanResult:
    """Create a deterministic handoff plan for the next tutoring session."""

    context = load_project(project_path)
    as_of_date = as_of or date.today()
    project = _read_project_metadata(context.project_file)
    ensure_learning_state_readable(
        context.learning_state,
        action="creating next-session plans",
    )
    state = _read_learning_state_for_next_plan(context.learning_state)
    due_reviews, future_reviews, invalid_reviews = _review_schedule_rows(
        state,
        as_of=as_of_date,
    )
    previous_session_id = _latest_previous_session_id(
        context.sessions_dir,
        exclude=session_id,
    )
    previous_session = _previous_session_handoff(
        context.sessions_dir,
        previous_session_id,
    )
    query_concept = due_reviews[0]["concept"] if due_reviews else project["topic"]
    kb_status = reference_kb_status(context.root)
    reference_context = _read_reference_context(context.root, query_concept)
    queue = collect_learning_queue(context.root)

    plan_path = context.learning_plan_dir / f"{session_id}_plan.md"
    manifest_path = context.learning_plan_dir / "next_session_plan_manifest.json"
    write_text(
        plan_path,
        _next_session_plan_text(
            session_id=session_id,
            topic=project["topic"],
            goal=project["goal"],
            as_of=as_of_date.isoformat(),
            previous_session_id=previous_session_id,
            previous_session=previous_session,
            due_reviews=due_reviews,
            future_reviews=future_reviews,
            invalid_reviews=invalid_reviews,
            queue=queue,
            reference_context=reference_context,
            kb_status=kb_status.status,
        ),
    )
    write_json(
        manifest_path,
        _next_session_manifest(
            context.root,
            session_id=session_id,
            as_of=as_of_date.isoformat(),
            plan_path=plan_path,
            previous_session_id=previous_session_id,
            due_reviews=due_reviews,
            future_reviews=future_reviews,
            invalid_reviews=invalid_reviews,
            queue=queue,
            reference_kb_status=kb_status.status,
        ),
    )
    append_project_log(context, f"Created next-session handoff plan {session_id}.")
    return NextSessionPlanResult(
        session_id=session_id,
        plan_path=plan_path,
        manifest_path=manifest_path,
        due_reviews=len(due_reviews),
        previous_session_id=previous_session_id,
    )


def adjust_short_term_plan_from_review_schedule(project_path: Path | str) -> Path:
    """Update the short-term plan with review tasks from learning state."""

    context = load_project(project_path)
    short_term_path = context.learning_plan_dir / "short_term_plan.md"
    if short_term_path.exists():
        current = short_term_path.read_text(encoding="utf-8")
    else:
        current = "# Short Term Plan\n"

    ensure_learning_state_readable(
        context.learning_state,
        action="adjusting review plans",
    )
    state = json.loads(context.learning_state.read_text(encoding="utf-8"))
    schedule = state.get("review_schedule", []) if isinstance(state, dict) else []
    if not isinstance(schedule, list):
        schedule = []

    write_text(short_term_path, _replace_review_adjustments(current, schedule))
    return short_term_path


def _read_project_metadata(project_file: Path) -> dict[str, str]:
    topic = ""
    goal = ""
    in_project = False
    in_user_goal = False
    for line in project_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not line.startswith(" ") and stripped.endswith(":"):
            in_project = stripped == "project:"
            in_user_goal = stripped == "user_goal:"
            continue
        if in_project and stripped.startswith("title:"):
            topic = _yaml_value(stripped.removeprefix("title:").strip())
        if in_user_goal and stripped.startswith("description:"):
            goal = _yaml_value(stripped.removeprefix("description:").strip())
    return {"topic": topic or "Untitled Project", "goal": goal or "No goal recorded yet."}


def _read_learning_state_for_next_plan(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def _review_schedule_rows(
    state: dict[str, object],
    *,
    as_of: date,
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    schedule = state.get("review_schedule", [])
    if not isinstance(schedule, list):
        return ([], [], [])

    due: list[dict[str, str]] = []
    future: list[dict[str, str]] = []
    invalid: list[dict[str, str]] = []
    for item in schedule:
        if not isinstance(item, dict):
            continue
        row = _review_schedule_row(item)
        try:
            scheduled_date = date.fromisoformat(row["scheduled_for"])
        except ValueError:
            invalid.append(row)
            continue
        if scheduled_date <= as_of:
            due.append(row)
        else:
            future.append(row)
    return (
        sorted(due, key=lambda row: (row["scheduled_for"], row["concept"])),
        sorted(future, key=lambda row: (row["scheduled_for"], row["concept"])),
        sorted(invalid, key=lambda row: (row["concept"], row["scheduled_for"])),
    )


def _review_schedule_row(item: dict[object, object]) -> dict[str, str]:
    return {
        "concept": str(item.get("concept", "review")),
        "scheduled_for": str(item.get("scheduled_for", "")).strip(),
        "priority": str(item.get("priority", "medium")),
        "due": str(item.get("due", "within_3_days")),
        "reason": str(item.get("reason", "review scheduled")),
        "repair": "; ".join(_review_repair_suggestions(item.get("repair_context", []))),
    }


def _latest_previous_session_id(sessions_dir: Path, *, exclude: str) -> str | None:
    if not sessions_dir.exists():
        return None
    session_ids = [
        path.name
        for path in sessions_dir.iterdir()
        if path.is_dir() and path.name != exclude
    ]
    return sorted(session_ids)[-1] if session_ids else None


def _previous_session_handoff(
    sessions_dir: Path,
    previous_session_id: str | None,
) -> dict[str, str]:
    if previous_session_id is None:
        return {}
    session_dir = sessions_dir / previous_session_id
    return {
        "summary": _read_optional_session_doc(session_dir / "summary.md"),
        "next_actions": _read_optional_session_doc(session_dir / "next_actions.md"),
        "misconceptions": _read_optional_session_doc(
            session_dir / "detected_misconceptions.md"
        ),
    }


def _read_optional_session_doc(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def _read_source_titles(source_registry: Path) -> list[str]:
    if not source_registry.exists():
        return []
    titles: list[str] = []
    for line in source_registry.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("title:"):
            title = _yaml_value(stripped.removeprefix("title:").strip())
            if title:
                titles.append(title)
    return titles


def _read_reference_context(project_root: Path, topic: str, *, limit: int = 5) -> list[dict[str, object]]:
    index_path = project_root / "06_kb" / "chunks" / "reference_index.json"
    if not index_path.exists():
        return []

    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(index, dict):
        return []
    objects = [item for item in index.get("objects", []) if isinstance(item, dict)]
    query = topic.casefold()
    matches: list[dict[str, object]] = []
    for item in objects:
        haystack = " ".join(
            [
                str(item.get("title", "")),
                str(item.get("statement", "")),
                " ".join(str(dep) for dep in item.get("dependencies", [])),
            ]
        ).casefold()
        if query in haystack:
            matches.append(item)
        if len(matches) >= limit:
            break
    return matches or objects[:limit]


def _read_chapter_outline(project_root: Path) -> list[dict[str, object]]:
    try:
        index = read_reference_chapter_index(project_root)
    except ValueError:
        return []
    chapters = index.get("chapters", [])
    if not isinstance(chapters, list):
        return []
    return [chapter for chapter in chapters if isinstance(chapter, dict)]


def _yaml_value(value: str) -> str:
    if value == "null":
        return ""
    if value.startswith('"') and value.endswith('"'):
        return str(json.loads(value))
    return value


def _source_section(source_titles: list[str]) -> str:
    if not source_titles:
        return "- Imported sources: none recorded yet.\n"
    lines = ["- Imported sources:"]
    lines.extend(f"  - {title}" for title in source_titles)
    return "\n".join(lines) + "\n"


def _reference_context_section(
    reference_context: list[dict[str, object]],
    *,
    kb_status: str,
) -> str:
    lines = [f"- Reference KB status: {kb_status}"]
    if not reference_context:
        lines.append("- Reference KB context: none indexed yet.")
        return "\n".join(lines) + "\n"
    lines.append("- Reference KB context:")
    for item in reference_context:
        source = item.get("source", {})
        source_path = "unknown"
        if isinstance(source, dict):
            source_path = str(source.get("path", "unknown"))
        dependencies = [str(dep) for dep in item.get("dependencies", [])]
        lines.append(f"  - {_reference_object_label(item)}")
        lines.append(f"    Source: {source_path}")
        if isinstance(source, dict) and source.get("page"):
            lines.append(f"    Page: {source['page']}")
        if dependencies:
            lines.append(f"    Depends: {', '.join(dependencies)}")
    return "\n".join(lines) + "\n"


def _reference_object_label(item: dict[str, object]) -> str:
    object_type = str(item.get("type", "object")).title()
    number = str(item.get("number", "")).strip()
    title = str(item.get("title", "Untitled"))
    if number:
        return f"{object_type} {number}: {title}"
    return f"{object_type}: {title}"


def _reference_reading_path_section(chapter_outline: list[dict[str, object]]) -> str:
    lines = ["## Reference Reading Path", ""]
    if not chapter_outline:
        lines.append("- none indexed yet.")
        return "\n".join(lines) + "\n"
    for chapter in chapter_outline:
        chapter_title = str(chapter.get("title") or "Unassigned")
        lines.append(f"- {chapter_title}")
        sections = chapter.get("sections", [])
        if not isinstance(sections, list) or not sections:
            continue
        for section in sections:
            if not isinstance(section, dict):
                continue
            lines.append(f"  - {section.get('title') or 'Unassigned'}")
            objects = section.get("objects", [])
            if not isinstance(objects, list):
                continue
            for item in objects:
                if isinstance(item, dict):
                    lines.append(f"    - {_reference_object_label(item)}")
    return "\n".join(lines) + "\n"


def _chapter_sequence_yaml(chapter_outline: list[dict[str, object]]) -> str:
    if not chapter_outline:
        return "chapters: []\n"
    lines = ["chapters:"]
    for chapter in chapter_outline:
        lines.append(f"  - title: {yaml_scalar(chapter.get('title') or 'Unassigned')}")
        sections = chapter.get("sections", [])
        if not isinstance(sections, list) or not sections:
            lines.append("    sections: []")
            continue
        lines.append("    sections:")
        for section in sections:
            if not isinstance(section, dict):
                continue
            lines.append(f"      - title: {yaml_scalar(section.get('title') or 'Unassigned')}")
            lines.append(
                f"        source_path: {yaml_scalar(section.get('source_path') or 'unknown')}"
            )
            objects = section.get("objects", [])
            if not isinstance(objects, list) or not objects:
                lines.append("        objects: []")
                continue
            lines.append("        objects:")
            for item in objects:
                if isinstance(item, dict):
                    lines.extend(_chapter_sequence_object_yaml(item))
    return "\n".join(lines) + "\n"


def _chapter_sequence_object_yaml(item: dict[str, object]) -> list[str]:
    lines = [
        f"          - id: {item.get('id') or 'unknown'}",
        f"            type: {item.get('type') or 'object'}",
        f"            title: {yaml_scalar(item.get('title') or 'Untitled')}",
    ]
    number = str(item.get("number") or "").strip()
    if number:
        lines.append(f"            number: {yaml_scalar(number)}")
    return lines


def _checkpoints_yaml(chapter_outline: list[dict[str, object]]) -> str:
    if not chapter_outline:
        return "checkpoints: []\n"
    lines = ["checkpoints:"]
    checkpoint_number = 1
    for chapter in chapter_outline:
        object_count = _chapter_object_count(chapter)
        title = str(chapter.get("title") or "Unassigned")
        lines.extend(
            [
                f"  - id: checkpoint_{checkpoint_number:03d}",
                f"    scope: {yaml_scalar(title)}",
                f"    objective: {yaml_scalar(f'Review indexed objects from {title}.')}",
                f"    object_count: {object_count}",
                "    status: pending",
            ]
        )
        checkpoint_number += 1
    return "\n".join(lines) + "\n"


def _next_session_plan_text(
    *,
    session_id: str,
    topic: str,
    goal: str,
    as_of: str,
    previous_session_id: str | None,
    previous_session: dict[str, str],
    due_reviews: list[dict[str, str]],
    future_reviews: list[dict[str, str]],
    invalid_reviews: list[dict[str, str]],
    queue: LearningQueue,
    reference_context: list[dict[str, object]],
    kb_status: str,
) -> str:
    return "\n".join(
        [
            f"# Session {session_id} Plan",
            "",
            "## Objective",
            "",
            (
                f"Prepare the next {topic} tutoring session from persisted review, "
                "queue, and reference context before introducing new material."
            ),
            "",
            "## Topic",
            "",
            topic,
            "",
            "## Goal",
            "",
            goal,
            "",
            "## Previous Session Handoff",
            "",
            *_previous_session_lines(previous_session_id, previous_session),
            "",
            "## Due Reviews",
            "",
            *_review_rows_lines(due_reviews, empty=f"- none due as of {as_of}"),
            "",
            "## Future Reviews",
            "",
            *_review_rows_lines(future_reviews, empty="- none scheduled after this date"),
            "",
            "## Review Schedule Warnings",
            "",
            *_invalid_review_lines(invalid_reviews),
            "",
            "## Action Queue Snapshot",
            "",
            *_queue_snapshot_lines(queue),
            "",
            "## Reference Context",
            "",
            _reference_context_section(reference_context, kb_status=kb_status).rstrip(),
            "",
            "## Suggested Teaching Moves",
            "",
            *_teaching_move_lines(due_reviews, previous_session),
            "",
            "## Boundary",
            "",
            (
                "- This is a deterministic handoff plan. It does not run autonomous "
                "tutoring, grade the learner, call an LLM judge, or mutate learning-state truth."
            ),
        ]
    ).rstrip() + "\n"


def _previous_session_lines(
    previous_session_id: str | None,
    previous_session: dict[str, str],
) -> list[str]:
    if previous_session_id is None:
        return ["- none recorded"]
    lines = [f"- Previous session: {previous_session_id}"]
    for label, key in (
        ("Summary", "summary"),
        ("Next actions", "next_actions"),
        ("Detected misconceptions", "misconceptions"),
    ):
        value = previous_session.get(key, "").strip()
        if value:
            lines.append(f"- {label}:")
            lines.extend(f"  {line}" if line else "" for line in value.splitlines())
    return lines


def _review_rows_lines(rows: list[dict[str, str]], *, empty: str) -> list[str]:
    if not rows:
        return [empty]
    lines: list[str] = []
    for row in rows:
        lines.append(
            (
                f"- {row['concept']} | {row['scheduled_for']} | "
                f"{row['priority']} | {row['reason']}"
            )
        )
        if row["repair"]:
            lines.append(f"  - repair: {row['repair']}")
    return lines


def _invalid_review_lines(rows: list[dict[str, str]]) -> list[str]:
    if not rows:
        return ["- none"]
    return [
        f"- {row['concept']} | {row['scheduled_for']} | repair schedule before relying on this item"
        for row in rows
    ]


def _queue_snapshot_lines(queue: LearningQueue) -> list[str]:
    counts = _queue_counts(queue)
    labels = {
        "notes_to_review": "Notes to review",
        "obsidian_exports_to_run": "Obsidian exports to run",
        "misconception_notes_to_draft": "Misconception notes to draft",
        "scheduled_reviews": "Scheduled reviews",
        "exercise_drafts_to_approve": "Exercise drafts to approve",
        "exercises_to_attempt": "Exercises to attempt",
        "attempts_to_grade": "Attempts to grade",
        "quality_checks_to_fix": "Quality checks to fix",
        "tool_verifications_to_fix": "Tool verifications to fix",
    }
    return [f"- {labels[key]}: {value}" for key, value in counts.items()]


def _teaching_move_lines(
    due_reviews: list[dict[str, str]],
    previous_session: dict[str, str],
) -> list[str]:
    lines: list[str] = []
    if due_reviews:
        first = due_reviews[0]
        lines.append(f"- Start with a diagnostic question on {first['concept']}.")
        if first["repair"]:
            lines.append(f"- Use repair focus: {first['repair']}")
    else:
        lines.append("- Start with the current short-term plan focus.")
    if previous_session.get("next_actions", "").strip():
        lines.append("- Reconcile the previous session next actions before new content.")
    lines.extend(
        [
            "- Keep hints minimal until the learner records an attempt.",
            "- End by updating notes, exercises, and learning state from observed evidence.",
        ]
    )
    return lines


def _queue_counts(queue: LearningQueue) -> dict[str, int]:
    return {
        "notes_to_review": len(queue.notes_to_review),
        "obsidian_exports_to_run": len(queue.obsidian_exports_to_run),
        "misconception_notes_to_draft": len(queue.misconception_notes_to_draft),
        "scheduled_reviews": len(queue.scheduled_reviews),
        "exercise_drafts_to_approve": len(queue.exercise_drafts_to_approve),
        "exercises_to_attempt": len(queue.exercises_to_attempt),
        "attempts_to_grade": len(queue.attempts_to_grade),
        "quality_checks_to_fix": len(queue.quality_checks_to_fix),
        "tool_verifications_to_fix": len(queue.tool_verifications_to_fix),
    }


def _next_session_manifest(
    project_root: Path,
    *,
    session_id: str,
    as_of: str,
    plan_path: Path,
    previous_session_id: str | None,
    due_reviews: list[dict[str, str]],
    future_reviews: list[dict[str, str]],
    invalid_reviews: list[dict[str, str]],
    queue: LearningQueue,
    reference_kb_status: str,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "session_id": session_id,
        "status": "ready" if not invalid_reviews else "needs_schedule_repair",
        "quality_boundary": "deterministic_handoff_plan",
        "as_of": as_of,
        "plan_path": plan_path.relative_to(project_root).as_posix(),
        "previous_session_id": previous_session_id,
        "due_reviews": len(due_reviews),
        "future_reviews": len(future_reviews),
        "invalid_review_items": len(invalid_reviews),
        "reference_kb_status": reference_kb_status,
        "action_queue": _queue_counts(queue),
    }


def _chapter_object_count(chapter: dict[str, object]) -> int:
    sections = chapter.get("sections", [])
    if not isinstance(sections, list):
        return 0
    total = 0
    for section in sections:
        if not isinstance(section, dict):
            continue
        objects = section.get("objects", [])
        if isinstance(objects, list):
            total += sum(1 for item in objects if isinstance(item, dict))
    return total


def _long_term_plan(
    topic: str,
    goal: str,
    source_titles: list[str],
    chapter_outline: list[dict[str, object]],
) -> str:
    return f"""# Long Term Plan

## Topic

{topic}

## Goal

{goal}

## Reference Base

{_source_section(source_titles)}
{_reference_reading_path_section(chapter_outline)}
## Milestones

- Establish the core vocabulary and motivating examples for {topic}.
- Build a dependency map from definitions to theorems and standard techniques.
- Practice proof reconstruction and problem solving against the stated goal.
"""


def _short_term_plan(topic: str, goal: str, source_titles: list[str]) -> str:
    return f"""# Short Term Plan

## Focus

Use the first study cycle to turn {topic} into a concrete reading and practice path.

## Goal Alignment

{goal}

## Reference Base

{_source_section(source_titles)}
## Next Steps

- Identify prerequisite concepts for the first session.
- Select the first definitions and examples to study.
- End the cycle with a short diagnostic and exercise attempt.
"""


def _replace_review_adjustments(current: str, schedule: list[object]) -> str:
    marker = "## Review Adjustments"
    before, separator, after = current.partition(marker)
    if separator:
        next_section_index = after.find("\n## ")
        if next_section_index >= 0:
            suffix = after[next_section_index + 1 :]
        else:
            suffix = ""
        current = before.rstrip() + "\n\n" + suffix.lstrip()
    section = _review_adjustments_section(schedule)
    return current.rstrip() + "\n\n" + section


def _review_adjustments_section(schedule: list[object]) -> str:
    lines = ["## Review Adjustments", ""]
    items = [item for item in schedule if isinstance(item, dict)]
    if not items:
        lines.append("- No scheduled review adjustments.")
        return "\n".join(lines) + "\n"
    for item in items:
        concept = item.get("concept", "review")
        priority = item.get("priority", "medium")
        due = item.get("due", "within_3_days")
        scheduled_for = item.get("scheduled_for", "")
        reason = item.get("reason", "review scheduled")
        suffix = f" | scheduled for {scheduled_for}" if scheduled_for else ""
        lines.append(f"- {concept} ({priority}, {due}): {reason}{suffix}")
        for suggestion in _review_repair_suggestions(item.get("repair_context", [])):
            lines.append(f"  - Repair suggestion: {suggestion}")
    return "\n".join(lines) + "\n"


def _review_repair_suggestions(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    suggestions: list[str] = []
    seen: set[str] = set()
    for raw_context in value:
        if not isinstance(raw_context, dict):
            continue
        suggestion = str(raw_context.get("repair_suggestion", "")).strip()
        if not suggestion or suggestion in seen:
            continue
        seen.add(suggestion)
        suggestions.append(suggestion)
    return suggestions


def _session_plan(
    topic: str,
    goal: str,
    source_titles: list[str],
    reference_context: list[dict[str, object]],
    kb_status: str,
    session: SessionPlan,
) -> str:
    prerequisites = "\n".join(f"- {item}" for item in session.prerequisites)
    concepts = "\n".join(f"- {concept}" for concept in session.target_concepts)
    return f"""# Session 0001 Plan

## Objective

{session.objective}

## Topic

{topic}

## Goal

{goal}

## Reference Base

{_source_section(source_titles)}
## Reference Context

{_reference_context_section(reference_context, kb_status=kb_status)}
## Prerequisites

{prerequisites}

## Diagnostic Question

{session.diagnostic_question}

## Target Concepts

{concepts}
"""
