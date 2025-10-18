"""Template-related commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

from solcoder.cli.template_utils import parse_template_tokens
from solcoder.cli.types import CommandResponse, CommandRouter, SlashCommand
from solcoder.core import TemplateError, available_templates, render_template

if TYPE_CHECKING:  # pragma: no cover
    from solcoder.cli.app import CLIApp


def register(app: CLIApp, router: CommandRouter) -> None:
    """Register the /template command."""

    def handle(app: CLIApp, args: list[str]) -> CommandResponse:
        if not args:
            templates = ", ".join(available_templates()) or "(none)"
            return CommandResponse(
                messages=[
                    (
                        "system",
                        "Usage: /template <name> <destination> [--program <name>] [--author <pubkey>] [--program-id <id>] [--cluster <cluster>] [--force]\n"
                        f"Available templates: {templates}",
                    )
                ]
            )

        template_name = args[0].lower()
        if template_name not in available_templates():
            app.log_event("build", f"Unknown template '{template_name}'", severity="warning")
            return CommandResponse(
                messages=[(
                    "system",
                    f"Unknown template '{template_name}'. Available: {', '.join(available_templates()) or '(none)'}",
                )]
            )

        defaults = app._default_template_metadata()
        options, error = parse_template_tokens(template_name, args[1:], defaults)
        if error:
            app.log_event("build", f"Template option parsing failed: {error}", severity="error")
            return CommandResponse(messages=[("system", error)])
        if options is None:
            app.log_event("build", "Template option parsing returned no result", severity="error")
            return CommandResponse(messages=[("system", "Unable to parse template options.")])
        try:
            output = render_template(options)
        except TemplateError as exc:
            app.log_event("build", f"Template render failed: {exc}", severity="error")
            return CommandResponse(messages=[("system", f"Template error: {exc}")])

        message = f"Template '{template_name}' rendered to {output}"
        app.log_event("build", f"Template '{template_name}' rendered to {output}")
        tool_calls = [
            {
                "type": "command",
                "name": "/template",
                "status": "success",
                "summary": f"{template_name} → {output}",
            }
        ]
        return CommandResponse(messages=[("system", message)], tool_calls=tool_calls)

    router.register(SlashCommand("template", handle, "Template scaffolding commands"))


__all__ = ["register"]
