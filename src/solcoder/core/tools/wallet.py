"""Wallet orchestration tools for SolCoder agents.

These tools let the agent pre-stage wallet flows while keeping
interactive confirmation (passphrase + final ack) with the user.
"""

from __future__ import annotations

from typing import Any

from solcoder.core.tools.base import Tool, ToolInvocationError, Toolkit, ToolResult


def _start_wallet_send_handler(payload: dict[str, Any]) -> ToolResult:
    destination = payload.get("destination")
    amount = payload.get("amount")

    if not isinstance(destination, str) or not destination.strip():
        raise ToolInvocationError("'destination' must be a non-empty string.")
    try:
        amount_value = float(amount)
    except (TypeError, ValueError):
        raise ToolInvocationError("'amount' must be a number (SOL).") from None
    if amount_value <= 0:
        raise ToolInvocationError("'amount' must be greater than zero.")

    summary_lines = [
        "Preparing SOL transfer:",
        f"Destination: {destination}",
        f"Amount: {amount_value:.3f} SOL",
        "The CLI will show a transaction summary next and require your",
        "passphrase and an explicit confirmation ('send') before broadcasting.",
    ]

    # Instruct the CLI to dispatch the wallet command interactively.
    # The command itself will handle summary + confirmation prompts.
    dispatch = f"/wallet send {destination} {amount_value:.9f}"
    return ToolResult(
        content="\n".join(summary_lines),
        summary="Wallet transfer prepared; awaiting user confirmation.",
        data={"dispatch_command": dispatch},
    )


def wallet_toolkit() -> Toolkit:
    send_tool = Tool(
        name="start_wallet_send",
        description=(
            "Pre-stage a SOL transfer to an address with a specified amount. "
            "The CLI will prompt the user with the transaction summary and require confirmation."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "destination": {
                    "type": "string",
                    "description": "Recipient address (base58).",
                },
                "amount": {
                    "type": "number",
                    "description": "Amount of SOL to send.",
                },
            },
            "required": ["destination", "amount"],
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        handler=_start_wallet_send_handler,
    )

    def _request_airdrop_handler(payload: dict[str, Any]) -> ToolResult:
        amount = payload.get("amount")
        if amount is None:
            amount_value = 2.0
        else:
            try:
                amount_value = float(amount)
            except (TypeError, ValueError):
                raise ToolInvocationError("'amount' must be a number (SOL).") from None
        if amount_value <= 0:
            raise ToolInvocationError("'amount' must be greater than zero.")

        lines = [
            f"Requesting a faucet airdrop: {amount_value:.3f} SOL.",
            "The CLI will submit the airdrop on devnet/testnet and wait",
            "for the balance to update before refreshing the status bar.",
        ]
        dispatch = f"/wallet airdrop {amount_value:.9f}"
        return ToolResult(
            content="\n".join(lines),
            summary=f"Airdrop {amount_value:.3f} SOL prepared.",
            data={"dispatch_command": dispatch, "suppress_preview": True},
        )

    airdrop_tool = Tool(
        name="request_airdrop",
        description=(
            "Request a faucet airdrop on devnet/testnet for the active wallet. "
            "Defaults to 2 SOL if 'amount' is not provided."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "amount": {
                    "type": "number",
                    "description": "Amount of SOL to request (default 2).",
                }
            },
            "required": [],
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        handler=_request_airdrop_handler,
    )
    return Toolkit(
        name="solcoder.wallet",
        version="1.0.0",
        description="Wallet orchestration helpers for agent-initiated flows.",
        tools=[send_tool, airdrop_tool],
    )


__all__ = ["wallet_toolkit"]
