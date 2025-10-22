"""Tools for token operations exposed to the agent."""

from __future__ import annotations

from typing import Any

from solcoder.core.tools.base import Tool, Toolkit, ToolResult, ToolInvocationError


def _create_quick_token_handler(payload: dict[str, Any]) -> ToolResult:
    # Validate inputs
    decimals = payload.get("decimals")
    supply = payload.get("supply")
    cluster = payload.get("cluster")
    if decimals is None or supply is None:
        raise ToolInvocationError("'decimals' and 'supply' are required.")
    try:
        dval = int(decimals)
    except Exception:
        raise ToolInvocationError("'decimals' must be an integer between 0 and 9.")
    if dval < 0 or dval > 9:
        raise ToolInvocationError("'decimals' must be between 0 and 9.")

    # Prepare CLI dispatch. The CLI will prompt the user for passphrase and a final confirmation.
    parts = [
        "/new",
        "token",
        "--quick",
        "--decimals",
        str(dval),
        "--supply",
        str(supply),
    ]
    if isinstance(cluster, str) and cluster.strip():
        parts.extend(["--cluster", cluster.strip()])
    dispatch = " ".join(parts)

    summary = (
        "Prepare quick SPL token mint (Token-2022):\n"
        f"  Decimals: {dval}\n"
        f"  Initial supply: {supply}\n"
        "The CLI will show a summary and request your passphrase and a final 'mint' confirmation."
    )
    return ToolResult(
        content=summary,
        summary="Quick token mint prepared; awaiting confirmation.",
        data={"dispatch_command": dispatch},
    )


def token_toolkit() -> Toolkit:
    create_quick_token = Tool(
        name="create_quick_token",
        description=(
            "Prepare a quick SPL Token-2022 mint without the full wizard. "
            "Prompts the user only for confirmation and passphrase."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "decimals": {"type": "integer", "minimum": 0, "maximum": 9},
                "supply": {"type": ["number", "string"], "description": "Initial supply as UI amount."},
                "cluster": {"type": "string", "description": "Optional cluster hint (devnet/testnet/mainnet-beta)."},
            },
            "required": ["decimals", "supply"],
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        handler=_create_quick_token_handler,
    )
    return Toolkit(
        name="solcoder.token",
        version="1.0.0",
        description="Token helpers for agent-initiated quick mints.",
        tools=[create_quick_token],
    )


__all__ = ["token_toolkit"]
