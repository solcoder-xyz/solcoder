"""HTTP transport helpers for the LLM client."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Sequence

from .errors import LLMError
from .types import ChunkCallback, LLMSettings

logger = logging.getLogger(__name__)


def build_endpoint(settings: LLMSettings) -> str:
    provider = settings.provider.lower()
    base = settings.base_url.rstrip("/")
    if provider in {"openai", "gpt"}:
        return f"{base}/responses"
    if provider in {"anthropic", "claude"}:
        return f"{base}/messages"
    return f"{base}/chat/completions"


def build_headers(settings: LLMSettings) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if settings.api_key:
        headers["Authorization"] = f"Bearer {settings.api_key}"
    provider = settings.provider.lower()
    if provider in {"anthropic", "claude"}:
        headers["x-api-key"] = settings.api_key or ""
        headers["anthropic-version"] = "2023-06-01"
    return headers


def normalize_messages(
    prompt: str,
    system_prompt: str | None,
    history: Sequence[dict[str, str]] | None,
) -> list[dict[str, str]]:
    conversation: list[dict[str, str]] = []
    if system_prompt:
        conversation.append({"role": "system", "content": system_prompt})
    for item in history or []:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "user"))
        content = item.get("content")
        if isinstance(content, str) and content:
            conversation.append({"role": role, "content": content})
    conversation.append({"role": "user", "content": prompt})
    return conversation


def build_payload(settings: LLMSettings, messages: list[dict[str, str]]) -> dict[str, object]:
    provider = settings.provider.lower()
    payload: dict[str, object] = {
        "model": settings.model,
        "stream": True,
    }
    if provider in {"openai", "gpt"}:
        payload["input"] = messages
        if settings.reasoning_effort:
            payload["reasoning"] = {"effort": settings.reasoning_effort}
    else:
        payload["messages"] = messages
        if provider in {"anthropic", "claude"}:
            payload["max_tokens"] = max(settings.max_output_tokens, 1)
    return payload


def consume_stream(
    lines: Iterable[str],
    on_chunk: ChunkCallback | None,
) -> tuple[str, str | None, dict[str, int] | None]:
    text_parts: list[str] = []
    finish_reason: str | None = None
    usage: dict[str, int] | None = None
    for raw_line in lines:
        if not raw_line:
            continue
        if raw_line.startswith("data:"):
            payload = raw_line.partition("data:")[2].strip()
        else:
            payload = raw_line.strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            logger.debug("Skipping non-JSON LLM payload: %s", payload)
            continue
        chunk_text, finish_reason, usage, handled = _handle_response_event(
            parsed,
            finish_reason,
            usage,
            bool(text_parts),
        )
        if not handled:
            chunk_text, finish_reason = _extract_chunk(parsed, finish_reason)
        if chunk_text:
            text_parts.append(chunk_text)
            if on_chunk:
                on_chunk(chunk_text)
    return "".join(text_parts), finish_reason, usage


def _handle_response_event(
    payload: dict[str, object],
    finish_reason: str | None,
    usage: dict[str, int] | None,
    has_existing_text: bool,
) -> tuple[str, str | None, dict[str, int] | None, bool]:
    event_type = str(payload.get("type", "")) if isinstance(payload, dict) else ""
    if not event_type:
        return "", finish_reason, usage, False

    if event_type == "response.error":
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message") or json.dumps(error)
        else:
            message = str(error or "Unknown LLM error")
        raise LLMError(message)

    chunk_text = ""
    if event_type.endswith(".delta"):
        delta = payload.get("delta")
        if isinstance(delta, str):
            chunk_text = delta
    elif event_type == "response.output_text":
        text = payload.get("text")
        if isinstance(text, str):
            chunk_text = text
    elif event_type == "response.completed":
        response_block = payload.get("response")
        if isinstance(response_block, dict):
            finish_reason = response_block.get("status") or finish_reason or "completed"
            usage_payload = response_block.get("usage")
            parsed_usage = _parse_usage(usage_payload)
            if parsed_usage:
                usage = parsed_usage
            final_text = response_block.get("output_text")
            if isinstance(final_text, str) and final_text and not has_existing_text:
                chunk_text = final_text
    else:
        delta = payload.get("delta")
        if isinstance(delta, str):
            chunk_text = delta

    return chunk_text, finish_reason, usage, True


def _extract_chunk(payload: dict[str, object], finish_reason: str | None) -> tuple[str, str | None]:
    if "content" in payload and isinstance(payload["content"], str):
        return payload["content"], finish_reason
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        choice = choices[0]
        if isinstance(choice, dict):
            delta = choice.get("delta")
            if isinstance(delta, dict):
                content = delta.get("content")
                if isinstance(content, str):
                    finish_reason = choice.get("finish_reason", finish_reason)
                    return content, finish_reason
            message = choice.get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str):
                    finish_reason = choice.get("finish_reason", finish_reason)
                    return content, finish_reason
    return "", finish_reason


def _parse_usage(usage_payload: object) -> dict[str, int] | None:
    if not isinstance(usage_payload, dict):
        return None
    usage: dict[str, int] = {}
    for key, value in usage_payload.items():
        if isinstance(value, int):
            usage[key] = value
        elif isinstance(value, float):
            usage[key] = int(value)
    return usage or None


__all__ = [
    "build_endpoint",
    "build_headers",
    "normalize_messages",
    "build_payload",
    "consume_stream",
]
