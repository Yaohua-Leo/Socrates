"""Learning-plan generation for initialized Socrates projects."""

from __future__ import annotations

import json
from pathlib import Path

from socrates.context import load_project, write_text
from socrates.contracts import SessionPlan


def create_learning_plan(project_path: Path | str) -> list[Path]:
    """Create the initial long-term, short-term, and first-session plans."""

    context = load_project(project_path)
    project = _read_project_metadata(context.project_file)
    source_titles = _read_source_titles(context.source_registry)
    reference_context = _read_reference_context(context.root, project["topic"])
    session = SessionPlan(
        session_id="session_0001",
        objective=f"Orient to {project['topic']} and convert the goal into a study map.",
        prerequisites=["Project has been initialized.", "Reference registry has been reviewed."],
        diagnostic_question=f"What do you already know that is closest to {project['topic']}?",
        target_concepts=[project["topic"]],
    )

    plans = {
        context.learning_plan_dir / "long_term_plan.md": _long_term_plan(
            project["topic"], project["goal"], source_titles
        ),
        context.learning_plan_dir / "short_term_plan.md": _short_term_plan(
            project["topic"], project["goal"], source_titles
        ),
        context.learning_plan_dir / "session_0001_plan.md": _session_plan(
            project["topic"], project["goal"], source_titles, reference_context, session
        ),
    }
    for path, content in plans.items():
        write_text(path, content)
    return list(plans)


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

    index = json.loads(index_path.read_text(encoding="utf-8"))
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


def _reference_context_section(reference_context: list[dict[str, object]]) -> str:
    if not reference_context:
        return "- Reference KB context: none indexed yet.\n"
    lines = ["- Reference KB context:"]
    for item in reference_context:
        source = item.get("source", {})
        source_path = "unknown"
        if isinstance(source, dict):
            source_path = str(source.get("path", "unknown"))
        dependencies = [str(dep) for dep in item.get("dependencies", [])]
        lines.append(f"  - {str(item.get('type', '')).title()}: {item.get('title', '')}")
        lines.append(f"    Source: {source_path}")
        if dependencies:
            lines.append(f"    Depends: {', '.join(dependencies)}")
    return "\n".join(lines) + "\n"


def _long_term_plan(topic: str, goal: str, source_titles: list[str]) -> str:
    return f"""# Long Term Plan

## Topic

{topic}

## Goal

{goal}

## Reference Base

{_source_section(source_titles)}
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


def _session_plan(
    topic: str,
    goal: str,
    source_titles: list[str],
    reference_context: list[dict[str, object]],
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

{_reference_context_section(reference_context)}
## Prerequisites

{prerequisites}

## Diagnostic Question

{session.diagnostic_question}

## Target Concepts

{concepts}
"""
