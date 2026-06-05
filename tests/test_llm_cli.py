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
