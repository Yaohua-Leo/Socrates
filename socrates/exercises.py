"""Exercise review and approval workflows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .context import append_project_log, load_project, read_json, write_text
from .quality import check_generated_exercise_quality, exercise_quality_issues
from .project import slugify_topic
from .state import (
    LearningStatePatch,
    MistakeRecord,
    build_review_schedule,
    ensure_learning_state_readable,
    resolve_active_misconceptions_for_concept,
    update_learning_state,
)


REVIEW_MASTERY_THRESHOLD = 0.7
EXERCISE_TYPES = frozenset(
    {
        "generated_exercise",
        "targeted_review_exercise",
        "definition_check",
        "example_construction",
        "counterexample_construction",
        "calculation",
        "proof",
        "debug_proof",
        "concept_comparison",
        "mixed_review",
    }
)


@dataclass(frozen=True)
class ExerciseSummary:
    """A lifecycle summary for one generated exercise."""

    exercise_id: str
    status: str
    exercise_type: str
    concept: str
    path: str
    detail: str = ""


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


def list_exercises(
    project_path: Path | str, *, status: str = "all", exercise_type: str = "all"
) -> list[ExerciseSummary]:
    """List generated exercises by their current learner/reviewer state and type."""

    allowed_statuses = {"all", "draft", "approved", "attempted", "graded"}
    if status not in allowed_statuses:
        allowed = ", ".join(sorted(allowed_statuses))
        raise ValueError(f"Unknown exercise status {status!r}; expected one of: {allowed}")
    allowed_types = {"all", *EXERCISE_TYPES}
    if exercise_type not in allowed_types:
        allowed = ", ".join(sorted(allowed_types))
        raise ValueError(f"Unknown exercise type {exercise_type!r}; expected one of: {allowed}")

    context = load_project(project_path)
    attempts_by_exercise = _attempts_by_exercise(context.root)
    graded_attempts = _graded_attempts(context.root)
    summaries: list[ExerciseSummary] = []
    for exercise_path in sorted(context.generated_exercises_dir.glob("*.md"), key=lambda path: path.stem):
        exercise_id = exercise_path.stem
        text = exercise_path.read_text(encoding="utf-8")
        summary_status, detail = _exercise_lifecycle_status(
            text=text,
            attempts=attempts_by_exercise.get(exercise_id, []),
            graded_attempts=graded_attempts,
        )
        summaries.append(
            ExerciseSummary(
                exercise_id=exercise_id,
                status=summary_status,
                exercise_type=_frontmatter_value(text, "type") or "generated_exercise",
                concept=_frontmatter_value(text, "concept") or exercise_id,
                path=exercise_path.relative_to(context.root).as_posix(),
                detail=detail,
            )
        )
    if status != "all":
        summaries = [summary for summary in summaries if summary.status == status]
    if exercise_type != "all":
        summaries = [summary for summary in summaries if summary.exercise_type == exercise_type]
    return sorted(summaries, key=lambda summary: (_exercise_status_order(summary.status), summary.exercise_id))


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
    *,
    misconception_id: str | None = None,
    analysis: str | None = None,
    repair_suggestion: str | None = None,
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

    ensure_learning_state_readable(
        context.learning_state,
        action="grading exercise attempts",
    )

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
    concept_id = slugify_topic(concept)
    mistakes = []
    if misconception_id:
        mistakes.append(
            MistakeRecord(
                session_id=attempt_id,
                concept=concept_id,
                misconception_id=slugify_topic(misconception_id),
                user_answer=_attempt_answer(attempt_text),
                analysis=_one_line(analysis) or "Recorded during exercise grading.",
                repair_suggestion=(
                    _one_line(repair_suggestion)
                    or _one_line(feedback_text)
                    or f"Review feedback for {attempt_id}."
                ),
                follow_up_exercises=[exercise_id],
            )
        )
    update_learning_state(
        context,
        LearningStatePatch(
            concept_mastery={concept_id: score},
            proof_skills={"exercise_solving": score},
            mistakes=mistakes,
        ),
    )
    if score >= REVIEW_MASTERY_THRESHOLD:
        resolve_active_misconceptions_for_concept(context, concept_id)
    if score < REVIEW_MASTERY_THRESHOLD or _has_review_schedule(context.learning_state):
        build_review_schedule(context, mastery_threshold=REVIEW_MASTERY_THRESHOLD)
    append_project_log(context, f"Graded attempt {attempt_id} with score {score:g}.")
    return grade_path


def _has_review_schedule(learning_state_path: Path) -> bool:
    state = read_json(learning_state_path) if learning_state_path.exists() else {}
    if not isinstance(state, dict):
        return False
    schedule = state.get("review_schedule", [])
    return isinstance(schedule, list) and bool(schedule)


def _attempts_by_exercise(project_root: Path) -> dict[str, list[str]]:
    attempted_dir = project_root / "05_exercises" / "attempted"
    attempts: dict[str, list[str]] = {}
    if not attempted_dir.exists():
        return attempts
    for attempt_path in sorted(attempted_dir.glob("*.md"), key=lambda path: path.stem):
        text = attempt_path.read_text(encoding="utf-8")
        exercise_id = _frontmatter_value(text, "exercise_id") or _exercise_id_from_attempt(attempt_path.stem)
        attempts.setdefault(exercise_id, []).append(attempt_path.stem)
    return attempts


def _graded_attempts(project_root: Path) -> dict[str, str]:
    graded_dir = project_root / "05_exercises" / "graded"
    graded: dict[str, str] = {}
    if not graded_dir.exists():
        return graded
    for grade_path in sorted(graded_dir.glob("*.md"), key=lambda path: path.stem):
        text = grade_path.read_text(encoding="utf-8")
        attempt_id = _frontmatter_value(text, "attempt_id") or grade_path.stem.removesuffix("_grade")
        score = _frontmatter_value(text, "score")
        graded[attempt_id] = f"score {score}" if score else "graded"
    return graded


def _exercise_lifecycle_status(
    *,
    text: str,
    attempts: list[str],
    graded_attempts: dict[str, str],
) -> tuple[str, str]:
    ungraded_attempts = [attempt_id for attempt_id in attempts if attempt_id not in graded_attempts]
    if ungraded_attempts:
        return ("attempted", f"attempt {ungraded_attempts[-1]}")
    graded = [attempt_id for attempt_id in attempts if attempt_id in graded_attempts]
    if graded:
        attempt_id = graded[-1]
        return ("graded", f"{attempt_id}, {graded_attempts[attempt_id]}")
    if _is_approved_exercise(text):
        return ("approved", "")
    return ("draft", "")


def _exercise_status_order(status: str) -> int:
    return {"draft": 0, "approved": 1, "attempted": 2, "graded": 3}.get(status, 4)


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


def _attempt_answer(attempt_text: str) -> str:
    marker = "## Answer"
    if marker not in attempt_text:
        return "No answer recorded."
    answer = attempt_text.split(marker, 1)[1].strip()
    return answer or "No answer recorded."


def _one_line(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(value.split())


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
