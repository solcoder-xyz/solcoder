"""Centralised in-memory log buffer for SolCoder CLI telemetry."""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable, Deque, Iterable, Literal

LogCategory = Literal["build", "deploy", "wallet", "system"]
LogSeverity = Literal["info", "warning", "error"]

VALID_CATEGORIES: set[str] = {"build", "deploy", "wallet", "system"}
VALID_SEVERITIES: set[str] = {"info", "warning", "error"}

_BASE58_PATTERN = re.compile(r"\b[1-9A-HJ-NP-Za-km-z]{32,44}\b")


def _mask_base58(token: str) -> str:
    if len(token) <= 8:
        return "••••"
    return f"{token[:4]}…{token[-4:]}"


def _redact(text: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        return _mask_base58(match.group(0))

    return _BASE58_PATTERN.sub(_replace, text)


@dataclass(slots=True)
class LogEntry:
    """Represents a single structured log entry."""

    timestamp: datetime
    category: LogCategory
    severity: LogSeverity
    message: str

    def as_dict(self) -> dict[str, str]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "category": self.category,
            "severity": self.severity,
            "message": self.message,
        }


class LogBuffer:
    """Fixed-size FIFO buffer storing CLI event logs with redaction."""

    def __init__(
        self,
        *,
        max_entries: int = 200,
        redaction_enabled: bool = True,
    ) -> None:
        self.max_entries = max(max_entries, 1)
        self._redaction_enabled = redaction_enabled
        self._entries: Deque[LogEntry] = deque(maxlen=self.max_entries)
        self._subscribers: list[Callable[[LogEntry], None]] = []

    def record(self, category: str, message: str, *, severity: str = "info") -> LogEntry:
        normalized_category = category.lower()
        if normalized_category not in VALID_CATEGORIES:
            normalized_category = "system"
        normalized_severity = severity.lower()
        if normalized_severity not in VALID_SEVERITIES:
            normalized_severity = "info"
        sanitized = _redact(message) if self._redaction_enabled else message
        entry = LogEntry(
            timestamp=datetime.now(UTC),
            category=normalized_category,  # type: ignore[arg-type]
            severity=normalized_severity,  # type: ignore[arg-type]
            message=sanitized,
        )
        self._entries.append(entry)
        for callback in list(self._subscribers):
            callback(entry)
        return entry

    def recent(self, *, category: str | None = None, limit: int = 50) -> list[LogEntry]:
        if category is None:
            return list(self._slice_latest(limit))
        normalized_category = category.lower()
        if normalized_category not in VALID_CATEGORIES:
            normalized_category = "system"
        filtered = [entry for entry in self._entries if entry.category == normalized_category]
        return filtered[-limit:]

    def latest(self) -> LogEntry | None:
        if not self._entries:
            return None
        return self._entries[-1]

    def subscribe(self, callback: Callable[[LogEntry], None]) -> None:
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[LogEntry], None]) -> None:
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def _slice_latest(self, limit: int) -> Iterable[LogEntry]:
        if limit <= 0:
            return []
        if limit >= len(self._entries):
            return list(self._entries)
        return list(self._entries)[-limit:]


__all__ = ["LogBuffer", "LogEntry", "LogCategory", "LogSeverity", "VALID_CATEGORIES", "VALID_SEVERITIES"]
