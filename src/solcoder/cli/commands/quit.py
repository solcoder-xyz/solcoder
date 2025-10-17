"""Quit command for SolCoder CLI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from solcoder.cli.types import CommandResponse, CommandRouter, SlashCommand

if TYPE_CHECKING:  # pragma: no cover
    from solcoder.cli.app import CLIApp


def register(_app: CLIApp, router: CommandRouter) -> None:
    """Register the /quit command."""

    def handle(_app: CLIApp, _args: list[str]) -> CommandResponse:
        return CommandResponse(messages=[("system", "Exiting SolCoder. Bye!")], continue_loop=False)

    router.register(SlashCommand("quit", handle, "Exit SolCoder"))


__all__ = ["register"]
