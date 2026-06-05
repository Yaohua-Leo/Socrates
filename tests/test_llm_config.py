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
