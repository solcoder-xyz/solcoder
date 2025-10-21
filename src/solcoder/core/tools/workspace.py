"""Workspace management tools (e.g., Anchor init)."""

from __future__ import annotations

from typing import Any
import shlex

from solcoder.core.tools.base import Tool, ToolInvocationError, Toolkit, ToolResult


def _init_anchor_handler(payload: dict[str, Any]) -> ToolResult:
    directory = payload.get("directory")
    name = payload.get("name")
    force = payload.get("force", False)
    offline = payload.get("offline", False)

    parts: list[str] = ["/init"]
    if isinstance(directory, str) and directory.strip():
        parts.append(directory)
    if isinstance(name, str) and name.strip():
        parts += ["--name", name]
    if bool(force):
        parts.append("--force")
    if bool(offline):
        parts.append("--offline")
    cmd = " ".join(shlex.quote(p) for p in parts)

    return ToolResult(
        content=f"Initializing Anchor workspace via: {cmd}",
        summary="Initialize Anchor workspace",
        data={"dispatch_command": cmd, "suppress_preview": True},
    )


def workspace_toolkit() -> Toolkit:
    return Toolkit(
        name="solcoder.workspace",
        version="1.0.0",
        description="Workspace utilities for initializing Anchor projects.",
        tools=[
            Tool(
                name="init_anchor_workspace",
                description=(
                    "Initialize an Anchor workspace (optionally in DIRECTORY). "
                    "Args: directory, name, force (bool), offline (bool)."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "directory": {"type": "string"},
                        "name": {"type": "string"},
                        "force": {"type": "boolean"},
                        "offline": {"type": "boolean"},
                    },
                    "required": [],
                },
                output_schema={"type": "object"},
                handler=_init_anchor_handler,
            )
        ],
    )


__all__ = ["workspace_toolkit"]

