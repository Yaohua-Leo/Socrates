"""DeepSeek chat-completions provider adapter."""

from __future__ import annotations

import json
from typing import Callable, Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .llm import LlmProviderError, LlmRequest, LlmResponse
from .llm_config import LlmConfig


HttpOpener = Callable[[Request, float], Any]


class DeepSeekClient:
    provider = "deepseek"

    def __init__(
        self,
        config: LlmConfig,
        *,
        opener: HttpOpener | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.config = config
        self.model = config.model
        self._opener = opener or urlopen
        self._timeout = timeout

    def complete(self, request: LlmRequest) -> LlmResponse:
        if not self.config.api_key_present:
            raise LlmProviderError("DEEPSEEK_API_KEY is required for DeepSeek calls")

        http_request = Request(
            f"{self.config.base_url}/chat/completions",
            data=json.dumps(self._payload(request)).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with self._opener(http_request, timeout=self._timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise LlmProviderError(self._http_error_message(exc)) from exc
        except URLError as exc:
            raise LlmProviderError(f"DeepSeek request failed: {_redact(str(exc), self.config.api_key)}") from exc
        except json.JSONDecodeError as exc:
            raise LlmProviderError("DeepSeek returned invalid JSON") from exc

        content = _response_content(payload)
        usage = payload.get("usage", {}) if isinstance(payload, dict) else {}
        return LlmResponse(
            content=content,
            provider=self.provider,
            model=self.model,
            raw_usage=usage if isinstance(usage, dict) else {},
        )

    def _payload(self, request: LlmRequest) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": self.model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in request.messages
            ],
            "thinking": {"type": "disabled"},
            "temperature": request.temperature,
            "stream": False,
        }
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        return payload

    def _http_error_message(self, exc: HTTPError) -> str:
        details = ""
        if exc.fp is not None:
            try:
                details = exc.fp.read().decode("utf-8", errors="replace")
            except OSError:
                details = ""
        raw = f"DeepSeek HTTP {exc.code}: {exc.reason}"
        if details:
            raw += f" - {details}"
        return _redact(raw, self.config.api_key)


def _response_content(payload: object) -> str:
    if not isinstance(payload, dict):
        raise LlmProviderError("DeepSeek response missing content")
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LlmProviderError("DeepSeek response missing content")
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise LlmProviderError("DeepSeek response missing content")
    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise LlmProviderError("DeepSeek response missing content")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise LlmProviderError("DeepSeek response missing content")
    return content


def _redact(value: str, secret: str) -> str:
    if secret:
        return value.replace(secret, "[redacted]")
    return value
