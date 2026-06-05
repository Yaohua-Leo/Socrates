# Socrates v0.3 LLM Provider and Learning State Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a minimal, local-first LLM layer for Socrates v0.3, using Leo's local DeepSeek configuration for opt-in testing while keeping all LLM outputs as reviewed suggestions or drafts.

**Architecture:** Keep the v0.2 deterministic CLI baseline intact. Add a small stdlib-only LLM configuration loader, provider contract, DeepSeek adapter, and suggestion artifact manifest; then attach LLM generation only to patch-only reference cleanup, next-question tutoring suggestions, and exercise feedback proposals. Default checks must remain offline and deterministic; live DeepSeek calls are opt-in smoke tests.

**Tech Stack:** Python 3.11+, stdlib only, `unittest`, `argparse`, local `.env` config, DeepSeek chat-completions compatible HTTP API, existing Socrates CLI/filesystem artifacts.

---

## Current Baseline and Execution Contract

- Start from the v0.2 closure branch or its merged integration result. At plan-writing time the working branch is `codex/v02-closure`, with v0.2 closure commit `eaeef82`.
- Preserve the existing no-runtime-dependency policy in `pyproject.toml`.
- Do not commit `D:\Socrates\.env`; `.env` is ignored and may contain Leo's real DeepSeek key.
- Use the local test model from config: `DEEPSEEK_MODEL=deepseek-v4-pro`.
- Treat exact DeepSeek endpoint details as external documentation. Before implementing Task 3, verify the current official DeepSeek request/response shape, but keep the local model name from `.env` unless Leo changes it.
- Default gate commands must not require network access:
  - `powershell -ExecutionPolicy Bypass -File scripts\check.ps1`
  - `bash scripts/check.sh`
- Live LLM verification is separate and explicit:
  - PowerShell: `$env:SOCRATES_RUN_LIVE_LLM="1"; python -m unittest tests.test_deepseek_live_smoke`
  - CLI smoke: `python -m socrates llm smoke --prompt "Return exactly: socrates-ok"`

## Safety Rules for v0.3

- No API key may appear in stdout, stderr, test snapshots, markdown artifacts, JSON manifests, commit messages, or PR descriptions.
- LLM output must never directly overwrite curated references, reviewed Obsidian notes, graded attempts, or learning-state truth.
- LLM output may create only:
  - correction patch proposals that still require existing `patches review` and `patches apply`;
  - tutoring next-question draft artifacts;
  - exercise feedback draft artifacts;
  - manifest records that point to these artifacts.
- If provider config is missing, CLI commands should fail with an actionable error instead of falling back to hidden defaults.
- If live provider calls fail, report the HTTP/provider error without printing secrets.

## File Structure

- Create `socrates/llm_config.py`: loads `.env` plus process environment into a redacted `LlmConfig`.
- Create `socrates/llm.py`: provider-neutral request/response dataclasses, `LlmClient` protocol, `FakeLlmClient`, JSON helpers, and output validation errors.
- Create `socrates/deepseek.py`: DeepSeek HTTP adapter using stdlib `urllib.request`.
- Create `socrates/llm_artifacts.py`: records LLM suggestion artifacts in `08_evals/llm_suggestions_manifest.json`.
- Modify `socrates/cli.py`: add `llm config`, `llm smoke`, `patches suggest`, `session suggest-next`, and `exercise suggest-feedback` commands.
- Modify `socrates/references.py`: add LLM-assisted patch proposal generation that reuses existing patch-only workflow.
- Modify `socrates/tutoring.py`: add next-question suggestion artifact generation without changing `teach`.
- Modify `socrates/exercises.py`: add exercise feedback proposal generation without changing existing grading semantics.
- Modify `socrates/learning_queue.py`, `socrates/quality.py`, or `socrates/cli.py` status helpers only if needed to report pending LLM drafts conservatively.
- Modify `docs/README.md`, `README.md`, `docs/development_log.md`, and `docs/development_roadmap.md` after the implementation is verified.
- Create tests:
  - `tests/test_llm_config.py`
  - `tests/test_llm_provider_contract.py`
  - `tests/test_deepseek_provider.py`
  - `tests/test_deepseek_live_smoke.py`
  - `tests/test_llm_cli.py`
  - `tests/test_llm_reference_patch.py`
  - `tests/test_llm_tutoring_suggestions.py`
  - `tests/test_llm_exercise_feedback.py`
  - `tests/test_v03_llm_flow.py`

## Task 1: Local LLM Config Loader

**Files:**
- Create: `socrates/llm_config.py`
- Test: `tests/test_llm_config.py`
- Modify: `.env.example` only if the local model default has drifted from `deepseek-v4-pro`

- [ ] **Step 1: Write config tests**

Create `tests/test_llm_config.py` with tests equivalent to:

```python
import os
from pathlib import Path
import tempfile
import unittest

from socrates.llm_config import load_llm_config


class LlmConfigTests(unittest.TestCase):
    def test_loads_deepseek_config_from_dotenv_without_echoing_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".env").write_text(
                "SOCRATES_LLM_PROVIDER=deepseek\n"
                "DEEPSEEK_API_KEY=fake-secret-value\n"
                "DEEPSEEK_BASE_URL=https://api.deepseek.com\n"
                "DEEPSEEK_MODEL=deepseek-v4-pro\n",
                encoding="utf-8",
                newline="\n",
            )

            config = load_llm_config(root)

            self.assertEqual(config.provider, "deepseek")
            self.assertEqual(config.api_key, "fake-secret-value")
            self.assertEqual(config.base_url, "https://api.deepseek.com")
            self.assertEqual(config.model, "deepseek-v4-pro")
            self.assertTrue(config.api_key_present)
            self.assertNotIn("fake-secret-value", config.redacted_summary())

    def test_process_environment_overrides_dotenv(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".env").write_text(
                "SOCRATES_LLM_PROVIDER=deepseek\n"
                "DEEPSEEK_API_KEY=from-file\n"
                "DEEPSEEK_MODEL=deepseek-chat\n",
                encoding="utf-8",
                newline="\n",
            )
            previous = os.environ.get("DEEPSEEK_MODEL")
            os.environ["DEEPSEEK_MODEL"] = "deepseek-v4-pro"
            try:
                config = load_llm_config(root)
            finally:
                if previous is None:
                    os.environ.pop("DEEPSEEK_MODEL", None)
                else:
                    os.environ["DEEPSEEK_MODEL"] = previous

            self.assertEqual(config.model, "deepseek-v4-pro")

    def test_missing_key_is_reported_without_secret_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = load_llm_config(Path(temp_dir))

            self.assertEqual(config.provider, "deepseek")
            self.assertFalse(config.api_key_present)
            self.assertIn("api_key=missing", config.redacted_summary())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the failing config tests**

Run: `python -m unittest tests.test_llm_config`

Expected before implementation: fail because `socrates.llm_config` does not exist.

- [ ] **Step 3: Implement `socrates/llm_config.py`**

Use this public shape:

```python
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class LlmConfig:
    provider: str
    api_key: str
    base_url: str
    model: str

    @property
    def api_key_present(self) -> bool:
        return bool(self.api_key.strip())

    def redacted_summary(self) -> str:
        status = "present" if self.api_key_present else "missing"
        return (
            f"provider={self.provider}\n"
            f"model={self.model}\n"
            f"base_url={self.base_url}\n"
            f"api_key={status}\n"
        )


