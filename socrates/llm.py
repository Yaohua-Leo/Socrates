"""Provider-neutral LLM request and response contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Protocol


class LlmProviderError(RuntimeError):
    """Raised when the configured LLM provider cannot return a usable response."""


class LlmOutputValidationError(ValueError):
    """Raised when a provider response cannot be used as a draft suggestion."""


@dataclass(frozen=True)
class LlmMessage:
    role: str
    content: str


@dataclass(frozen=True)
class LlmRequest:
    purpose: str
    messages: tuple[LlmMessage, ...]
    temperature: float = 0.2
    max_tokens: int | None = None


@dataclass(frozen=True)
class LlmResponse:
    content: str
    provider: str
    model: str
    raw_usage: dict[str, object] = field(default_factory=dict)


class LlmClient(Protocol):
    provider: str
    model: str

    def complete(self, request: LlmRequest) -> LlmResponse:
        ...


class FakeLlmClient:
    provider = "fake"
    model = "fake-model"

    def __init__(self, responses: list[str] | tuple[str, ...]) -> None:
        self._responses = list(responses)
        self.requests: list[LlmRequest] = []

    def complete(self, request: LlmRequest) -> LlmResponse:
        self.requests.append(request)
        if not self._responses:
            raise LlmProviderError("fake LLM response queue is empty")
        return LlmResponse(
            content=self._responses.pop(0),
            provider=self.provider,
            model=self.model,
        )


def parse_json_object(content: str, *, required_keys: tuple[str, ...]) -> dict[str, object]:
    """Parse one JSON object and ensure required keys are present."""

    try:
        value = json.loads(content)
    except json.JSONDecodeError as exc:
        raise LlmOutputValidationError(f"LLM response is not valid JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise LlmOutputValidationError("LLM response must be a JSON object")
    missing = [key for key in required_keys if key not in value]
    if missing:
        raise LlmOutputValidationError(f"LLM response missing required keys: {', '.join(missing)}")
    return value


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
