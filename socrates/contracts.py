"""Shared data contracts for Socrates v0.1 workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
import json


def yaml_scalar(value: object) -> str:
    """Return a conservative YAML scalar for generated project files."""

    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


@dataclass(frozen=True)
class SourceRecord:
    """A single entry in ``01_references/source_registry.yaml``."""

    id: str
    type: str
    title: str
    role: str
    priority: int
    status: str
    local_path: str
    processed_paths: dict[str, str | None] = field(
        default_factory=lambda: {"markdown": None, "curated": None}
    )
    notes: str = ""

    def to_registry_yaml(self) -> str:
        """Serialize the record as one item in the source registry."""

        processed = self.processed_paths or {"markdown": None, "curated": None}
        lines = [
            f"- id: {self.id}",
            f"  type: {self.type}",
            f"  title: {yaml_scalar(self.title)}",
            f"  role: {self.role}",
            f"  priority: {self.priority}",
            f"  status: {self.status}",
            f"  local_path: {yaml_scalar(self.local_path)}",
            "  processed_paths:",
        ]
        for key in sorted(processed):
            lines.append(f"    {key}: {yaml_scalar(processed[key])}")
        lines.append(f"  notes: {yaml_scalar(self.notes)}")
        return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class SessionPlan:
    """A deterministic plan for one teaching session."""

    session_id: str
    objective: str
    prerequisites: list[str]
    diagnostic_question: str
    target_concepts: list[str]


@dataclass(frozen=True)
class TeachingSession:
    """Paths and metadata produced by a completed teaching session."""

    session_id: str
    hint_level: int
    transcript_path: str
    summary_path: str
    misconceptions_path: str


@dataclass(frozen=True)
class AtomicNoteDraft:
    """A draft note awaiting user review."""

    id: str
    type: str
    concept: str
    path: str


@dataclass(frozen=True)
class ExerciseDraft:
    """A generated exercise awaiting review."""

    id: str
    type: str
    difficulty: int
    path: str


@dataclass(frozen=True)
class MisconceptionRecord:
    """A concise record of a detected learning mistake."""

    id: str
    concept: str
    mistake_type: str
    status: str = "active"


@dataclass(frozen=True)
class LearningStateUpdate:
    """Summary of state changes written after a learning session."""

    session_id: str
    updated_concepts: list[str]
    misconceptions: list[MisconceptionRecord]
