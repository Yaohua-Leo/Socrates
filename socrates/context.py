"""Project loading and shared file helpers for Socrates workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path


@dataclass(frozen=True)
class ProjectContext:
    """Resolved canonical paths for one Socrates learning project."""

    root: Path

    @property
    def project_file(self) -> Path:
        return self.root / "project.yaml"

    @property
    def meta_dir(self) -> Path:
        return self.root / "00_meta"

    @property
    def project_log(self) -> Path:
        return self.meta_dir / "project_log.md"

    @property
    def learning_state(self) -> Path:
        return self.meta_dir / "learning_state.json"

    @property
    def references_dir(self) -> Path:
        return self.root / "01_references"

    @property
    def source_registry(self) -> Path:
        return self.references_dir / "source_registry.yaml"

    @property
    def learning_plan_dir(self) -> Path:
        return self.root / "02_learning_plan"

    @property
    def sessions_dir(self) -> Path:
        return self.root / "03_sessions"

    @property
    def atomic_note_drafts_dir(self) -> Path:
        return self.root / "04_atomic_notes" / "drafts"

    @property
    def generated_exercises_dir(self) -> Path:
        return self.root / "05_exercises" / "generated"

    @property
    def mistake_bank(self) -> Path:
        return self.root / "05_exercises" / "mistake_bank.md"

    @property
    def evals_dir(self) -> Path:
        return self.root / "08_evals"


def load_project(path: Path | str) -> ProjectContext:
    """Load a Socrates project and validate that it has a project file."""

    root = Path(path).expanduser().resolve()
    project_file = root / "project.yaml"
    if not project_file.exists():
        raise FileNotFoundError(f"Missing Socrates project file: {project_file}")
    return ProjectContext(root=root)


def append_project_log(context: ProjectContext, message: str) -> None:
    """Append a dated project-log bullet."""

    existing = context.project_log.read_text(encoding="utf-8")
    entry = f"\n## {date.today().isoformat()}\n\n- {message}\n"
    context.project_log.write_text(existing.rstrip() + entry, encoding="utf-8", newline="\n")


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def project_title(project_file: Path, *, fallback: str) -> str:
    try:
        lines = project_file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return fallback
    in_project = False
    for line in lines:
        stripped = line.strip()
        if stripped == "project:":
            in_project = True
            continue
        if in_project and stripped.startswith("title:"):
            title = _yaml_like_string(stripped.removeprefix("title:").strip())
            return title or fallback
        if in_project and line and not line.startswith(" "):
            break
    return fallback


def _yaml_like_string(value: str) -> str:
    if value in {"", "null"}:
        return ""
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return value.strip("'\"")
    return parsed if isinstance(parsed, str) else str(parsed)


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
