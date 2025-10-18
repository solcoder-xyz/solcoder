"""Conversation context helpers shared across SolCoder components."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Sequence

from solcoder.core.llm import LLMError
from solcoder.session import TRANSCRIPT_LIMIT, SessionContext

from .config import ConfigContext

if TYPE_CHECKING:  # pragma: no cover
    from solcoder.cli.types import LLMBackend
else:  # pragma: no cover - runtime fallback
    LLMBackend = Any

logger = logging.getLogger(__name__)


DEFAULT_HISTORY_LIMIT = 20
DEFAULT_SUMMARY_KEEP = 10
DEFAULT_SUMMARY_MAX_WORDS = 200
DEFAULT_AUTO_COMPACT_THRESHOLD = 0.95
DEFAULT_LLM_INPUT_LIMIT = 272_000
DEFAULT_COMPACTION_COOLDOWN = 10


class HistoryCompactionStrategy:
    """Protocol for history compaction policies."""

    def compact(self, manager: ContextManager) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def force_compact(self, manager: ContextManager) -> str:  # pragma: no cover - interface
        raise NotImplementedError


@dataclass
class RollingHistoryStrategy(HistoryCompactionStrategy):
    """Default strategy that rolls older entries into summaries when limits are hit."""

    def compact(self, manager: ContextManager) -> None:
        transcript = manager.session_context.transcript
        metadata = manager.session_context.metadata
        history_limit = manager.config_int("history_max_messages", DEFAULT_HISTORY_LIMIT)
        cooldown = metadata.compression_cooldown
        if len(transcript) > history_limit and cooldown <= 0:
            self._summarize_older_history(manager)

        input_limit = manager.config_int("llm_input_token_limit", DEFAULT_LLM_INPUT_LIMIT)
        threshold = manager.config_float(
            "history_auto_compact_threshold",
            DEFAULT_AUTO_COMPACT_THRESHOLD,
        )
        if metadata.llm_last_input_tokens >= int(input_limit * threshold) and cooldown <= 0:
            self._compress_full_history(manager)

        metadata.compression_cooldown = max(metadata.compression_cooldown - 1, 0)

    def force_compact(self, manager: ContextManager) -> str:
        before = len(manager.session_context.transcript)
        self._compress_full_history(manager)
        after = len(manager.session_context.transcript)
        return f"Compacted history from {before} entries to {after}."

    def _summarize_older_history(self, manager: ContextManager) -> None:
        transcript = manager.session_context.transcript
        history_limit = manager.config_int("history_max_messages", DEFAULT_HISTORY_LIMIT)
        keep_count = manager.config_int("history_summary_keep", DEFAULT_SUMMARY_KEEP)
        if keep_count >= history_limit:
            keep_count = max(history_limit - 2, 1)
        if len(transcript) <= keep_count:
            return

        older = transcript[:-keep_count]
        if not older:
            return

        summary_text = manager.generate_summary(older)
        summary_entry = {
            "role": "system",
            "message": summary_text,
            "timestamp": datetime.now(UTC).isoformat(),
            "summary": True,
        }
        manager.session_context.transcript = [summary_entry, *transcript[-keep_count:]]
        manager.refresh_transcript_reference()
        input_limit = manager.config_int("llm_input_token_limit", DEFAULT_LLM_INPUT_LIMIT)
        manager.session_context.metadata.llm_last_input_tokens = min(
            manager.estimate_context_tokens(),
            input_limit,
        )
        manager.session_context.metadata.compression_cooldown = manager.config_int(
            "history_compaction_cooldown",
            DEFAULT_COMPACTION_COOLDOWN,
        )

    def _compress_full_history(self, manager: ContextManager) -> None:
        transcript = manager.session_context.transcript
        keep_count = manager.config_int("history_summary_keep", DEFAULT_SUMMARY_KEEP)
        keep_count = max(min(keep_count, len(transcript)), 1)
        if len(transcript) <= keep_count:
            return

        keep = transcript[-keep_count:]
        summary_text = manager.generate_summary(transcript[:-keep_count])
        summary_entry = {
            "role": "system",
            "message": summary_text,
            "timestamp": datetime.now(UTC).isoformat(),
            "summary": True,
        }
        manager.session_context.transcript = [summary_entry, *keep]
        manager.refresh_transcript_reference()
        estimated = manager.estimate_context_tokens()
        metadata = manager.session_context.metadata
        input_limit = manager.config_int("llm_input_token_limit", DEFAULT_LLM_INPUT_LIMIT)
        metadata.llm_last_input_tokens = min(estimated, input_limit)
        metadata.compression_cooldown = manager.config_int(
            "history_compaction_cooldown",
            DEFAULT_COMPACTION_COOLDOWN,
        )


class ContextManager:
    """Coordinates transcript updates and history compaction policies for the CLI."""

    def __init__(
        self,
        session_context: SessionContext,
        *,
        llm: LLMBackend | None,
        config_context: ConfigContext | None,
        strategy: HistoryCompactionStrategy | None = None,
    ) -> None:
        self.session_context = session_context
        self.llm = llm
        self.config_context = config_context
        self.strategy = strategy or RollingHistoryStrategy()
        self._transcript = self.session_context.transcript

    @property
    def transcript(self) -> list[dict[str, Any]]:
        return self._transcript

    def refresh_transcript_reference(self) -> None:
        """Resynchronise cached transcript reference after reassignment."""
        self._transcript = self.session_context.transcript

    def conversation_history(self) -> list[dict[str, str]]:
        history: list[dict[str, str]] = []
        for entry in self.transcript[:-1]:
            message = entry.get("message")
            if not isinstance(message, str) or not message:
                continue
            if entry.get("summary"):
                history.append({"role": "system", "content": message})
                continue
            role = entry.get("role")
            if role == "user":
                history.append({"role": "user", "content": message})
            elif role == "agent":
                history.append({"role": "assistant", "content": message})
            else:
                history.append({"role": "system", "content": message})
        return history

    def record(
        self,
        role: str,
        message: str,
        *,
        tool_calls: Sequence[dict[str, Any]] | None = None,
    ) -> None:
        entry: dict[str, Any] = {
            "role": role,
            "message": message,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        if tool_calls:
            entry["tool_calls"] = list(tool_calls)
        self.session_context.transcript.append(entry)
        if len(self.session_context.transcript) > TRANSCRIPT_LIMIT:
            del self.session_context.transcript[:-TRANSCRIPT_LIMIT]
        self.refresh_transcript_reference()

    def compact_history_if_needed(self) -> None:
        self.strategy.compact(self)

    def force_compact_history(self) -> str:
        return self.strategy.force_compact(self)

    def config_int(self, attr: str, default: int) -> int:
        if self.config_context is None:
            return default
        return int(getattr(self.config_context.config, attr, default) or default)

    def config_float(self, attr: str, default: float) -> float:
        if self.config_context is None:
            return default
        return float(getattr(self.config_context.config, attr, default) or default)

    def estimate_context_tokens(self) -> int:
        total = 0
        for entry in self.session_context.transcript:
            message = entry.get("message")
            if isinstance(message, str):
                total += len(message.split())
        return total

    def generate_summary(self, entries: list[dict[str, Any]]) -> str:
        if not entries:
            return "(history empty)"

        conversation_lines: list[str] = []
        for entry in entries:
            role = entry.get("role", "unknown")
            message = entry.get("message", "")
            conversation_lines.append(f"{role}: {message}")
        transcript_text = "\n".join(conversation_lines)
        base_words = self.config_int("history_summary_max_words", DEFAULT_SUMMARY_MAX_WORDS)
        keep_count = self.config_int("history_summary_keep", DEFAULT_SUMMARY_KEEP)
        multiplier = max(1, len(entries) // max(1, keep_count))
        max_words = base_words * multiplier
        prompt = (
            f"Summarize the following SolCoder chat history in no more than {max_words} words. "
            "Highlight user goals, decisions, constraints, and any open questions.\n"
            f"Conversation:\n{transcript_text}\n"
            "Return plain text without bullet characters unless required."
        )
        if self.llm is None:
            logger.warning("LLM backend unavailable; returning truncated history for summary.")
            return "\n".join(conversation_lines[-3:]) or "Summary not available."

        tokens: list[str] = []
        try:
            result = self.llm.stream_chat(  # type: ignore[call-arg]
                prompt,
                history=(),
                system_prompt="You are a concise summarization engine for coding assistant transcripts.",
                on_chunk=tokens.append,
            )
            summary_text = "".join(tokens).strip() or getattr(result, "text", "").strip()
        except LLMError as exc:
            logger.warning("LLM summarization failed: %s", exc)
            summary_text = "Summary unavailable. Recent highlights:\n" + "\n".join(conversation_lines[-3:])
        if not summary_text:
            summary_text = "Summary not available."
        return summary_text

__all__ = [
    "ContextManager",
    "HistoryCompactionStrategy",
    "RollingHistoryStrategy",
    "DEFAULT_HISTORY_LIMIT",
    "DEFAULT_SUMMARY_KEEP",
    "DEFAULT_SUMMARY_MAX_WORDS",
    "DEFAULT_AUTO_COMPACT_THRESHOLD",
    "DEFAULT_LLM_INPUT_LIMIT",
    "DEFAULT_COMPACTION_COOLDOWN",
]
