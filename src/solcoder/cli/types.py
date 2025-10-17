"""Shared CLI types and routing helpers."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:  # pragma: no cover
    from solcoder.cli.app import CLIApp
else:  # pragma: no cover - runtime only
    CLIApp = Any  # type: ignore[assignment]


logger = logging.getLogger(__name__)


@dataclass
class CommandResponse:
    """Represents the outcome of handling a CLI input."""

    messages: list[tuple[str, str]]
    continue_loop: bool = True
    tool_calls: list[dict[str, Any]] | None = None
    rendered_roles: set[str] | None = None


class LLMBackend(Protocol):
    """Interface for SolCoder LLM adapters."""

    def stream_chat(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        history: Iterable[dict[str, str]] | None = None,
        on_chunk: Callable[[str], None] | None = None,
    ) -> Any:
        ...


class SlashCommand:
    """Container for slash command metadata."""

    def __init__(self, name: str, handler: Callable[[CLIApp, list[str]], CommandResponse], help_text: str) -> None:
        self.name = name
        self.handler = handler
        self.help_text = help_text


class CommandRouter:
    """Parses and dispatches slash commands."""

    def __init__(self) -> None:
        self._commands: dict[str, SlashCommand] = {}

    def register(self, command: SlashCommand) -> None:
        logger.debug("Registering command: %s", command.name)
        self._commands[command.name] = command

    def available_commands(self) -> Iterable[SlashCommand]:
        return self._commands.values()

    def dispatch(self, app: CLIApp, raw_line: str) -> CommandResponse:
        parts = raw_line.strip().split()
        if not parts:
            return CommandResponse(messages=[])
        command_name, *args = parts
        command = self._commands.get(command_name)
        if not command:
            logger.info("Unknown command: /%s", command_name)
            return CommandResponse(messages=[("system", f"Unknown command '/{command_name}'. Type /help for a list of commands.")])
        logger.debug("Dispatching command '/%s' with args %s", command_name, args)
        return command.handler(app, args)


__all__ = ["CommandResponse", "CommandRouter", "LLMBackend", "SlashCommand"]
