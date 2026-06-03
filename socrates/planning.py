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
            project["topic"], project["goal"], source_titles, session
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
## Prerequisites

{prerequisites}

## Diagnostic Question

{session.diagnostic_question}

## Target Concepts

{concepts}
"""
