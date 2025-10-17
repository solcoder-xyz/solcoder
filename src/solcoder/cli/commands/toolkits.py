"""Toolkit listing commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

from solcoder.cli.types import CommandResponse, CommandRouter, SlashCommand

if TYPE_CHECKING:  # pragma: no cover
    from solcoder.cli.app import CLIApp


def register(app: CLIApp, router: CommandRouter) -> None:
    """Register the /toolkits command."""

    def handle(app: CLIApp, args: list[str]) -> CommandResponse:
        toolkits = app.tool_registry.available_toolkits()
        if not args or args[0].lower() == "list":
            if not toolkits:
                return CommandResponse(messages=[("system", "No toolkits registered.")])
            lines = [
                f"{name}\t{toolkit.description} (v{toolkit.version})"
                for name, toolkit in sorted(toolkits.items())
            ]
            return CommandResponse(messages=[("system", "\n".join(lines))])

        toolkit_name = args[0]
        toolkit = toolkits.get(toolkit_name)
        if not toolkit:
            return CommandResponse(messages=[("system", f"Toolkit '{toolkit_name}' not found.")])

        if len(args) == 1 or (len(args) >= 2 and args[1].lower() == "tools"):
            lines = [f"{tool.name}\t{tool.description}" for tool in toolkit.tools]
            header = f"Tools in toolkit '{toolkit.name}' (v{toolkit.version}):"
            return CommandResponse(messages=[("system", "\n".join([header, *lines]))])

        return CommandResponse(messages=[("system", "Usage: /toolkits list | /toolkits <toolkit> tools")])

    router.register(SlashCommand("toolkits", handle, "List toolkits and tools"))


__all__ = ["register"]
