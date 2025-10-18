"""Logs command for viewing recent operational events."""

from __future__ import annotations

from typing import TYPE_CHECKING

from solcoder.cli.types import CommandResponse, CommandRouter, SlashCommand
from solcoder.core.logs import VALID_CATEGORIES

if TYPE_CHECKING:  # pragma: no cover
    from solcoder.cli.app import CLIApp

DEFAULT_LOG_LIMIT = 20


def register(app: CLIApp, router: CommandRouter) -> None:
    """Register the /logs command."""

    def handle(app: CLIApp, args: list[str]) -> CommandResponse:
        category_filter: str | None = None
        if args:
            candidate = args[0].lower()
            if candidate not in VALID_CATEGORIES:
                allowed = ", ".join(sorted(VALID_CATEGORIES))
                return CommandResponse(
                    messages=[("system", f"Unknown log category '{candidate}'. Choose from: {allowed}.")],
                )
            category_filter = candidate

        entries = app.log_buffer.recent(category=category_filter, limit=DEFAULT_LOG_LIMIT)
        if not entries:
            if category_filter:
                return CommandResponse(
                    messages=[("system", f"No '{category_filter}' log entries yet.")],
                )
            return CommandResponse(messages=[("system", "No log entries recorded yet.")])

        lines: list[str] = []
        header = "timestamp           category  severity message"
        lines.append(header)
        lines.append("-" * len(header))
        for entry in entries:
            timestamp = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            lines.append(
                f"{timestamp}  {entry.category:<8} {entry.severity.upper():<7} {entry.message}",
            )
        return CommandResponse(messages=[("system", "\n".join(lines))])

    router.register(SlashCommand("logs", handle, "Show recent activity logs"))


__all__ = ["register"]