def load_llm_config(root: Path | str | None = None) -> LlmConfig:
    values = _read_dotenv(Path(root or Path.cwd()) / ".env")
    merged = {**values, **_selected_environment()}
    return LlmConfig(
        provider=merged.get("SOCRATES_LLM_PROVIDER", "deepseek").strip() or "deepseek",
        api_key=merged.get("DEEPSEEK_API_KEY", "").strip(),
        base_url=merged.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/"),
        model=merged.get("DEEPSEEK_MODEL", "deepseek-v4-pro").strip() or "deepseek-v4-pro",
    )


def _selected_environment() -> dict[str, str]:
    keys = {
        "SOCRATES_LLM_PROVIDER",
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_BASE_URL",
        "DEEPSEEK_MODEL",
    }
    return {key: value for key in keys if (value := os.environ.get(key)) is not None}


def _read_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values
```

- [ ] **Step 4: Run config tests and diff check**

Run:

```powershell
python -m unittest tests.test_llm_config
git diff --check
```

Expected: tests pass; no whitespace errors.

- [ ] **Step 5: Commit Task 1**

Use a Lore-style commit message. Example intent line:

```text
Load local LLM config without exposing provider secrets
```

## Task 2: Provider Contract, Fake Client, and LLM Suggestion Manifest

**Files:**
- Create: `socrates/llm.py`
- Create: `socrates/llm_artifacts.py`
- Test: `tests/test_llm_provider_contract.py`

- [ ] **Step 1: Write provider and manifest tests**

Create `tests/test_llm_provider_contract.py` with tests equivalent to:

```python
from pathlib import Path
import json
import tempfile
import unittest

from socrates.llm import FakeLlmClient, LlmMessage, LlmRequest
from socrates.llm_artifacts import record_llm_suggestion, list_llm_suggestions


