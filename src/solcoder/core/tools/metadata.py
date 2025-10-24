"""Agent tools for metadata flows (upload + set)."""

from __future__ import annotations

from typing import Any
import shlex

from solcoder.core.tools.base import Tool, Toolkit, ToolResult, ToolInvocationError


def _upload_handler(payload: dict[str, Any]) -> ToolResult:
    file = payload.get("file")
    directory = payload.get("directory")
    if bool(file) == bool(directory):
        raise ToolInvocationError("Provide exactly one of 'file' or 'directory'.")
    if file:
        cmd = shlex.join(["/metadata", "upload", "--file", str(file)])
        return ToolResult(
            content=f"Upload file via: {cmd}",
            summary="Upload file",
            data={"dispatch_command": cmd, "suppress_preview": True},
        )
    else:
        cmd = shlex.join(["/metadata", "upload", "--dir", str(directory)])
        return ToolResult(
            content=f"Upload directory via: {cmd}",
            summary="Upload directory",
            data={"dispatch_command": cmd, "suppress_preview": True},
        )


def _set_handler(payload: dict[str, Any]) -> ToolResult:
    mint = payload.get("mint")
    name = payload.get("name")
    symbol = payload.get("symbol")
    uri = payload.get("uri")
    if not all(isinstance(x, str) and x.strip() for x in (mint, name, symbol, uri)):
        raise ToolInvocationError("'mint', 'name', 'symbol', and 'uri' are required.")
    parts = [
        "/metadata",
        "set",
        "--mint",
        str(mint),
        "--name",
        str(name),
        "--symbol",
        str(symbol),
        "--uri",
        str(uri),
    ]
    r_bps = payload.get("royalty_bps")
    if r_bps is not None:
        parts += ["--royalty-bps", str(r_bps)]
    creators = payload.get("creators")
    if creators:
        parts += ["--creators", str(creators)]
    collection = payload.get("collection")
    if collection:
        parts += ["--collection", str(collection)]
    cmd = shlex.join(parts)
    return ToolResult(
        content=f"Stage metadata set via: {cmd}",
        summary="Set metadata (staged)",
        data={"dispatch_command": cmd, "suppress_preview": False},
    )


def metadata_toolkit() -> Toolkit:
    upload = Tool(
        name="upload",
        description="Upload assets (file or directory) for metadata and return local URIs.",
        input_schema={
            "type": "object",
            "properties": {
                "file": {"type": "string"},
                "directory": {"type": "string"},
            },
            "required": [],
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        handler=_upload_handler,
    )
    set_tool = Tool(
        name="set",
        description="Set metadata for a mint (staged local write; future on-chain integration).",
        input_schema={
            "type": "object",
            "properties": {
                "mint": {"type": "string"},
                "name": {"type": "string"},
                "symbol": {"type": "string"},
                "uri": {"type": "string"},
                "royalty_bps": {"type": ["integer", "null"]},
                "creators": {"type": ["string", "null"]},
                "collection": {"type": ["string", "null"]},
            },
            "required": ["mint", "name", "symbol", "uri"],
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        handler=_set_handler,
    )
    return Toolkit(
        name="solcoder.metadata",
        version="1.0.0",
        description="Tools for staging metadata upload and set flows.",
        tools=[upload, set_tool],
    )


__all__ = ["metadata_toolkit"]
