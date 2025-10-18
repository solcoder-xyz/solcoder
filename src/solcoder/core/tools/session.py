"""Session management tools for SolCoder."""

from __future__ import annotations

from typing import Any

from solcoder.core.tools.base import Tool, ToolInvocationError, Toolkit, ToolResult


def _quit_handler(payload: dict[str, Any]) -> ToolResult:
    custom_message = payload.get("message")
    if custom_message and not isinstance(custom_message, str):
        raise ToolInvocationError("Optional 'message' must be a string.")

    goodbye = custom_message or "Shutting down SolCoder. Come back soon!"
    return ToolResult(
        content=goodbye,
        summary="CLI session marked for shutdown.",
        data={
            "exit_app": True,
            "farewell": goodbye,
        },
    )


def session_toolkit() -> Toolkit:
    """Session lifecycle utilities."""

    quit_tool = Tool(
        name="quit",
        description=(
            "Gracefully end the interactive SolCoder session. "
            "Use when the user requests to exit (e.g., 'bye', 'quit', 'close the app')."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Optional farewell message to display when exiting.",
                },
            },
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "exit_app": {"type": "boolean"},
                "farewell": {"type": "string"},
            },
            "required": ["exit_app"],
        },
        handler=_quit_handler,
    )

    return Toolkit(
        name="solcoder.session",
        version="1.0.0",
        description="Session lifecycle controls for SolCoder.",
        tools=[quit_tool],
    )


__all__ = ["session_toolkit"]
