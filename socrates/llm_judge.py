"""Review-only LLM judge draft artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .context import load_project, write_text
from .llm import LlmClient, LlmMessage, LlmRequest, parse_json_object, sha256_text
from .llm_artifacts import record_llm_suggestion


SESSION_JUDGE_BOUNDARY = "review_only_llm_judge_draft"

_SESSION_SOURCE_FILES = (
    "transcript.md",
    "summary.md",
    "tutor_notes.md",
    "detected_misconceptions.md",
    "next_actions.md",
)


@dataclass(frozen=True)
class _JudgeSuggestion:
    summary: str
    rubric_findings: tuple[str, ...]
    risks: tuple[str, ...]
    recommended_human_checks: tuple[str, ...]
    confidence: str


def suggest_session_judge_with_llm(
    project_path: Path | str,
    session_id: str,
    *,
    client: LlmClient,
) -> Path:
    """Write a review-only LLM draft about one tutoring session."""

    context = load_project(project_path)
    session_dir = context.sessions_dir / session_id
    session_sources = _read_session_sources(session_dir)
    score_manifest_path = context.evals_dir / "session_score_manifest.json"
    score_manifest = (
        score_manifest_path.read_text(encoding="utf-8") if score_manifest_path.exists() else ""
    )
    response = client.complete(
        LlmRequest(
            purpose="session_quality_judge",
            messages=(
                LlmMessage(
                    role="system",
                    content=(
                        "Return one JSON object with keys summary, rubric_findings, "
                        "risks, recommended_human_checks, confidence. "
                        "rubric_findings, risks, and recommended_human_checks must be "
                        "non-empty arrays of strings. confidence must be low, medium, "
                        "or high. This is a human-review draft only, not a grade, "
                        "score, readiness gate, proof, or learning-state update."
                    ),
                ),
                LlmMessage(
                    role="user",
                    content=_judge_prompt(
                        session_id=session_id,
                        session_sources=session_sources,
                        score_manifest=score_manifest,
                    ),
                ),
            ),
            temperature=0.1,
        )
    )
    suggestion = _parse_judge_suggestion(response.content)
    artifact_path = session_dir / "llm_session_judge.md"
    write_text(
        artifact_path,
        _judge_artifact(
            session_id=session_id,
            suggestion=suggestion,
            provider=client.provider,
            model=client.model,
        ),
    )
    source_paths = [f"03_sessions/{session_id}/{name}" for name in _SESSION_SOURCE_FILES]
    prompt_parts = [session_sources[name] for name in _SESSION_SOURCE_FILES]
    if score_manifest:
        source_paths.append("08_evals/session_score_manifest.json")
        prompt_parts.append(score_manifest)
    record_llm_suggestion(
        context.root,
        artifact_path=artifact_path,
        suggestion_type="session_quality_judge",
        provider=client.provider,
        model=client.model,
        source_paths=source_paths,
        prompt_hash=sha256_text("\n\n".join(prompt_parts)),
    )
    return artifact_path


def _read_session_sources(session_dir: Path) -> dict[str, str]:
    sources: dict[str, str] = {}
    for filename in _SESSION_SOURCE_FILES:
        path = session_dir / filename
        sources[filename] = path.read_text(encoding="utf-8")
    return sources


def _judge_prompt(
    *,
    session_id: str,
    session_sources: dict[str, str],
    score_manifest: str,
) -> str:
    score_context = score_manifest or "No deterministic session score manifest is present."
    sections = [
        f"Session id: {session_id}",
        "Boundary: review-only draft; do not invent a grade or mutate learning state.",
        f"Deterministic session score manifest:\n{score_context}",
    ]
    sections.extend(
        f"{filename}:\n{session_sources[filename]}" for filename in _SESSION_SOURCE_FILES
    )
    return "\n\n".join(sections)


def _parse_judge_suggestion(content: str) -> _JudgeSuggestion:
    required = ("summary", "rubric_findings", "risks", "recommended_human_checks", "confidence")
    data = parse_json_object(content, required_keys=required)
    summary = str(data.get("summary", "")).strip()
    confidence = str(data.get("confidence", "")).strip().lower()
    suggestion = _JudgeSuggestion(
        summary=summary,
        rubric_findings=_string_list(data.get("rubric_findings"), "rubric_findings"),
        risks=_string_list(data.get("risks"), "risks"),
        recommended_human_checks=_string_list(
            data.get("recommended_human_checks"),
            "recommended_human_checks",
        ),
        confidence=confidence,
    )
    if not suggestion.summary:
        raise ValueError("LLM session judge suggestion missing summary")
    if suggestion.confidence not in {"low", "medium", "high"}:
        raise ValueError("LLM session judge confidence must be low, medium, or high")
    return suggestion


def _string_list(value: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"LLM session judge {field_name} must be a list")
    non_string_items = [item for item in value if not isinstance(item, str)]
    if non_string_items:
        raise ValueError(f"LLM session judge {field_name} must contain only strings")
    items = tuple(item.strip() for item in value if item.strip())
    if not items:
        raise ValueError(f"LLM session judge {field_name} must not be empty")
    return items


def _judge_artifact(
    *,
    session_id: str,
    suggestion: _JudgeSuggestion,
    provider: str,
    model: str,
) -> str:
    return (
        "---\n"
        "status: draft\n"
        "created_by: socrates_llm\n"
        f"provider: {provider}\n"
        f"model: {model}\n"
        f"session_id: {session_id}\n"
        f"quality_boundary: {SESSION_JUDGE_BOUNDARY}\n"
        "---\n\n"
        "# LLM Session Judge Draft\n\n"
        "## Boundary\n\n"
        "This draft is for human review only. It is not a deterministic score, "
        "grade, readiness gate, proof, or learning-state update.\n\n"
        "## Summary\n\n"
        f"{suggestion.summary}\n\n"
        "## Rubric Findings\n\n"
        f"{_bullet_list(suggestion.rubric_findings)}\n"
        "## Risks\n\n"
        f"{_bullet_list(suggestion.risks)}\n"
        "## Recommended Human Checks\n\n"
        f"{_bullet_list(suggestion.recommended_human_checks)}\n"
        "## Confidence\n\n"
        f"{suggestion.confidence}\n"
    )


def _bullet_list(items: tuple[str, ...]) -> str:
    return "\n".join(f"- {item}" for item in items) + "\n\n"
