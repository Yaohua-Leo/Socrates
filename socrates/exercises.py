"""Exercise review and approval workflows."""

from __future__ import annotations

from pathlib import Path

from .context import append_project_log, load_project, write_text
from .quality import check_generated_exercise_quality, exercise_quality_issues
from .project import slugify_topic
from .state import LearningStatePatch, build_review_schedule, update_learning_state


REVIEW_MASTERY_THRESHOLD = 0.7


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


def grade_exercise_attempt(
    project_path: Path | str,
    attempt_id: str,
    score: float,
    feedback_path: Path | str,
) -> Path:
    """Write a grade artifact for one recorded exercise attempt."""

    if score < 0 or score > 1:
        raise ValueError("Exercise grade score must be between 0 and 1.")

    context = load_project(project_path)
    attempt_path = context.root / "05_exercises" / "attempted" / f"{attempt_id}.md"
    if not attempt_path.exists():
        raise FileNotFoundError(f"Attempt does not exist: {attempt_path}")

    attempt_text = attempt_path.read_text(encoding="utf-8")
    exercise_id = _frontmatter_value(attempt_text, "exercise_id") or _exercise_id_from_attempt(attempt_id)
    source_exercise = _frontmatter_value(attempt_text, "source_exercise")
    exercise_path = context.root / source_exercise if source_exercise else context.generated_exercises_dir / f"{exercise_id}.md"
    if not exercise_path.exists():
        raise FileNotFoundError(f"Source exercise does not exist: {exercise_path}")
    concept = _frontmatter_value(exercise_path.read_text(encoding="utf-8"), "concept") or exercise_id

    feedback_file = Path(feedback_path).expanduser().resolve()
    if not feedback_file.exists():
        raise FileNotFoundError(f"Feedback file does not exist: {feedback_file}")
    feedback_text = feedback_file.read_text(encoding="utf-8").rstrip()

    grade_path = context.root / "05_exercises" / "graded" / f"{attempt_id}_grade.md"
    write_text(
        grade_path,
        _grade_text(
            attempt_id=attempt_id,
            exercise_id=exercise_id,
            score=score,
            concept=concept,
            source_attempt=attempt_path.relative_to(context.root).as_posix(),
            feedback_text=feedback_text,
        ),
    )
    update_learning_state(
        context,
        LearningStatePatch(
            concept_mastery={slugify_topic(concept): score},
            proof_skills={"exercise_solving": score},
        ),
    )
    if score < REVIEW_MASTERY_THRESHOLD:
        build_review_schedule(context, mastery_threshold=REVIEW_MASTERY_THRESHOLD)
    append_project_log(context, f"Graded attempt {attempt_id} with score {score:g}.")
    return grade_path


def _next_attempt_path(project_root: Path, exercise_id: str) -> Path:
    attempted_dir = project_root / "05_exercises" / "attempted"
    for index in range(1, 1000):
        path = attempted_dir / f"{exercise_id}_attempt_{index:03d}.md"
        if not path.exists():
            return path
    raise RuntimeError(f"Too many attempts recorded for exercise {exercise_id}.")


def _exercise_id_from_attempt(attempt_id: str) -> str:
    marker = "_attempt_"
    if marker not in attempt_id:
        return attempt_id
    return attempt_id.split(marker, 1)[0]


def _is_approved_exercise(text: str) -> bool:
    return 'status: "approved"' in text and "reviewed_by_user: true" in text


def _frontmatter_value(text: str, key: str) -> str | None:
    if not text.startswith("---\n"):
        return None
    parts = text.split("---\n", 2)
    if len(parts) != 3:
        return None
    prefix = f"{key}:"
    for line in parts[1].splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip().strip('"')
    return None


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


def _grade_text(
    *,
    attempt_id: str,
    exercise_id: str,
    score: float,
    concept: str,
    source_attempt: str,
    feedback_text: str,
) -> str:
    return (
        "---\n"
        f'attempt_id: "{attempt_id}"\n'
        f'exercise_id: "{exercise_id}"\n'
        'status: "graded"\n'
        f"score: {score:g}\n"
        f'concept: "{concept}"\n'
        f'source_attempt: "{source_attempt}"\n'
        "---\n\n"
        f"# Grade: {attempt_id}\n\n"
        "## Feedback\n\n"
        f"{feedback_text}\n"
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
