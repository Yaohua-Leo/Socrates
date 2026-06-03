"""Learning-project creation for Socrates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path
import re
import unicodedata


class ProjectExistsError(RuntimeError):
    """Raised when project initialization would overwrite existing content."""


@dataclass(frozen=True)
class ProjectSpec:
    """Input specification for a Socrates learning project."""

    topic: str
    path: Path | str
    goal: str = ""
    main_reference: str | None = None
    target_level: str = "advanced_undergraduate"
    preferred_style: str = "proof_oriented"


PROJECT_DIRECTORIES = (
    "00_meta",
    "01_references/raw",
    "01_references/converted",
    "01_references/curated",
    "02_learning_plan",
    "03_sessions",
    "04_atomic_notes/drafts",
    "04_atomic_notes/definitions",
    "04_atomic_notes/theorems",
    "04_atomic_notes/examples",
    "04_atomic_notes/counterexamples",
    "04_atomic_notes/techniques",
    "04_atomic_notes/exercises",
    "05_exercises/generated",
    "05_exercises/attempted",
    "05_exercises/solutions",
    "05_exercises/graded",
    "06_kb/embeddings",
    "06_kb/chunks",
    "06_kb/retrieval_index",
    "07_exports/obsidian",
    "07_exports/reports",
    "07_exports/latex_notes",
    "07_exports/pdf",
    "08_evals",
)


def create_project(spec: ProjectSpec) -> Path:
    """Create a Socrates learning project and return its absolute path."""

    project_path = Path(spec.path).expanduser().resolve()
    _ensure_safe_target(project_path)

    for relative_dir in PROJECT_DIRECTORIES:
        (project_path / relative_dir).mkdir(parents=True, exist_ok=True)

    project_id = slugify_topic(spec.topic)
    _write_text(project_path / "project.yaml", _project_yaml(spec, project_id))
    _write_text(project_path / "README.md", _project_readme(spec))
    _write_text(project_path / "00_meta" / "goals.md", _goals_md(spec))
    _write_text(project_path / "00_meta" / "user_profile.md", "# User Profile\n\n")
    _write_text(project_path / "00_meta" / "decisions.md", "# Decisions\n\n")
    _write_text(project_path / "00_meta" / "project_log.md", _project_log(spec))
    _write_json(project_path / "00_meta" / "progress.json", {"events": []})
    _write_json(
        project_path / "00_meta" / "learning_state.json",
        {
            "concept_mastery": {},
            "proof_skills": {},
            "misconceptions": {},
        },
    )
    _write_text(project_path / "01_references" / "source_registry.yaml", "sources: []\n")
    _write_text(project_path / "01_references" / "citations.bib", "")
    _write_text(project_path / "02_learning_plan" / "long_term_plan.md", "# Long Term Plan\n\n")
    _write_text(project_path / "02_learning_plan" / "short_term_plan.md", "# Short Term Plan\n\n")
    _write_text(project_path / "02_learning_plan" / "chapter_sequence.yaml", "chapters: []\n")
    _write_text(project_path / "02_learning_plan" / "checkpoints.yaml", "checkpoints: []\n")
    _write_text(project_path / "05_exercises" / "mistake_bank.md", "# Mistake Bank\n\n")
    _write_json(project_path / "06_kb" / "concept_graph.json", {"nodes": [], "edges": []})
    _write_json(project_path / "06_kb" / "dependency_graph.json", {"nodes": [], "edges": []})
    _write_text(project_path / "08_evals" / "ingestion_eval.md", "# Ingestion Eval\n\n")
    _write_text(project_path / "08_evals" / "tutoring_eval.md", "# Tutoring Eval\n\n")
    _write_text(project_path / "08_evals" / "exercise_eval.md", "# Exercise Eval\n\n")
    _write_text(project_path / "08_evals" / "note_quality_eval.md", "# Note Quality Eval\n\n")

    return project_path


def slugify_topic(topic: str) -> str:
    """Convert a topic name into a stable filesystem/project identifier."""

    normalized = unicodedata.normalize("NFKD", topic)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_text).strip("_")
    return slug or "socrates_project"


def _ensure_safe_target(project_path: Path) -> None:
    if project_path.exists() and not project_path.is_dir():
        raise ProjectExistsError(f"Target path is not a directory: {project_path}")
    if project_path.exists():
        existing_items = list(project_path.iterdir())
        if existing_items or (project_path / "project.yaml").exists():
            raise ProjectExistsError(f"Target directory is not empty: {project_path}")
        return
    project_path.mkdir(parents=True, exist_ok=False)


def _project_yaml(spec: ProjectSpec, project_id: str) -> str:
    main_reference = yaml_scalar(spec.main_reference) if spec.main_reference else "null"
    return f"""project:
  id: {project_id}
  title: {yaml_scalar(spec.topic)}
  created_at: {yaml_scalar(date.today().isoformat())}
  status: active

user_goal:
  description: {yaml_scalar(spec.goal)}
  target_level: {yaml_scalar(spec.target_level)}
  preferred_style: {yaml_scalar(spec.preferred_style)}
  output_format:
    - obsidian_notes
    - exercises
    - summaries

references:
  main_reference: {main_reference}
  source_registry: 01_references/source_registry.yaml

learning:
  current_phase: initialization
  current_topic: null
  current_session: null

policies:
  answer_policy: socratic
  note_policy: draft_first
  verification_policy: conservative
"""


def _project_readme(spec: ProjectSpec) -> str:
    goal = spec.goal or "No goal recorded yet."
    return f"""# {spec.topic}

This is a Socrates mathematics learning project.

## Goal

{goal}

## Current Phase

initialization
"""


def _goals_md(spec: ProjectSpec) -> str:
    goal = spec.goal or "No goal recorded yet."
    main_reference = spec.main_reference or "No main reference recorded yet."
    return f"""# Goals

## Topic

{spec.topic}

## Learning Goal

{goal}

## Main Reference

{main_reference}
"""


def _project_log(spec: ProjectSpec) -> str:
    return f"""# Project Log

## {date.today().isoformat()}

- Initialized Socrates project for topic: {spec.topic}
"""


def yaml_scalar(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
