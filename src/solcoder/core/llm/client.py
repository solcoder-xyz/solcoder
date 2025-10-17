"""Concrete LLM client implementation."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Sequence

import httpx

from .errors import LLMError
from .offline import offline_response
from .transport import (
    build_endpoint,
    build_headers,
    build_payload,
    consume_stream,
    normalize_messages,
)
from .types import ChunkCallback, LLMResponse, LLMSettings

logger = logging.getLogger(__name__)


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
            content = offline_response(prompt, system_prompt)
            if on_chunk:
                on_chunk(content)
            return LLMResponse(text=content, latency_seconds=0.0, cached=True)

        messages = normalize_messages(prompt, system_prompt, history)
        url = build_endpoint(self._settings)
        headers = build_headers(self._settings)
        payload = build_payload(self._settings, messages)

        attempt = 0
        backoff = 1.5
        last_error: Exception | None = None

        while attempt <= self._settings.max_retries:
            start_time = time.perf_counter()
            try:
                with self._client.stream("POST", url, headers=headers, json=payload) as response:
                    response.raise_for_status()
                    text, finish_reason, usage = consume_stream(response.iter_lines(), on_chunk)
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
                sleep_for = backoff ** attempt
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


__all__ = ["LLMClient"]
