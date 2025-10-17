"""LLM client utilities for SolCoder."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

import httpx

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """Raised when the LLM client cannot complete a request."""


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


@dataclass(slots=True)
class LLMResponse:
    """Holds metadata for a streamed LLM response."""

    text: str
    latency_seconds: float
    finish_reason: str | None = None
    token_usage: dict[str, int] | None = None
    cached: bool = False


ChunkCallback = Callable[[str], None]


class LLMClient:
    """Minimal streaming LLM client with retry logic and offline fallback."""

    def __init__(
        self,
        settings: LLMSettings,
        *,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._settings = settings
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=settings.timeout_seconds)
        self._sleep = sleep or time.sleep

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def stream_chat(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        history: Sequence[dict[str, str]] | None = None,
        on_chunk: ChunkCallback | None = None,
    ) -> LLMResponse:
        """Send a prompt and stream the response back."""

        if self._settings.offline_mode or not self._settings.api_key:
            logger.info("LLM offline mode active; returning stub response.")
            content = self._offline_response(prompt, system_prompt)
            if on_chunk:
                on_chunk(content)
            return LLMResponse(text=content, latency_seconds=0.0, cached=True)

        messages = self._normalize_messages(prompt, system_prompt, history)

        url = self._build_endpoint()
        headers = self._build_headers()
        payload = self._build_payload(messages)

        attempt = 0
        backoff = 1.5
        last_error: Exception | None = None

        while attempt <= self._settings.max_retries:
            start_time = time.perf_counter()
            try:
                with self._client.stream("POST", url, headers=headers, json=payload) as response:
                    response.raise_for_status()
                    text, finish_reason, usage = self._consume_stream(response.iter_lines(), on_chunk)
                latency = time.perf_counter() - start_time
                logger.debug(
                    "LLM call successful (model=%s, latency=%.2fs, usage=%s)",
                    self._settings.model,
                    latency,
                    usage,
                )
                return LLMResponse(
                    text=text,
                    latency_seconds=latency,
                    finish_reason=finish_reason,
                    token_usage=usage,
                )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:  # noqa: PERF203
                last_error = exc
                attempt += 1
                if attempt > self._settings.max_retries:
                    break
                sleep_for = backoff**attempt
                logger.warning("LLM request failed (%s); retrying in %.1fs", type(exc).__name__, sleep_for)
                self._sleep(sleep_for)
                continue
            except httpx.HTTPStatusError as exc:
                logger.error("LLM request failed with status %s: %s", exc.response.status_code, exc)
                detail: str | dict[str, object] | None = None
                try:
                    raw = exc.response.read()
                    if raw:
                        try:
                            detail = json.loads(raw.decode("utf-8", errors="replace"))
                        except json.JSONDecodeError:
                            detail = raw.decode("utf-8", errors="replace")
                except Exception as read_exc:  # noqa: BLE001
                    logger.debug("Unable to read error payload: %s", read_exc)
                if detail is None:
                    detail = exc.response.reason_phrase
                raise LLMError(f"LLM request failed: {detail}") from exc
            except Exception as exc:  # noqa: BLE001
                logger.exception("Unexpected LLM error: %s", exc)
                raise LLMError(f"Unexpected LLM error: {exc}") from exc

        message = f"LLM request failed after {self._settings.max_retries + 1} attempts"
        if last_error:
            message = f"{message}: {last_error}"
        raise LLMError(message)

    def close(self) -> None:
        """Dispose the underlying HTTP client if owned by this instance."""
        if self._owns_client:
            self._client.close()

    def update_settings(self, *, model: str | None = None, reasoning_effort: str | None = None) -> None:
        """Update mutable LLM settings at runtime."""
        if model:
            logger.debug("Updating LLM model from %s to %s", self._settings.model, model)
            self._settings.model = model
        if reasoning_effort:
            logger.debug(
                "Updating LLM reasoning effort from %s to %s",
                self._settings.reasoning_effort,
                reasoning_effort,
            )
            self._settings.reasoning_effort = reasoning_effort

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _offline_response(self, prompt: str, system_prompt: str | None) -> str:
        pieces = ["[offline stub]"]
        if system_prompt:
            pieces.append(f"(system: {system_prompt.strip()[:120]})")
        trimmed_prompt = prompt.strip()
        if len(trimmed_prompt) > 160:
            trimmed_prompt = f"{trimmed_prompt[:157]}…"
        pieces.append(trimmed_prompt or "<empty prompt>")
        return " ".join(pieces)

    def _build_endpoint(self) -> str:
        provider = self._settings.provider.lower()
        base = self._settings.base_url.rstrip("/")
        if provider in {"openai", "gpt"}:
            return f"{base}/responses"
        if provider in {"anthropic", "claude"}:
            return f"{base}/messages"
        return f"{base}/chat/completions"

    def _build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._settings.api_key:
            headers["Authorization"] = f"Bearer {self._settings.api_key}"
        provider = self._settings.provider.lower()
        if provider in {"anthropic", "claude"}:
            headers["x-api-key"] = self._settings.api_key or ""
            headers["anthropic-version"] = "2023-06-01"
        return headers

    def _normalize_messages(
        self,
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

    def _build_payload(self, messages: list[dict[str, str]]) -> dict[str, object]:
        provider = self._settings.provider.lower()
        payload: dict[str, object] = {
            "model": self._settings.model,
            "stream": True,
        }
        if provider in {"openai", "gpt"}:
            payload["input"] = messages
            if self._settings.reasoning_effort:
                payload["reasoning"] = {"effort": self._settings.reasoning_effort}
        else:
            payload["messages"] = messages
        return payload

    def _consume_stream(
        self,
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
            chunk_text, finish_reason, usage, handled = self._handle_response_event(
                parsed,
                finish_reason,
                usage,
                bool(text_parts),
            )
            if not handled:
                chunk_text, finish_reason = self._extract_chunk(parsed, finish_reason)
            if chunk_text:
                text_parts.append(chunk_text)
                if on_chunk:
                    on_chunk(chunk_text)
        return "".join(text_parts), finish_reason, usage

    def _handle_response_event(
        self,
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
                parsed_usage = self._parse_usage(usage_payload)
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

    def _extract_chunk(self, payload: dict[str, object], finish_reason: str | None) -> tuple[str, str | None]:
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

    def _parse_usage(self, usage_payload: object) -> dict[str, int] | None:
        if not isinstance(usage_payload, dict):
            return None
        usage: dict[str, int] = {}
        for key, value in usage_payload.items():
            if isinstance(value, int):
                usage[key] = value
            elif isinstance(value, float):
                usage[key] = int(value)
        return usage or None


__all__ = ["LLMClient", "LLMError", "LLMResponse", "LLMSettings"]
