"""Exercise review and approval workflows."""

from __future__ import annotations

from pathlib import Path

from .context import append_project_log, load_project, write_text
from .quality import check_generated_exercise_quality, exercise_quality_issues


def approve_exercise_draft(project_path: Path | str, exercise_id: str) -> Path:
    """Mark one generated exercise draft as approved after quality checks."""

    context = load_project(project_path)
    exercise_path = context.generated_exercises_dir / f"{exercise_id}.md"
    if not exercise_path.exists():
        raise FileNotFoundError(f"Generated exercise does not exist: {exercise_path}")

    issues = exercise_quality_issues(exercise_path)
    if issues:
        result = check_generated_exercise_quality(context.root)
        raise ValueError(
            f"Exercise draft {exercise_id} failed quality gate: "
            f"{'; '.join(issues)}. See {result.report_path}"
        )

    approved_text = _set_frontmatter_values(
        exercise_path.read_text(encoding="utf-8"),
        {
            "status": '"approved"',
            "review_status": '"approved"',
            "reviewed_by_user": "true",
        },
    )
    write_text(exercise_path, approved_text)
    append_project_log(context, f"Approved exercise draft {exercise_id}.")
    return exercise_path


def _set_frontmatter_values(text: str, values: dict[str, str]) -> str:
    if not text.startswith("---\n"):
        added = ["---", *(f"{key}: {value}" for key, value in values.items()), "---", ""]
        return "\n".join(added) + text

    parts = text.split("---\n", 2)
    if len(parts) != 3:
        return text
    _, frontmatter_text, body = parts
    lines = frontmatter_text.rstrip("\n").splitlines()
    seen: set[str] = set()
    updated: list[str] = []
    for line in lines:
        key, separator, _ = line.partition(":")
        if separator and key in values:
            updated.append(f"{key}: {values[key]}")
            seen.add(key)
        else:
            updated.append(line)
    for key, value in values.items():
        if key not in seen:
            updated.append(f"{key}: {value}")
    return "---\n" + "\n".join(updated) + "\n---\n" + body
