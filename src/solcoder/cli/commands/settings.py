"""Settings command for SolCoder CLI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from solcoder.cli.types import CommandResponse, CommandRouter, SlashCommand

if TYPE_CHECKING:  # pragma: no cover
    from solcoder.cli.app import CLIApp


def register(app: CLIApp, router: CommandRouter) -> None:
    """Register the /settings command."""

    def handle(app: CLIApp, args: list[str]) -> CommandResponse:
        metadata = app.session_context.metadata
        if not args:
            project_display = metadata.active_project or "unknown"
            wallet_display = metadata.wallet_status or "---"
            spend_display = f"{metadata.spend_amount:.2f} SOL"
            lines = [
                f"Active project:\t{project_display}",
                f"Wallet:\t\t{wallet_display}",
                f"Session spend:\t{spend_display}",
            ]
            return CommandResponse(messages=[("system", "\n".join(lines))])

        subcommand, *values = args

        if subcommand.lower() == "wallet":
            if not values:
                return CommandResponse(
                    messages=[("system", "Usage: /settings wallet <label-or-address>")],
                )
            metadata.wallet_status = " ".join(values)
            return CommandResponse(messages=[("system", f"Wallet updated to '{metadata.wallet_status}'.")])

        if subcommand.lower() == "spend":
            if not values:
                return CommandResponse(messages=[("system", "Usage: /settings spend <amount-sol>")])
            try:
                amount = float(values[0])
            except ValueError:
                return CommandResponse(messages=[("system", "Spend amount must be a number (SOL).")])
            if amount < 0:
                return CommandResponse(messages=[("system", "Spend amount cannot be negative.")])
            metadata.spend_amount = amount
            return CommandResponse(messages=[("system", f"Session spend set to {metadata.spend_amount:.2f} SOL.")])

        if subcommand.lower() == "model":
            if not values:
                return CommandResponse(
                    messages=[("system", "Usage: /settings model <gpt-5|gpt-5-codex>")],
                )
            choice = values[0].strip().lower()
            allowed_models = {"gpt-5", "gpt-5-codex"}
            if choice not in allowed_models:
                return CommandResponse(
                    messages=[(
                        "system",
                        "Supported models: gpt-5, gpt-5-codex.",
                    )]
                )
            canonical_choice = "gpt-5-codex" if choice == "gpt-5-codex" else "gpt-5"
            app._update_llm_settings(model=canonical_choice)
            return CommandResponse(messages=[("system", f"LLM model updated to {canonical_choice}.")])

        if subcommand.lower() in {"reasoning", "effort"}:
            if not values:
                return CommandResponse(
                    messages=[("system", "Usage: /settings reasoning <low|medium|high>")],
                )
            choice = values[0].strip().lower()
            allowed_efforts = {"low", "medium", "high"}
            if choice not in allowed_efforts:
                return CommandResponse(
                    messages=[("system", "Reasoning effort must be one of: low, medium, high.")]
                )
            app._update_llm_settings(reasoning=choice)
            return CommandResponse(messages=[("system", f"Reasoning effort set to {choice}.")])

        return CommandResponse(
            messages=[
                (
                    "system",
                    "Unknown settings option. Use `/settings`, `/settings wallet <value>`, `/settings spend <amount>`, `/settings model <gpt-5|gpt-5-codex>`, or `/settings reasoning <low|medium|high>`.",
                )
            ]
        )

    router.register(SlashCommand("settings", handle, "View or update session settings"))


__all__ = ["register"]