class LlmProviderContractTests(unittest.TestCase):
    def test_fake_client_returns_scripted_response_and_records_request(self) -> None:
        client = FakeLlmClient(["{\"answer\": \"ok\"}"])
        response = client.complete(
            LlmRequest(
                purpose="smoke",
                messages=(LlmMessage(role="user", content="Say ok"),),
                temperature=0.0,
            )
        )

        self.assertEqual(response.content, "{\"answer\": \"ok\"}")
        self.assertEqual(response.provider, "fake")
        self.assertEqual(response.model, "fake-model")
        self.assertEqual(len(client.requests), 1)

    def test_manifest_records_redacted_llm_suggestion_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            (project / "project.yaml").write_text("project: {}\n", encoding="utf-8")
            artifact = project / "03_sessions" / "s1" / "llm_next_question.md"
            artifact.parent.mkdir(parents=True)
            artifact.write_text("# Draft\n", encoding="utf-8", newline="\n")

            record_llm_suggestion(
                project,
                artifact_path=artifact,
                suggestion_type="tutoring_next_question",
                provider="deepseek",
                model="deepseek-v4-pro",
                source_paths=["03_sessions/s1/transcript.md"],
                prompt_hash="abc123",
            )

            records = list_llm_suggestions(project)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].suggestion_type, "tutoring_next_question")
            manifest = json.loads(
                (project / "08_evals" / "llm_suggestions_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertNotIn("DEEPSEEK_API_KEY", json.dumps(manifest))
            self.assertNotIn("real-secret", json.dumps(manifest))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the failing provider tests**

Run: `python -m unittest tests.test_llm_provider_contract`

Expected before implementation: fail because `socrates.llm` and `socrates.llm_artifacts` do not exist.

- [ ] **Step 3: Implement `socrates/llm.py`**

Use these public dataclasses and protocol:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class LlmProviderError(RuntimeError):
    """Raised when the configured LLM provider cannot return a usable response."""


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
```

- [ ] **Step 4: Implement `socrates/llm_artifacts.py`**

Use a stable manifest schema:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

from socrates.context import write_json


MANIFEST_PATH = Path("08_evals") / "llm_suggestions_manifest.json"


@dataclass(frozen=True)
class LlmSuggestionSummary:
    suggestion_id: str
    suggestion_type: str
    status: str
    artifact_path: str
    provider: str
    model: str


def record_llm_suggestion(
    project_path: Path | str,
    *,
    artifact_path: Path,
    suggestion_type: str,
    provider: str,
    model: str,
    source_paths: list[str],
    prompt_hash: str,
) -> None:
    project = Path(project_path).resolve()
    manifest_path = project / MANIFEST_PATH
    manifest = _read_manifest(manifest_path)
    relative_artifact = artifact_path.resolve().relative_to(project).as_posix()
    record = {
        "suggestion_id": Path(relative_artifact).stem,
        "suggestion_type": suggestion_type,
        "status": "draft",
        "artifact_path": relative_artifact,
        "provider": provider,
        "model": model,
        "source_paths": list(source_paths),
        "prompt_hash": prompt_hash,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    manifest["records"].append(record)
    write_json(manifest_path, manifest)


def list_llm_suggestions(project_path: Path | str) -> list[LlmSuggestionSummary]:
    manifest = _read_manifest(Path(project_path).resolve() / MANIFEST_PATH)
    return [
        LlmSuggestionSummary(
            suggestion_id=str(item.get("suggestion_id", "")),
            suggestion_type=str(item.get("suggestion_type", "")),
            status=str(item.get("status", "draft")),
            artifact_path=str(item.get("artifact_path", "")),
            provider=str(item.get("provider", "")),
            model=str(item.get("model", "")),
        )
        for item in manifest.get("records", [])
        if isinstance(item, dict)
    ]


def _read_manifest(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"schema_version": 1, "records": []}
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or not isinstance(manifest.get("records"), list):
        raise ValueError("invalid llm_suggestions_manifest.json")
    return manifest
```

- [ ] **Step 5: Run provider tests**

Run:

```powershell
python -m unittest tests.test_llm_provider_contract
git diff --check
```

Expected: tests pass; no whitespace errors.

- [ ] **Step 6: Commit Task 2**

Use a Lore-style commit message. Example intent line:

```text
Define LLM suggestions as reviewable project artifacts
```

## Task 3: DeepSeek Provider Adapter

**Files:**
- Create: `socrates/deepseek.py`
- Test: `tests/test_deepseek_provider.py`
- Test: `tests/test_deepseek_live_smoke.py`

- [ ] **Step 1: Verify current DeepSeek HTTP contract**

Check official DeepSeek API documentation for:

```text
POST {base_url}/chat/completions
Authorization: Bearer <DEEPSEEK_API_KEY>
request.model = deepseek-v4-pro
request.messages = [{"role": "user", "content": "..."}]
response.choices[0].message.content
```

If only field names or endpoint paths differ, update the adapter and tests in this task. Do not add a third-party SDK unless Leo explicitly asks for it.

- [ ] **Step 2: Write adapter unit tests with a fake HTTP opener**

Create `tests/test_deepseek_provider.py` with tests equivalent to:

```python
from io import BytesIO
import json
import unittest

from socrates.deepseek import DeepSeekClient
from socrates.llm import LlmMessage, LlmProviderError, LlmRequest
from socrates.llm_config import LlmConfig


class FakeHttpResponse:
    def __init__(self, payload: dict[str, object], status: int = 200) -> None:
        self.payload = payload
        self.status = status

    def __enter__(self) -> "FakeHttpResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class DeepSeekProviderTests(unittest.TestCase):
    def test_posts_chat_completion_request_without_leaking_key(self) -> None:
        captured = {}

        def opener(request, timeout=0):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return FakeHttpResponse(
                {"choices": [{"message": {"content": "socrates-ok"}}], "usage": {"total_tokens": 4}}
            )

        client = DeepSeekClient(
            LlmConfig(
                provider="deepseek",
                api_key="fake-secret-value",
                base_url="https://api.deepseek.com",
                model="deepseek-v4-pro",
            ),
            opener=opener,
        )
        response = client.complete(
            LlmRequest(
                purpose="smoke",
                messages=(LlmMessage(role="user", content="Return ok"),),
            )
        )

        self.assertEqual(response.content, "socrates-ok")
        self.assertEqual(response.model, "deepseek-v4-pro")
        self.assertEqual(captured["body"]["model"], "deepseek-v4-pro")
        self.assertIn("Bearer fake-secret-value", captured["headers"].values())

    def test_missing_key_fails_before_network_call(self) -> None:
        calls = []
        client = DeepSeekClient(
            LlmConfig(
                provider="deepseek",
                api_key="",
                base_url="https://api.deepseek.com",
                model="deepseek-v4-pro",
            ),
            opener=lambda request, timeout=0: calls.append(request),
        )

        with self.assertRaisesRegex(LlmProviderError, "DEEPSEEK_API_KEY"):
            client.complete(
                LlmRequest(
                    purpose="smoke",
                    messages=(LlmMessage(role="user", content="Return ok"),),
                )
            )
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Implement `socrates/deepseek.py`**

Use stdlib HTTP and keep the opener injectable:

```python
from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from socrates.llm import LlmProviderError, LlmRequest, LlmResponse
from socrates.llm_config import LlmConfig


class DeepSeekClient:
    provider = "deepseek"

    def __init__(self, config: LlmConfig, *, opener=urlopen, timeout: float = 30.0) -> None:
        self._config = config
        self._opener = opener
        self._timeout = timeout
        self.model = config.model

    def complete(self, request: LlmRequest) -> LlmResponse:
        if not self._config.api_key_present:
            raise LlmProviderError("DEEPSEEK_API_KEY is missing")
        payload: dict[str, object] = {
            "model": self._config.model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in request.messages
            ],
            "temperature": request.temperature,
            "stream": False,
        }
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        http_request = Request(
            f"{self._config.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with self._opener(http_request, timeout=self._timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise LlmProviderError(f"DeepSeek HTTP error {exc.code}") from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise LlmProviderError(f"DeepSeek request failed: {exc}") from exc

        content = _choice_content(data)
        return LlmResponse(
            content=content,
            provider=self.provider,
            model=self._config.model,
            raw_usage=data.get("usage", {}) if isinstance(data, dict) else {},
        )


def _choice_content(data: object) -> str:
    if not isinstance(data, dict):
        raise LlmProviderError("DeepSeek response was not a JSON object")
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LlmProviderError("DeepSeek response did not include choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise LlmProviderError("DeepSeek response choice was invalid")
    message = first.get("message")
    if not isinstance(message, dict):
        raise LlmProviderError("DeepSeek response choice did not include a message")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise LlmProviderError("DeepSeek response content was empty")
    return content
```

- [ ] **Step 4: Add opt-in live smoke test**

Create `tests/test_deepseek_live_smoke.py`:

```python
import os
from pathlib import Path
import unittest

from socrates.deepseek import DeepSeekClient
from socrates.llm import LlmMessage, LlmRequest
from socrates.llm_config import load_llm_config


@unittest.skipUnless(
    os.environ.get("SOCRATES_RUN_LIVE_LLM") == "1",
    "set SOCRATES_RUN_LIVE_LLM=1 to call the live DeepSeek provider",
)
class DeepSeekLiveSmokeTests(unittest.TestCase):
    def test_live_deepseek_returns_short_response(self) -> None:
        config = load_llm_config(Path.cwd())
        self.assertTrue(config.api_key_present, "DEEPSEEK_API_KEY must be present in .env")
        client = DeepSeekClient(config)
        response = client.complete(
            LlmRequest(
                purpose="live_smoke",
                messages=(
                    LlmMessage(
                        role="user",
                        content="Return exactly this token and nothing else: socrates-ok",
                    ),
                ),
                temperature=0.0,
                max_tokens=16,
            )
        )

        self.assertIn("socrates-ok", response.content.lower())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 5: Run adapter tests**

Run:

```powershell
python -m unittest tests.test_deepseek_provider
python -m unittest tests.test_deepseek_live_smoke
git diff --check
```

Expected: adapter tests pass; live smoke is skipped unless `SOCRATES_RUN_LIVE_LLM=1`.

- [ ] **Step 6: Run Leo's live DeepSeek smoke test**

Run only on Leo's local machine with `.env` present:

```powershell
$env:SOCRATES_RUN_LIVE_LLM="1"
python -m unittest tests.test_deepseek_live_smoke
Remove-Item Env:\SOCRATES_RUN_LIVE_LLM
```

Expected: one live test passes. If it fails because DeepSeek changed the endpoint or model name, update only `socrates/deepseek.py`, `.env.example`, and the adapter tests in this task.

- [ ] **Step 7: Commit Task 3**

Use a Lore-style commit message. Example intent line:

```text
Connect DeepSeek through a stdlib-only provider adapter
```

## Task 4: LLM CLI Visibility and Smoke Command

**Files:**
- Modify: `socrates/cli.py`
- Test: `tests/test_llm_cli.py`

- [ ] **Step 1: Write CLI tests**

Create `tests/test_llm_cli.py` with tests equivalent to:

```python
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]


class LlmCliTests(unittest.TestCase):
    def test_llm_config_redacts_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".env").write_text(
                "SOCRATES_LLM_PROVIDER=deepseek\n"
                "DEEPSEEK_API_KEY=fake-secret-value\n"
                "DEEPSEEK_BASE_URL=https://api.deepseek.com\n"
                "DEEPSEEK_MODEL=deepseek-v4-pro\n",
                encoding="utf-8",
                newline="\n",
            )

            result = subprocess.run(
                [sys.executable, "-m", "socrates", "llm", "config", "--root", str(root)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("provider=deepseek", result.stdout)
            self.assertIn("model=deepseek-v4-pro", result.stdout)
            self.assertIn("api_key=present", result.stdout)
            self.assertNotIn("fake-secret-value", result.stdout)

    def test_llm_smoke_without_key_fails_before_provider_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socrates",
                    "llm",
                    "smoke",
                    "--root",
                    temp_dir,
                    "--prompt",
                    "Return ok",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("DEEPSEEK_API_KEY is missing", result.stderr)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run failing CLI tests**

Run: `python -m unittest tests.test_llm_cli`

Expected before implementation: fail because `llm` command does not exist.

- [ ] **Step 3: Add CLI parser and handlers**

In `build_parser()` add:

```python
    llm_parser = subparsers.add_parser(
        "llm",
        help="Inspect and smoke-test the configured local LLM provider.",
    )
    llm_subparsers = llm_parser.add_subparsers(dest="llm_command", required=True)
    llm_config_parser = llm_subparsers.add_parser(
        "config",
        help="Print redacted LLM provider configuration.",
    )
    llm_config_parser.add_argument("--root", default=".", help="Directory containing .env.")
    llm_config_parser.set_defaults(func=_handle_llm_config)
    llm_smoke_parser = llm_subparsers.add_parser(
        "smoke",
        help="Call the configured LLM provider with a short prompt.",
    )
    llm_smoke_parser.add_argument("--root", default=".", help="Directory containing .env.")
    llm_smoke_parser.add_argument("--prompt", required=True, help="Short smoke-test prompt.")
    llm_smoke_parser.set_defaults(func=_handle_llm_smoke)
```

Add imports:

```python
from .deepseek import DeepSeekClient
from .llm import LlmMessage, LlmProviderError, LlmRequest
from .llm_config import load_llm_config
```

Add handlers:

```python
def _handle_llm_config(args: argparse.Namespace) -> int:
    config = load_llm_config(Path(args.root))
    print(config.redacted_summary(), end="")
    return 0


def _handle_llm_smoke(args: argparse.Namespace) -> int:
    config = load_llm_config(Path(args.root))
    client = DeepSeekClient(config)
    try:
        response = client.complete(
            LlmRequest(
                purpose="cli_smoke",
                messages=(LlmMessage(role="user", content=args.prompt),),
                temperature=0.0,
                max_tokens=64,
            )
        )
    except LlmProviderError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(response.content)
    return 0
```

- [ ] **Step 4: Run CLI tests and local config command**

Run:

```powershell
python -m unittest tests.test_llm_cli
python -m socrates llm config --root .
git diff --check
```

Expected: tests pass; config command prints `api_key=present` locally without printing the key.

- [ ] **Step 5: Run optional CLI live smoke**

Run on Leo's machine:

```powershell
python -m socrates llm smoke --root . --prompt "Return exactly: socrates-ok"
```

Expected: command exits 0 and includes `socrates-ok` or an obvious equivalent. Do not store the raw response in committed files.

- [ ] **Step 6: Commit Task 4**

Use a Lore-style commit message. Example intent line:

```text
Expose LLM readiness without leaking local credentials
```

## Task 5: Patch-Only Reference Cleanup Suggestions

**Files:**
- Modify: `socrates/references.py`
- Modify: `socrates/cli.py`
- Test: `tests/test_llm_reference_patch.py`

- [ ] **Step 1: Write reference patch suggestion tests**

Create `tests/test_llm_reference_patch.py` with tests equivalent to:

```python
from pathlib import Path
import tempfile
import unittest

from socrates.llm import FakeLlmClient
from socrates.project import ProjectSpec, create_project
from socrates.references import (
    curate_reference,
    import_reference,
    suggest_correction_patch_with_llm,
)


class LlmReferencePatchTests(unittest.TestCase):
    def test_llm_suggestion_creates_pending_patch_only_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "group_theory"
            create_project(ProjectSpec(topic="Group Theory", path=project))
            source = root / "normality.md"
            source.write_text(
                "### Definition: Normal Subgroup\n"
                "A normal subgroup is a subgroup where every element commutes.\n",
                encoding="utf-8",
                newline="\n",
            )
            import_reference(project, source, role="lecture_notes", title="Normality")
            curate_reference(project, "normality")
            client = FakeLlmClient(
                [
                    "{"
                    "\"location\":\"Definition: Normal Subgroup\","
                    "\"original\":\"A normal subgroup is a subgroup where every element commutes.\","
                    "\"proposed_correction\":\"A normal subgroup is stable under conjugation by every group element.\","
                    "\"reason\":\"Normality is about conjugation invariance, not commutativity.\","
                    "\"risk_level\":\"medium\""
                    "}"
                ]
            )

            patch_path = suggest_correction_patch_with_llm(
                project,
                "normality",
                client=client,
                location_hint="Definition: Normal Subgroup",
            )

            text = patch_path.read_text(encoding="utf-8")
            curated = (project / "01_references" / "curated" / "normality.curated.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("review_status: pending", text)
            self.assertIn("stable under conjugation", text)
            self.assertIn("A normal subgroup is a subgroup where every element commutes.", curated)
            self.assertTrue((project / "08_evals" / "llm_suggestions_manifest.json").exists())

    def test_rejects_suggestion_when_original_text_is_not_in_curated_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "group_theory"
            create_project(ProjectSpec(topic="Group Theory", path=project))
            source = root / "normality.md"
            source.write_text("### Definition: Normal Subgroup\nCorrect text.\n", encoding="utf-8")
            import_reference(project, source, role="lecture_notes", title="Normality")
            curate_reference(project, "normality")
            client = FakeLlmClient(
                [
                    "{"
                    "\"location\":\"Definition\","
                    "\"original\":\"not present\","
                    "\"proposed_correction\":\"replacement\","
                    "\"reason\":\"bad span\","
                    "\"risk_level\":\"low\""
                    "}"
                ]
            )

            with self.assertRaisesRegex(ValueError, "original text was not found"):
                suggest_correction_patch_with_llm(project, "normality", client=client)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run failing reference patch tests**

Run: `python -m unittest tests.test_llm_reference_patch`

Expected before implementation: fail because `suggest_correction_patch_with_llm` does not exist.

- [ ] **Step 3: Implement `suggest_correction_patch_with_llm`**

Add this public shape to `socrates/references.py`:

```python
def suggest_correction_patch_with_llm(
    project_path: Path | str,
    source_id: str,
    *,
    client: LlmClient,
    location_hint: str = "",
) -> Path:
    context = load_project(project_path)
    registry_text = context.source_registry.read_text(encoding="utf-8")
    record = _find_registry_record(registry_text, source_id)
    if record is None:
        raise ValueError(f"Unknown source id: {source_id}")
    curated_relative = str(record.get("processed_paths", {}).get("curated") or "")
    if not curated_relative:
        raise ValueError(f"Reference {source_id} does not have a curated markdown path")
    curated_path = context.root / curated_relative
    curated_text = curated_path.read_text(encoding="utf-8")
    response = client.complete(
        LlmRequest(
            purpose="reference_patch_suggestion",
            messages=(
                LlmMessage(
                    role="system",
                    content=(
                        "Return one JSON object with keys location, original, "
                        "proposed_correction, reason, risk_level. "
                        "The original value must be an exact span from the curated reference."
                    ),
                ),
                LlmMessage(
                    role="user",
                    content=(
                        f"Source id: {source_id}\n"
                        f"Location hint: {location_hint}\n\n"
                        f"Curated reference:\n{curated_text[:12000]}"
                    ),
                ),
            ),
            temperature=0.1,
        )
    )
    suggestion = _parse_patch_suggestion(response.content)
    if suggestion["original"] not in curated_text:
        raise ValueError("LLM suggested original text was not found in the curated reference")
    patch_path = create_correction_patch(
        context.root,
        source_id,
        location=suggestion["location"],
        original=suggestion["original"],
        proposed_correction=suggestion["proposed_correction"],
        reason=suggestion["reason"],
        risk_level=suggestion["risk_level"],
    )
    record_llm_suggestion(
        context.root,
        artifact_path=patch_path,
        suggestion_type="reference_correction_patch",
        provider=client.provider,
        model=client.model,
        source_paths=[curated_relative],
        prompt_hash=_sha256_text(curated_text + location_hint),
    )
    return patch_path
```

Add helpers in the same file or move to `socrates/llm.py` if reused:

```python
def _parse_patch_suggestion(content: str) -> dict[str, str]:
    data = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError("LLM patch suggestion must be a JSON object")
    required = ("location", "original", "proposed_correction", "reason", "risk_level")
    result = {key: str(data.get(key, "")).strip() for key in required}
    missing = [key for key, value in result.items() if not value]
    if missing:
        raise ValueError(f"LLM patch suggestion missing fields: {', '.join(missing)}")
    if result["risk_level"] not in {"low", "medium", "high"}:
        raise ValueError("LLM patch suggestion risk_level must be low, medium, or high")
    return result
```

- [ ] **Step 4: Add CLI command under `patches suggest`**

In `build_parser()` add to `patches_subparsers`:

```python
    patches_suggest_parser = patches_subparsers.add_parser(
        "suggest",
        help="Ask the configured LLM for one patch-only reference correction proposal.",
    )
    patches_suggest_parser.add_argument("--project", required=True, help="Socrates project directory.")
    patches_suggest_parser.add_argument("--source-id", required=True, help="Reference source id.")
    patches_suggest_parser.add_argument(
        "--location-hint",
        default="",
        help="Optional section or line hint to focus the LLM review.",
    )
    patches_suggest_parser.set_defaults(func=_handle_patches_suggest)
```

Add handler:

```python
def _handle_patches_suggest(args: argparse.Namespace) -> int:
    config = load_llm_config(Path.cwd())
    client = DeepSeekClient(config)
    try:
        patch = suggest_correction_patch_with_llm(
            args.project,
            args.source_id,
            client=client,
            location_hint=args.location_hint,
        )
    except (LlmProviderError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote LLM correction patch for {args.source_id}: {patch}")
    return 0
```

- [ ] **Step 5: Run tests and optional local CLI**

Run:

```powershell
python -m unittest tests.test_llm_reference_patch
python -m unittest tests.test_llm_cli
git diff --check
```

Optional live command on a throwaway Socrates project:

```powershell
python -m socrates patches suggest --project <project-path> --source-id <source-id> --location-hint "Definition"
```

Expected: a pending patch appears under `01_references/converted/patches/`; the curated file is unchanged.

- [ ] **Step 6: Commit Task 5**

Use a Lore-style commit message. Example intent line:

```text
Limit LLM reference cleanup to reviewable patch proposals
```

## Task 6: Tutoring Next-Question Suggestions

**Files:**
- Modify: `socrates/tutoring.py`
- Modify: `socrates/cli.py`
- Test: `tests/test_llm_tutoring_suggestions.py`

- [ ] **Step 1: Write tutoring suggestion tests**

Create `tests/test_llm_tutoring_suggestions.py` with tests equivalent to:

```python
from pathlib import Path
import tempfile
import unittest

from socrates.llm import FakeLlmClient
from socrates.project import ProjectSpec, create_project
from socrates.tutoring import run_scripted_tutoring_session, suggest_next_question_with_llm


class LlmTutoringSuggestionTests(unittest.TestCase):
    def test_next_question_suggestion_writes_draft_without_mutating_transcript(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "group_theory"
            create_project(ProjectSpec(topic="Group Theory", path=project))
            script = root / "session.script"
            script.write_text(
                "topic: Normal Subgroup\n"
                "question: What does normality require?\n"
                "attempt: It means abelian.\n"
                "misconception: normal_equals_abelian\n",
                encoding="utf-8",
                newline="\n",
            )
            run_scripted_tutoring_session(project, script, session_id="session_0001")
            transcript_before = (
                project / "03_sessions" / "session_0001" / "transcript.md"
            ).read_text(encoding="utf-8")
            client = FakeLlmClient(
                [
                    "{"
                    "\"question\":\"Can you test normality using conjugation by an arbitrary group element?\","
                    "\"reason\":\"Targets the active normal_equals_abelian misconception.\","
                    "\"expected_student_action\":\"Compare commutativity with conjugation invariance.\""
                    "}"
                ]
            )

            artifact = suggest_next_question_with_llm(project, "session_0001", client=client)

            self.assertTrue(artifact.exists())
            text = artifact.read_text(encoding="utf-8")
            self.assertIn("status: draft", text)
            self.assertIn("conjugation", text)
            self.assertEqual(
                transcript_before,
                (project / "03_sessions" / "session_0001" / "transcript.md").read_text(
                    encoding="utf-8"
                ),
            )
            self.assertTrue((project / "08_evals" / "llm_suggestions_manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run failing tutoring suggestion tests**

Run: `python -m unittest tests.test_llm_tutoring_suggestions`

Expected before implementation: fail because `suggest_next_question_with_llm` does not exist.

- [ ] **Step 3: Implement `suggest_next_question_with_llm`**

Add to `socrates/tutoring.py`:

```python
def suggest_next_question_with_llm(
    project_path: Path | str,
    session_id: str,
    *,
    client: LlmClient,
) -> Path:
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
        prompt_hash=_sha256_text(transcript + summary + misconceptions),
    )
    return artifact_path
```

Add `_parse_next_question` with required non-empty keys `question`, `reason`, and `expected_student_action`.

- [ ] **Step 4: Add CLI command under `session suggest-next`**

In `build_parser()` add to `session_subparsers`:

```python
    session_suggest_parser = session_subparsers.add_parser(
        "suggest-next",
        help="Ask the configured LLM for a draft next Socratic question.",
    )
    session_suggest_parser.add_argument("--project", required=True, help="Socrates project directory.")
    session_suggest_parser.add_argument("--session-id", required=True, help="Tutoring session id.")
    session_suggest_parser.set_defaults(func=_handle_session_suggest_next)
```

Add handler:

```python
def _handle_session_suggest_next(args: argparse.Namespace) -> int:
    config = load_llm_config(Path.cwd())
    client = DeepSeekClient(config)
    try:
        artifact = suggest_next_question_with_llm(
            args.project,
            args.session_id,
            client=client,
        )
    except (OSError, ValueError, LlmProviderError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote LLM next-question draft: {artifact}")
    return 0
```

- [ ] **Step 5: Run tests**

Run:

```powershell
python -m unittest tests.test_llm_tutoring_suggestions
python -m unittest tests.test_llm_cli
git diff --check
```

Expected: tests pass; no existing `teach` behavior changes.

- [ ] **Step 6: Commit Task 6**

Use a Lore-style commit message. Example intent line:

```text
Keep LLM tutoring help as draft next-question artifacts
```

## Task 7: Exercise Feedback and Misconception Proposals

**Files:**
- Modify: `socrates/exercises.py`
- Modify: `socrates/cli.py`
- Test: `tests/test_llm_exercise_feedback.py`

- [ ] **Step 1: Write exercise feedback tests**

Create `tests/test_llm_exercise_feedback.py` with tests equivalent to:

```python
from pathlib import Path
import tempfile
import unittest

from socrates.exercises import approve_exercise_draft, record_exercise_attempt, suggest_exercise_feedback_with_llm
from socrates.llm import FakeLlmClient
from socrates.project import ProjectSpec, create_project
from socrates.artifacts import generate_exercise_drafts


class LlmExerciseFeedbackTests(unittest.TestCase):
    def test_feedback_suggestion_does_not_grade_or_update_learning_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "group_theory"
            create_project(ProjectSpec(topic="Group Theory", path=project))
            draft = generate_exercise_drafts(
                project,
                concept="Normal Subgroup",
                source_id="manual",
                count=5,
            )[0]
            approve_exercise_draft(project, draft.id)
            answer = root / "answer.md"
            answer.write_text("I think normal just means abelian.", encoding="utf-8")
            attempt = record_exercise_attempt(project, draft.id, answer)
            learning_state_before = (project / "00_meta" / "learning_state.json").read_text(
                encoding="utf-8"
            )
            client = FakeLlmClient(
                [
                    "{"
                    "\"score_suggestion\":0.2,"
                    "\"misconception_id\":\"normal_equals_abelian\","
                    "\"analysis\":\"The answer confuses normality with commutativity.\","
                    "\"repair_suggestion\":\"Ask for conjugation invariance.\","
                    "\"follow_up_prompt\":\"Test gng^-1 for an arbitrary g.\""
                    "}"
                ]
            )

            artifact = suggest_exercise_feedback_with_llm(project, attempt.id, client=client)

            self.assertTrue(artifact.exists())
            text = artifact.read_text(encoding="utf-8")
            self.assertIn("status: draft", text)
            self.assertIn("normal_equals_abelian", text)
            self.assertEqual(
                learning_state_before,
                (project / "00_meta" / "learning_state.json").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run failing exercise feedback tests**

Run: `python -m unittest tests.test_llm_exercise_feedback`

Expected before implementation: fail because `suggest_exercise_feedback_with_llm` does not exist.

- [ ] **Step 3: Implement `suggest_exercise_feedback_with_llm`**

Use existing attempt and exercise file locations in `socrates/exercises.py`; add a public function:

```python
def suggest_exercise_feedback_with_llm(
    project_path: Path | str,
    attempt_id: str,
    *,
    client: LlmClient,
) -> Path:
    context = load_project(project_path)
    attempt_path = context.root / "05_exercises" / "attempted" / f"{attempt_id}.md"
    if not attempt_path.exists():
        raise FileNotFoundError(f"Exercise attempt does not exist: {attempt_path}")
    attempt_text = attempt_path.read_text(encoding="utf-8")
    response = client.complete(
        LlmRequest(
            purpose="exercise_feedback_suggestion",
            messages=(
                LlmMessage(
                    role="system",
                    content=(
                        "Return one JSON object with keys score_suggestion, "
                        "misconception_id, analysis, repair_suggestion, follow_up_prompt. "
                        "This is a draft for human review, not a grade."
                    ),
                ),
                LlmMessage(role="user", content=f"Exercise attempt:\n{attempt_text}"),
            ),
            temperature=0.1,
        )
    )
    suggestion = _parse_feedback_suggestion(response.content)
    artifact_path = context.root / "05_exercises" / "attempted" / f"{attempt_id}_llm_feedback.md"
    write_text(
        artifact_path,
        (
            "---\n"
            "status: draft\n"
            "created_by: socrates_llm\n"
            f"provider: {client.provider}\n"
            f"model: {client.model}\n"
            f"attempt_id: {attempt_id}\n"
            "---\n\n"
            "# LLM Exercise Feedback Draft\n\n"
            f"Score suggestion: {suggestion['score_suggestion']}\n\n"
            f"Misconception: {suggestion['misconception_id']}\n\n"
            f"Analysis: {suggestion['analysis']}\n\n"
            f"Repair suggestion: {suggestion['repair_suggestion']}\n\n"
            f"Follow-up prompt: {suggestion['follow_up_prompt']}\n"
        ),
    )
    record_llm_suggestion(
        context.root,
        artifact_path=artifact_path,
        suggestion_type="exercise_feedback",
        provider=client.provider,
        model=client.model,
        source_paths=[f"05_exercises/attempted/{attempt_id}.md"],
        prompt_hash=_sha256_text(attempt_text),
    )
    return artifact_path
```

Validation rules for `_parse_feedback_suggestion`:

```text
score_suggestion must parse as float and satisfy 0 <= score <= 1
misconception_id, analysis, repair_suggestion, follow_up_prompt must be non-empty strings
the function returns string values for markdown rendering
```

- [ ] **Step 4: Add CLI command under `exercise suggest-feedback`**

In `build_parser()` add to `exercise_subparsers`:

```python
    exercise_suggest_feedback_parser = exercise_subparsers.add_parser(
        "suggest-feedback",
        help="Ask the configured LLM for draft feedback on one exercise attempt.",
    )
    exercise_suggest_feedback_parser.add_argument("--project", required=True, help="Socrates project directory.")
    exercise_suggest_feedback_parser.add_argument("--attempt", required=True, help="Attempt id, without .md.")
    exercise_suggest_feedback_parser.set_defaults(func=_handle_exercise_suggest_feedback)
```

Add handler:

```python
def _handle_exercise_suggest_feedback(args: argparse.Namespace) -> int:
    config = load_llm_config(Path.cwd())
    client = DeepSeekClient(config)
    try:
        artifact = suggest_exercise_feedback_with_llm(
            args.project,
            args.attempt,
            client=client,
        )
    except (OSError, ValueError, LlmProviderError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote LLM exercise-feedback draft: {artifact}")
    return 0
```

- [ ] **Step 5: Run tests**

Run:

```powershell
python -m unittest tests.test_llm_exercise_feedback
python -m unittest tests.test_llm_cli
git diff --check
```

Expected: tests pass; existing `exercise grade` remains the only command that mutates learning state from an attempt.

- [ ] **Step 6: Commit Task 7**

Use a Lore-style commit message. Example intent line:

```text
Separate LLM feedback proposals from learner state mutation
```

## Task 8: Status, Lifecycle, and v0.3 End-to-End Regression

**Files:**
- Modify: `socrates/cli.py`
- Modify: `socrates/learning_queue.py` or lifecycle helpers only if the current status code already has a better local home
- Test: `tests/test_v03_llm_flow.py`
- Test: update `tests/test_status_quality_summary.py` or `tests/test_lifecycle_audit.py` if status/audit output changes

- [ ] **Step 1: Write v0.3 end-to-end regression with fake LLM**

Create `tests/test_v03_llm_flow.py` with a deterministic fake-provider flow:

```python
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from socrates.llm import FakeLlmClient
from socrates.project import ProjectSpec, create_project
from socrates.references import import_reference, curate_reference, suggest_correction_patch_with_llm
from socrates.tutoring import run_scripted_tutoring_session, suggest_next_question_with_llm

REPO_ROOT = Path(__file__).resolve().parents[1]


class V03LlmFlowTests(unittest.TestCase):
    def test_fake_llm_reference_and_tutoring_suggestions_are_visible_in_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "group_theory"
            create_project(ProjectSpec(topic="Group Theory", path=project))
            reference = root / "normality.md"
            reference.write_text(
                "### Definition: Normal Subgroup\n"
                "A normal subgroup is a subgroup where every element commutes.\n",
                encoding="utf-8",
                newline="\n",
            )
            import_reference(project, reference, role="lecture_notes", title="Normality")
            curate_reference(project, "normality")
            script = root / "session.script"
            script.write_text(
                "topic: Normal Subgroup\n"
                "question: What does normality require?\n"
                "attempt: It means abelian.\n"
                "misconception: normal_equals_abelian\n",
                encoding="utf-8",
                newline="\n",
            )
            run_scripted_tutoring_session(project, script, session_id="session_0001")
            client = FakeLlmClient(
                [
                    "{"
                    "\"location\":\"Definition\","
                    "\"original\":\"A normal subgroup is a subgroup where every element commutes.\","
                    "\"proposed_correction\":\"A normal subgroup is stable under conjugation by every group element.\","
                    "\"reason\":\"Normality is about conjugation invariance.\","
                    "\"risk_level\":\"medium\""
                    "}",
                    "{"
                    "\"question\":\"How would you test gng^-1 for arbitrary g?\","
                    "\"reason\":\"Targets normal_equals_abelian.\","
                    "\"expected_student_action\":\"Use conjugation invariance.\""
                    "}",
                ]
            )

            suggest_correction_patch_with_llm(project, "normality", client=client)
            suggest_next_question_with_llm(project, "session_0001", client=client)
            status = subprocess.run(
                [sys.executable, "-m", "socrates", "status", "--project", str(project)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("LLM suggestion drafts: 2", status.stdout)
            self.assertTrue((project / "08_evals" / "llm_suggestions_manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run failing v0.3 flow test**

Run: `python -m unittest tests.test_v03_llm_flow`

Expected before status integration: fail because `status` does not report LLM suggestion drafts.

- [ ] **Step 3: Add status/lifecycle visibility**

Add a helper near existing status helpers:

```python
def _count_llm_suggestion_drafts(project_path: Path) -> int:
    try:
        return sum(1 for item in list_llm_suggestions(project_path) if item.status == "draft")
    except (OSError, ValueError, json.JSONDecodeError):
        return 0
```

In `_handle_status`, print:

```python
    llm_suggestion_draft_count = _count_llm_suggestion_drafts(context.root)
```

and include a line in the status output:

```python
f"LLM suggestion drafts: {llm_suggestion_draft_count}"
```

If lifecycle audit already has a structured checklist helper, add a non-blocking line:

```text
- LLM suggestion drafts: pass
```

when the manifest is valid, and:

```text
- LLM suggestion drafts: fail
```

when the manifest is corrupt. This should not convert draft existence into a readiness gate failure; only corrupt generated artifact manifests should fail.

- [ ] **Step 4: Run status and lifecycle tests**

Run:

```powershell
python -m unittest tests.test_v03_llm_flow
python -m unittest tests.test_status_quality_summary
python -m unittest tests.test_lifecycle_audit
git diff --check
```

Expected: tests pass and corrupt manifests are conservative failures.

- [ ] **Step 5: Run full deterministic gate**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
bash scripts/check.sh
```

Expected: all tests pass; live DeepSeek smoke is skipped unless explicitly enabled.

- [ ] **Step 6: Commit Task 8**

Use a Lore-style commit message. Example intent line:

```text
Make LLM draft artifacts visible without gating offline workflows
```

## Task 9: Documentation and v0.3 Closure Notes

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/development_log.md`
- Modify: `docs/development_roadmap.md`
- Optionally create: `docs/v03_llm_provider_notes.md` if the DeepSeek behavior needs a durable implementation note

- [ ] **Step 1: Update README capability boundary**

In `README.md`, update the LLM boundary from "future v0.3+ architecture decision" to the implemented v0.3-alpha state:

```text
v0.3 adds an opt-in LLM provider layer for draft suggestions only. The default CLI
workflow remains deterministic and offline; live DeepSeek calls require local
`.env` configuration and are not part of the default check gate.
```

- [ ] **Step 2: Update development log**

Append a dated v0.3 entry to `docs/development_log.md` with:

```text
## v0.3 LLM provider alpha

- Added local `.env` based LLM provider configuration with redacted status output.
- Added DeepSeek provider adapter using `DEEPSEEK_MODEL=deepseek-v4-pro`.
- Added LLM suggestion artifacts for reference correction patches, tutoring next questions, and exercise feedback drafts.
- Preserved the safety boundary: LLM output is reviewed draft material and does not directly mutate curated references, reviewed notes, graded attempts, or learning state.
- Default gates remain offline; live DeepSeek smoke is opt-in.
```

- [ ] **Step 3: Update roadmap**

In `docs/development_roadmap.md`, under v0.3, mark the LLM provider alpha as completed if Tasks 1-8 passed. Keep OCR, LLM judge, and full autonomous tutoring in v0.4+ or v0.5+ unless implemented separately.

- [ ] **Step 4: Update docs index**

In `docs/README.md`, include this plan under a "Plans" section:

```markdown
## Plans

- `superpowers/plans/2026-06-04-v03-llm-provider-learning-state.md`: executable v0.3 plan for the first LLM/provider layer and DeepSeek smoke testing.
```

- [ ] **Step 5: Run documentation and full checks**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
bash scripts/check.sh
git diff --check
```

Expected: all checks pass; documentation contains no API key or raw live response.

- [ ] **Step 6: Final commit**

Use a Lore-style commit message. Example intent line:

```text
Document the v0.3 LLM alpha boundary after verified implementation
```

## Final Verification Checklist

- [ ] `python -m unittest discover -s tests` passes.
- [ ] `python -m compileall socrates` passes.
- [ ] `git diff --check` passes.
- [ ] `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` passes.
- [ ] `bash scripts/check.sh` passes.
- [ ] Default tests skip live DeepSeek calls.
- [ ] On Leo's machine, `$env:SOCRATES_RUN_LIVE_LLM="1"; python -m unittest tests.test_deepseek_live_smoke` passes or records a concrete provider/API drift reason.
- [ ] `python -m socrates llm config --root .` reports `api_key=present` without printing the key.
- [ ] `python -m socrates llm smoke --root . --prompt "Return exactly: socrates-ok"` works locally when DeepSeek is reachable.
- [ ] `git status --short --branch` shows only intentional tracked changes before commit, never `.env`.

## Definition of Done

v0.3-alpha is complete when Socrates can:

1. Read local DeepSeek config from `.env` without leaking secrets.
2. Call DeepSeek through a provider adapter in explicit smoke tests.
3. Produce LLM-based reference correction patches that still require human review/apply.
4. Produce LLM next-question drafts for tutoring sessions without changing transcripts.
5. Produce LLM exercise-feedback drafts without grading attempts or mutating learning state.
6. Show LLM draft artifact counts in status/lifecycle surfaces.
7. Pass the full deterministic v0.2/v0.3 gate without network access.

## Out of Scope for This Plan

- OCR/PDF backend implementation.
- Vector embeddings or semantic retrieval.
- Autonomous full-session LLM tutoring.
- LLM judge for quality evaluation.
- UI, Obsidian plugin, web app, or provider selection UI.
- Any new runtime dependency or third-party SDK.
