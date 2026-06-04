"""Structured parsing and validation for generated exercise Markdown."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .contracts import (
    EXERCISE_ALLOWED_REVIEW_STATUSES,
    EXERCISE_ALLOWED_STATUSES,
    EXERCISE_ALLOWED_TYPES,
)


EXERCISE_SCHEMA_VERSION = "v0.4"


@dataclass(frozen=True)
class HintStep:
    level: int
    label: str
    text: str


@dataclass(frozen=True)
class SolutionStep:
    index: int
    text: str


@dataclass(frozen=True)
class RubricItem:
    label: str
    points: int


@dataclass(frozen=True)
class Rubric:
    total_points: int
    items: list[RubricItem]


@dataclass(frozen=True)
class ExerciseSpec:
    path: Path
    exercise_id: str
    schema_version: str
    status: str
    review_status: str
    exercise_type: str
    concept: str
    source_id: str
    difficulty: int
    statement: str
    target_training_point: str
    concepts: list[str]
    prerequisites: list[str]
    hints: list[HintStep]
    solution_steps: list[SolutionStep]
    rubric: Rubric
    common_mistakes: list[str]
    reference_kb_status: str = ""


def parse_exercise_markdown(path: Path | str) -> ExerciseSpec:
    """Parse one generated exercise Markdown file into a structured spec."""

    exercise_path = Path(path)
    text = exercise_path.read_text(encoding="utf-8")
    frontmatter, body = _split_frontmatter(text)
    sections = _sections(body)
    return ExerciseSpec(
        path=exercise_path,
        exercise_id=exercise_path.stem,
        schema_version=frontmatter.get("schema_version", ""),
        status=frontmatter.get("status", ""),
        review_status=frontmatter.get("review_status", ""),
        exercise_type=frontmatter.get("type", ""),
        concept=frontmatter.get("concept", ""),
        source_id=frontmatter.get("source_id", ""),
        difficulty=_int_frontmatter(frontmatter.get("difficulty"), default=0),
        statement=sections.get("Statement", "").strip(),
        target_training_point=sections.get("Target Training Point", "").strip(),
        concepts=_bullet_items(sections.get("Concepts", "")),
        prerequisites=_bullet_items(sections.get("Prerequisites", "")),
        hints=_hint_steps(sections.get("Hints", "")),
        solution_steps=_solution_steps(sections.get("Solution Outline", "")),
        rubric=_rubric(sections.get("Rubric", "")),
        common_mistakes=_bullet_items(sections.get("Common Mistakes", "")),
        reference_kb_status=frontmatter.get("reference_kb_status", ""),
    )


def validate_exercise_spec(spec: ExerciseSpec) -> list[str]:
    """Return conservative schema and evidence issues for one exercise spec."""

    issues: list[str] = []
    if spec.schema_version and spec.schema_version != EXERCISE_SCHEMA_VERSION:
        issues.append("unsupported exercise schema version")
    if spec.status not in EXERCISE_ALLOWED_STATUSES:
        issues.append("invalid exercise status")
    if spec.review_status not in EXERCISE_ALLOWED_REVIEW_STATUSES:
        issues.append("invalid exercise review status")
    if spec.exercise_type not in EXERCISE_ALLOWED_TYPES:
        issues.append("invalid exercise type")
    if not spec.concept:
        issues.append("missing concept")
    if not spec.source_id and spec.exercise_type == "generated_exercise":
        issues.append("missing source id")
    if spec.difficulty < 1 or spec.difficulty > 5:
        issues.append("difficulty must be between 1 and 5")
    if not spec.statement:
        issues.append("missing statement")
    if not spec.target_training_point:
        issues.append("missing target training point")
    if not spec.concepts:
        issues.append("missing concepts")
    if not spec.prerequisites:
        issues.append("missing prerequisites")
    if len(spec.hints) < 3:
        issues.append("hint ladder must include at least three hints")
    if spec.hints and [hint.level for hint in spec.hints] != list(range(1, len(spec.hints) + 1)):
        issues.append("non-progressive hint ladder")
    if len(spec.solution_steps) < 3:
        issues.append("solution outline must include at least three steps")
    if spec.rubric.total_points <= 0:
        issues.append("missing rubric total")
    if len(spec.rubric.items) < 2:
        issues.append("rubric must include multiple criteria")
    if sum(item.points for item in spec.rubric.items) != spec.rubric.total_points:
        issues.append("rubric point values do not sum to total")
    if not spec.common_mistakes:
        issues.append("missing common mistakes")
    return issues


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    parts = text.split("---\n", 2)
    if len(parts) != 3:
        return {}, text
    _, frontmatter_text, body = parts
    values: dict[str, str] = {}
    for line in frontmatter_text.splitlines():
        key, separator, raw_value = line.partition(":")
        if not separator:
            continue
        value = raw_value.strip()
        if not value or value == "[]":
            continue
        values[key.strip()] = value.strip('"')
    return values, body


def _sections(body: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current: str | None = None
    lines: list[str] = []
    for line in body.splitlines():
        if line.startswith("## "):
            if current is not None:
                sections[current] = "\n".join(lines).strip()
            current = line.removeprefix("## ").strip()
            lines = []
            continue
        if current is not None:
            lines.append(line)
    if current is not None:
        sections[current] = "\n".join(lines).strip()
    return sections


def _bullet_items(text: str) -> list[str]:
    items: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        value = stripped.removeprefix("- ").strip()
        if value and value != "None recorded.":
            items.append(value)
    return items


def _hint_steps(text: str) -> list[HintStep]:
    hints: list[HintStep] = []
    pattern = re.compile(r"^- Hint\s+(\d+)\s+\(([^)]+)\):\s*(.+)$")
    for line in text.splitlines():
        match = pattern.match(line.strip())
        if match:
            hints.append(
                HintStep(
                    level=int(match.group(1)),
                    label=match.group(2).strip(),
                    text=match.group(3).strip(),
                )
            )
    return hints


def _solution_steps(text: str) -> list[SolutionStep]:
    steps: list[SolutionStep] = []
    pattern = re.compile(r"^- Step\s+(\d+):\s*(.+)$")
    for line in text.splitlines():
        match = pattern.match(line.strip())
        if match:
            steps.append(SolutionStep(index=int(match.group(1)), text=match.group(2).strip()))
    return steps


def _rubric(text: str) -> Rubric:
    total = 0
    items: list[RubricItem] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        value = stripped.removeprefix("- ").strip()
        match = re.match(r"(.+?):\s*(\d+)\s*pts?$", value)
        if not match:
            continue
        label = match.group(1).strip()
        points = int(match.group(2))
        if label.casefold() == "total":
            total = points
        else:
            items.append(RubricItem(label=label, points=points))
    return Rubric(total_points=total, items=items)


def _int_frontmatter(value: str | None, *, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default
