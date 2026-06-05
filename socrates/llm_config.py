"""Local LLM provider configuration loading."""

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
