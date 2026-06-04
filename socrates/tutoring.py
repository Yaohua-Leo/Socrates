"""Scripted tutoring-session lane for Socrates projects."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from socrates.context import load_project, write_text
from socrates.llm import LlmClient, LlmMessage, LlmRequest, parse_json_object, sha256_text
from socrates.llm_artifacts import record_llm_suggestion


@dataclass(frozen=True)
class TutoringSessionResult:
    """Filesystem result for a scripted tutoring session."""

    session_id: str
    session_dir: Path


@dataclass(frozen=True)
class TutoringSessionSummary:
    """A filesystem summary for one persisted tutoring session."""

    session_id: str
    status: str
    path: str
    missing_artifacts: tuple[str, ...]
    quality_status: str | None = None
    quality_score: int | None = None


@dataclass(frozen=True)
class _Script:
    topic: str
    goal: str
    question: str
    hints: tuple[str, ...]
    attempts: tuple[str, ...]
    solution: str | None
    misconceptions: tuple[str, ...]
    next_actions: tuple[str, ...]


SESSION_ARTIFACTS = (
    "transcript.md",
    "tutor_notes.md",
    "detected_misconceptions.md",
    "summary.md",
    "next_actions.md",
)


def run_scripted_tutoring_session(
    project_path: Path | str,
    script_path: Path | str,
    *,
    session_id: str,
) -> TutoringSessionResult:
    """Run a deterministic scripted tutoring session and write session artifacts."""

    context = load_project(project_path)
    script = _read_script(Path(script_path))
    session_dir = context.sessions_dir / session_id

    write_text(session_dir / "transcript.md", _transcript(session_id, script))
    write_text(session_dir / "tutor_notes.md", _tutor_notes(script))
    write_text(
        session_dir / "detected_misconceptions.md",
        _bullet_doc("Detected Misconceptions", script.misconceptions, "None detected."),
    )
    write_text(session_dir / "summary.md", _summary(script))
    write_text(
        session_dir / "next_actions.md",
        _bullet_doc("Next Actions", script.next_actions, "No next actions recorded."),
    )

    return TutoringSessionResult(session_id=session_id, session_dir=session_dir)


def list_tutoring_sessions(
    project_path: Path | str,
    *,
    status: str = "all",
) -> list[TutoringSessionSummary]:
    """List persisted tutoring sessions and required artifact completeness."""

    allowed_statuses = {"all", "complete", "incomplete"}
    if status not in allowed_statuses:
        allowed = ", ".join(sorted(allowed_statuses))
        raise ValueError(f"Unknown session status {status!r}; expected one of: {allowed}")

    context = load_project(project_path)
    summaries: list[TutoringSessionSummary] = []
    quality_by_session = _tutoring_quality_by_session(context.root)
    if not context.sessions_dir.exists():
        return summaries
    for session_dir in sorted(context.sessions_dir.iterdir(), key=lambda path: path.name):
        if not session_dir.is_dir():
            continue
        missing = tuple(name for name in SESSION_ARTIFACTS if not (session_dir / name).exists())
        session_status = "incomplete" if missing else "complete"
        quality_status, quality_score = quality_by_session.get(session_dir.name, (None, None))
        summaries.append(
            TutoringSessionSummary(
                session_id=session_dir.name,
                status=session_status,
                path=session_dir.relative_to(context.root).as_posix(),
                missing_artifacts=missing,
                quality_status=quality_status,
                quality_score=quality_score,
            )
        )
    if status != "all":
        summaries = [summary for summary in summaries if summary.status == status]
    return summaries


def suggest_next_question_with_llm(
    project_path: Path | str,
    session_id: str,
    *,
    client: LlmClient,
) -> Path:
    """Write a reviewable LLM draft for the next Socratic question."""

    context = load_project(project_path)
    session_dir = context.sessions_dir / session_id
    transcript = (session_dir / "transcript.md").read_text(encoding="utf-8")
    summary = (session_dir / "summary.md").read_text(encoding="utf-8")
    misconceptions = (session_dir / "detected_misconceptions.md").read_text(encoding="utf-8")
    response = client.complete(
        LlmRequest(
            purpose="tutoring_next_question",
            messages=(
                LlmMessage(
                    role="system",
                    content=(
                        "Return one JSON object with keys question, reason, "
                        "expected_student_action. Ask a Socratic next question, "
                        "not a full solution."
                    ),
                ),
                LlmMessage(
                    role="user",
                    content=(
                        f"Transcript:\n{transcript}\n\n"
                        f"Summary:\n{summary}\n\n"
                        f"Detected misconceptions:\n{misconceptions}"
                    ),
                ),
            ),
            temperature=0.2,
        )
    )
    suggestion = _parse_next_question(response.content)
    artifact_path = session_dir / "llm_next_question.md"
    write_text(
        artifact_path,
        (
            "---\n"
            "status: draft\n"
            "created_by: socrates_llm\n"
            f"provider: {client.provider}\n"
            f"model: {client.model}\n"
            "---\n\n"
            "# LLM Next Question Draft\n\n"
            f"## Question\n\n{suggestion['question']}\n\n"
            f"## Reason\n\n{suggestion['reason']}\n\n"
            f"## Expected Student Action\n\n{suggestion['expected_student_action']}\n"
        ),
    )
    record_llm_suggestion(
        context.root,
        artifact_path=artifact_path,
        suggestion_type="tutoring_next_question",
        provider=client.provider,
        model=client.model,
        source_paths=[
            f"03_sessions/{session_id}/transcript.md",
            f"03_sessions/{session_id}/summary.md",
            f"03_sessions/{session_id}/detected_misconceptions.md",
        ],
        prompt_hash=sha256_text(transcript + summary + misconceptions),
    )
    return artifact_path


def _tutoring_quality_by_session(project_root: Path) -> dict[str, tuple[str | None, int | None]]:
    manifest_path = project_root / "08_evals" / "tutoring_quality_manifest.json"
    if not manifest_path.exists():
        return {}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    sessions = manifest.get("sessions", []) if isinstance(manifest, dict) else []
    if not isinstance(sessions, list):
        return {}

    quality_by_session: dict[str, tuple[str | None, int | None]] = {}
    for item in sessions:
        if not isinstance(item, dict):
            continue
        session_id = str(item.get("session_id", "")).strip()
        quality_status = str(item.get("status", "")).strip()
        if not session_id or not quality_status:
            continue
        score_value = item.get("total_score")
        quality_score = score_value if type(score_value) is int and 0 <= score_value <= 100 else None
        quality_by_session[session_id] = (quality_status, quality_score)
    return quality_by_session


def _parse_next_question(content: str) -> dict[str, str]:
    required = ("question", "reason", "expected_student_action")
    data = parse_json_object(content, required_keys=required)
    result = {key: str(data.get(key, "")).strip() for key in required}
    missing = [key for key, value in result.items() if not value]
    if missing:
        raise ValueError(f"LLM next-question suggestion missing fields: {', '.join(missing)}")
    return result


def _read_script(script_path: Path) -> _Script:
    fields: dict[str, list[str]] = {}
    for raw_line in script_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition(":")
        if not separator:
            raise ValueError(f"Invalid script line: {raw_line}")
        fields.setdefault(key.strip().lower(), []).append(value.strip())

    question = _first(fields, "question")
    if question is None:
        raise ValueError("Script must include a question.")

    return _Script(
        topic=_title(_first(fields, "topic") or "Untitled session"),
        goal=_first(fields, "goal") or "No goal recorded.",
        question=question,
        hints=tuple(fields.get("hint", ())),
        attempts=tuple(fields.get("attempt", ())),
        solution=_first(fields, "solution"),
        misconceptions=tuple(fields.get("misconception", ())),
        next_actions=tuple(fields.get("next", ())),
    )


def _transcript(session_id: str, script: _Script) -> str:
    lines = [
        f"# Tutoring Session: {session_id}",
        "",
        "## Topic",
        "",
        script.topic,
        "",
        "## Transcript",
        "",
        f"Tutor: {script.question}",
    ]
    lines.extend(f"Hint {index}: {hint}" for index, hint in enumerate(script.hints, start=1))

    if script.attempts:
        for attempt in script.attempts:
            lines.append(f"Student attempt: {attempt}")
        if script.solution:
            lines.append(f"Tutor follow-up: {script.solution}")
    elif script.solution:
        lines.append("Tutor follow-up: Full solution withheld until after a student attempt.")

    return "\n".join(lines) + "\n"


def _tutor_notes(script: _Script) -> str:
    lines = [
        "# Tutor Notes",
        "",
        f"Goal: {script.goal}",
        f"Question: {script.question}",
        f"Hint ladder length: {len(script.hints)}",
    ]
    return "\n".join(lines) + "\n"


def _summary(script: _Script) -> str:
    lines = ["# Summary", ""]
    if script.attempts:
        lines.append(f"Student made {len(script.attempts)} attempt(s).")
    else:
        lines.append("No student attempt recorded.")
    if script.misconceptions:
        lines.append(f"Detected {len(script.misconceptions)} misconception(s).")
    else:
        lines.append("No misconceptions recorded.")
    return "\n".join(lines) + "\n"


def _bullet_doc(title: str, items: tuple[str, ...], empty_text: str) -> str:
    lines = [f"# {title}", ""]
    if items:
        lines.extend(f"- {item}" for item in items)
    else:
        lines.append(empty_text)
    return "\n".join(lines) + "\n"


def _first(fields: dict[str, list[str]], key: str) -> str | None:
    values = fields.get(key)
    if not values:
        return None
    return values[0]


def _title(value: str) -> str:
    return value[:1].upper() + value[1:]
