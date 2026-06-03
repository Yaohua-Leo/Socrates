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


def record_exercise_attempt(
    project_path: Path | str,
    exercise_id: str,
    answer_path: Path | str,
) -> Path:
    """Record one learner answer for an approved exercise."""

    context = load_project(project_path)
    exercise_path = context.generated_exercises_dir / f"{exercise_id}.md"
    if not exercise_path.exists():
        raise FileNotFoundError(f"Generated exercise does not exist: {exercise_path}")
    exercise_text = exercise_path.read_text(encoding="utf-8")
    if not _is_approved_exercise(exercise_text):
        raise ValueError(f"Exercise {exercise_id} is not approved for attempts.")

    answer_file = Path(answer_path).expanduser().resolve()
    if not answer_file.exists():
        raise FileNotFoundError(f"Answer file does not exist: {answer_file}")
    answer_text = answer_file.read_text(encoding="utf-8").rstrip()
    attempt_path = _next_attempt_path(context.root, exercise_id)
    write_text(
        attempt_path,
        _attempt_text(
            exercise_id=exercise_id,
            source_exercise=exercise_path.relative_to(context.root).as_posix(),
            answer_text=answer_text,
        ),
    )
    append_project_log(context, f"Recorded attempt for exercise {exercise_id}.")
    return attempt_path


def _next_attempt_path(project_root: Path, exercise_id: str) -> Path:
    attempted_dir = project_root / "05_exercises" / "attempted"
    for index in range(1, 1000):
        path = attempted_dir / f"{exercise_id}_attempt_{index:03d}.md"
        if not path.exists():
            return path
    raise RuntimeError(f"Too many attempts recorded for exercise {exercise_id}.")


def _is_approved_exercise(text: str) -> bool:
    return 'status: "approved"' in text and "reviewed_by_user: true" in text


def _attempt_text(
    *,
    exercise_id: str,
    source_exercise: str,
    answer_text: str,
) -> str:
    return (
        "---\n"
        f'exercise_id: "{exercise_id}"\n'
        'status: "attempted"\n'
        f'source_exercise: "{source_exercise}"\n'
        "---\n\n"
        f"# Attempt: {exercise_id}\n\n"
        "## Answer\n\n"
        f"{answer_text}\n"
    )


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
