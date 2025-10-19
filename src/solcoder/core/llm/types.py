"""Shared LLM types."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

ChunkCallback = Callable[[str], None]


@dataclass(slots=True)
class LLMSettings:
    """Runtime configuration for the LLM client."""

    provider: str
    base_url: str
    model: str
    api_key: str | None
    timeout_seconds: float = 30.0
    max_retries: int = 2
    offline_mode: bool = False
    reasoning_effort: str = "medium"
    max_output_tokens: int = 1024


@dataclass(slots=True)
class LLMResponse:
    """Holds metadata for a streamed LLM response."""

    text: str
    latency_seconds: float
    finish_reason: str | None = None
    token_usage: dict[str, int] | None = None
    cached: bool = False


__all__ = ["LLMSettings", "LLMResponse", "ChunkCallback"]
