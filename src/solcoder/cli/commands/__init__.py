"""Builtin CLI command registration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from solcoder.cli.commands import env, logs, session, settings, template, todo, toolkits, wallet, program, metadata as metadata_cmd, blueprint as blueprint_cmd, new as new_cmd, init as init_cmd, deploy as deploy_cmd, kb as kb_cmd
from solcoder.cli.commands import help as help_cmd
from solcoder.cli.commands import quit as quit_cmd
from solcoder.cli.types import CommandRouter

if TYPE_CHECKING:  # pragma: no cover
    from solcoder.cli.app import CLIApp


def register_builtin_commands(app: CLIApp, router: CommandRouter) -> None:
    """Attach all builtin slash commands to the router."""

    help_cmd.register(app, router)
    quit_cmd.register(app, router)
    settings.register(app, router)
    kb_cmd.register(app, router)
    toolkits.register(app, router)
    session.register(app, router)
    env.register(app, router)
    template.register(app, router)
    todo.register(app, router)
    logs.register(app, router)
    wallet.register(app, router)
    program.register(app, router)
    metadata_cmd.register(app, router)
    blueprint_cmd.register(app, router)
    new_cmd.register(app, router)
    init_cmd.register(app, router)
    deploy_cmd.register(app, router)


__all__ = ["register_builtin_commands"]
