from __future__ import annotations

import json
from collections.abc import Callable, Iterable

from solcoder.cli.types import LLMBackend
from solcoder.core.llm import LLMResponse


class StubLLM(LLMBackend):
    """Placeholder LLM adapter used until the real integration is wired in."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.model = "gpt-5-codex"
        self.reasoning_effort = "medium"
        self._awaiting_ack = False
        self._last_user_prompt = ""

    def respond(self, prompt: str) -> str:
        self.calls.append(prompt)
        if not self._awaiting_ack:
            self._awaiting_ack = True
            self._last_user_prompt = prompt
            payload = {
                "type": "plan",
                "message": "Stub plan for the request.",
                "steps": [
                    f"Consider the request: {prompt[:80]}",
                    "Outline the response.",
                ],
            }
        else:
            self._awaiting_ack = False
            payload = {
                "type": "reply",
                "message": f"[stub] Completed request: {self._last_user_prompt[:80]}",
            }
        return json.dumps(payload)

    def stream_chat(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        history: Iterable[dict[str, str]] | None = None,
        on_chunk: Callable[[str], None] | None = None,
    ) -> LLMResponse:
        reply = self.respond(prompt)
        if on_chunk:
            on_chunk(reply)
        words_in = max(len(prompt.split()), 1)
        words_out = max(len(reply.split()), 1)
        return LLMResponse(
            text=reply,
            latency_seconds=0.0,
            cached=True,
            token_usage={
                "input_tokens": words_in,
                "output_tokens": words_out,
                "total_tokens": words_in + words_out,
            },
        )

    def update_settings(self, *, model: str | None = None, reasoning_effort: str | None = None) -> None:
        if model:
            self.model = model
        if reasoning_effort:
            self.reasoning_effort = reasoning_effort


__all__ = ["StubLLM"]
