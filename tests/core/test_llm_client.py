import json

import httpx
import pytest

from solcoder.core.llm import LLMClient, LLMError, LLMResponse, LLMSettings


def test_stream_chat_offline_returns_stub() -> None:
    settings = LLMSettings(
        provider="openai",
        base_url="https://api.openai.com/v1",
        model="gpt-5-codex",
        api_key=None,
        offline_mode=True,
    )
    client = LLMClient(settings)
    tokens: list[str] = []

    response = client.stream_chat("hello world", on_chunk=tokens.append)

    assert isinstance(response, LLMResponse)
    assert response.cached is True
    assert "[offline stub]" in response.text
    assert tokens == [response.text]


def test_stream_chat_parses_stream_payload() -> None:
    lines = [
        b"data: {\"type\":\"response.output_text.delta\",\"delta\":\"Hello\",\"response\":{\"id\":\"resp_123\"}}\n\n",
        b"data: {\"type\":\"response.output_text.delta\",\"delta\":\" world\",\"response\":{\"id\":\"resp_123\"}}\n\n",
        b"data: {\"type\":\"response.completed\",\"response\":{\"status\":\"completed\",\"output_text\":\"Hello world\",\"usage\":{\"input_tokens\":5,\"output_tokens\":7,\"total_tokens\":12}}}\n\n",
        b"data: [DONE]\n\n",
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path.endswith("/responses")
        payload = json.loads(request.content.decode())
        assert payload["stream"] is True
        assert payload["input"][-1]["content"] == "ping"
        assert payload["reasoning"]["effort"] == "high"
        return httpx.Response(
            status_code=200,
            headers={"content-type": "text/event-stream"},
            content=b"".join(lines),
        )

    transport = httpx.MockTransport(handler)
    settings = LLMSettings(
        provider="openai",
        base_url="https://api.openai.com/v1",
        model="gpt-5-codex",
        api_key="test-key",
        reasoning_effort="high",
    )
    client = LLMClient(settings, client=httpx.Client(transport=transport))
    tokens: list[str] = []

    response = client.stream_chat("ping", on_chunk=tokens.append)

    assert response.text == "Hello world"
    assert tokens == ["Hello", " world"]
    assert response.finish_reason == "completed"
    assert response.token_usage == {"input_tokens": 5, "output_tokens": 7, "total_tokens": 12}


def test_stream_chat_raises_on_http_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=401, json={"error": {"message": "bad key"}})

    transport = httpx.MockTransport(handler)
    settings = LLMSettings(
        provider="openai",
        base_url="https://api.openai.com/v1",
        model="gpt-5-codex",
        api_key="bad-key",
    )
    client = LLMClient(settings, client=httpx.Client(transport=transport))

    with pytest.raises(LLMError) as excinfo:
        client.stream_chat("unauthorized")

    assert "bad key" in str(excinfo.value)
