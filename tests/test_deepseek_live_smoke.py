import os
import unittest

from socrates.deepseek import DeepSeekClient
from socrates.llm import LlmMessage, LlmRequest
from socrates.llm_config import load_llm_config


@unittest.skipUnless(
    os.environ.get("SOCRATES_RUN_LIVE_LLM") == "1",
    "live DeepSeek smoke is opt-in",
)
class DeepSeekLiveSmokeTests(unittest.TestCase):
    def test_live_deepseek_smoke_returns_text(self) -> None:
        config = load_llm_config()
        client = DeepSeekClient(config)
        response = client.complete(
            LlmRequest(
                purpose="live_smoke",
                messages=(
                    LlmMessage(role="user", content="Return exactly: socrates-ok"),
                ),
                temperature=0.0,
                max_tokens=20,
            )
        )

        self.assertIn("socrates-ok", response.content.lower())


if __name__ == "__main__":
    unittest.main()
