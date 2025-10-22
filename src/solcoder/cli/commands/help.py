"""Help command for SolCoder CLI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from solcoder.cli.types import CommandResponse, CommandRouter, SlashCommand

if TYPE_CHECKING:  # pragma: no cover
    from solcoder.cli.app import CLIApp


def register(app: CLIApp, router: CommandRouter) -> None:
    """Register the /help command."""

    def handle(_app: CLIApp, _args: list[str]) -> CommandResponse:
        commands = [c for c in router.available_commands() if not c.name.startswith("_")]
        commands = sorted(commands, key=lambda cmd: cmd.name)
        lines = ["Available commands:"]
        for command in commands:
            lines.append(f"/{command.name}\t{command.help_text}")
        return CommandResponse(messages=[("system", "\n".join(lines))])

    router.register(SlashCommand("help", handle, "Show available commands"))


__all__ = ["register"]
