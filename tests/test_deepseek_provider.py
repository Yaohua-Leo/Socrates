from io import BytesIO
import json
import unittest
from urllib.error import HTTPError

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
                {
                    "choices": [{"message": {"content": "socrates-ok"}}],
                    "usage": {"total_tokens": 4},
                }
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
        self.assertEqual(captured["url"], "https://api.deepseek.com/chat/completions")
        self.assertEqual(captured["body"]["model"], "deepseek-v4-pro")
        self.assertEqual(captured["body"]["thinking"], {"type": "disabled"})
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

    def test_provider_errors_are_redacted(self) -> None:
        def opener(request, timeout=0):
            raise HTTPError(
                request.full_url,
                401,
                "Unauthorized fake-secret-value",
                hdrs=None,
                fp=BytesIO(b'{"error":{"message":"bad key fake-secret-value"}}'),
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

        with self.assertRaises(LlmProviderError) as raised:
            client.complete(
                LlmRequest(
                    purpose="smoke",
                    messages=(LlmMessage(role="user", content="Return ok"),),
                )
            )

        self.assertNotIn("fake-secret-value", str(raised.exception))
        self.assertIn("DeepSeek HTTP 401", str(raised.exception))

    def test_rejects_unusable_response_shape(self) -> None:
        client = DeepSeekClient(
            LlmConfig(
                provider="deepseek",
                api_key="fake-secret-value",
                base_url="https://api.deepseek.com",
                model="deepseek-v4-pro",
            ),
            opener=lambda request, timeout=0: FakeHttpResponse({"choices": []}),
        )

        with self.assertRaisesRegex(LlmProviderError, "missing content"):
            client.complete(
                LlmRequest(
                    purpose="smoke",
                    messages=(LlmMessage(role="user", content="Return ok"),),
                )
            )


if __name__ == "__main__":
    unittest.main()
