"""Agent tools for on-chain program interaction (inspect + prepare call)."""

from __future__ import annotations

from typing import Any
import json
import shlex

from solcoder.core.tools.base import Tool, ToolInvocationError, Toolkit, ToolResult


def _inspect_handler(payload: dict[str, Any]) -> ToolResult:
    program_id = payload.get("program_id")
    if not isinstance(program_id, str) or not program_id.strip():
        raise ToolInvocationError("'program_id' must be a non-empty string.")
    return ToolResult(
        content=f"Inspecting program {program_id}…",
        summary="Program inspection requested.",
        data={"dispatch_command": f"/program inspect {program_id}", "suppress_preview": True},
    )


def _prepare_call_handler(payload: dict[str, Any]) -> ToolResult:
    program_id = payload.get("program_id")
    method = payload.get("method")
    args = payload.get("args")
    accounts = payload.get("accounts")
    if not isinstance(program_id, str) or not program_id.strip():
        raise ToolInvocationError("'program_id' must be a non-empty string.")
    if method is not None and not isinstance(method, str):
        raise ToolInvocationError("'method' must be a string if provided.")
    if args is not None and not isinstance(args, (dict, list)):
        raise ToolInvocationError("'args' must be an object or array if provided.")
    if accounts is not None and not isinstance(accounts, dict):
        raise ToolInvocationError("'accounts' must be an object mapping names to addresses if provided.")

    summary_lines = [
        "Preparing program call:",
        f"Program: {program_id}",
        f"Method: {method or '(choose in wizard)'}",
    ]
    parts = ["/program", "call", program_id]
    if method:
        parts += ["--method", method]
    if args is not None:
        try:
            args_json = json.dumps(args, separators=(",", ":"))
        except Exception as exc:  # noqa: BLE001
            raise ToolInvocationError(f"Unable to serialize 'args' to JSON: {exc}") from exc
        parts += ["--args-json", args_json]
    if accounts is not None:
        try:
            accounts_json = json.dumps(accounts, separators=(",", ":"))
        except Exception as exc:  # noqa: BLE001
            raise ToolInvocationError(f"Unable to serialize 'accounts' to JSON: {exc}") from exc
        parts += ["--accounts-json", accounts_json]
    cmd = " ".join(shlex.quote(p) for p in parts)
    return ToolResult(
        content="\n".join(summary_lines),
        summary="Program call prepared; awaiting confirmation.",
        data={"dispatch_command": cmd, "suppress_preview": True},
    )


def program_toolkit() -> Toolkit:
    return Toolkit(
        name="solcoder.program",
        version="1.0.0",
        description="Program interaction helpers for inspection and call pre-staging.",
        tools=[
            Tool(
                name="inspect_program",
                description="Inspect an on-chain program (Anchor-first; falls back to SPL catalog).",
                input_schema={
                    "type": "object",
                    "properties": {
                        "program_id": {"type": "string", "description": "Program public key (base58)."}
                    },
                    "required": ["program_id"],
                },
                output_schema={"type": "object"},
                handler=_inspect_handler,
            ),
            Tool(
                name="prepare_program_call",
                description="Pre-stage a call to an on-chain program; CLI will prompt for confirmation before sending.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "program_id": {"type": "string"},
                        "method": {"type": "string"},
                        "args": {"type": ["object", "array"]},
                        "accounts": {"type": "object"},
                    },
                    "required": ["program_id"],
                },
                output_schema={"type": "object"},
                handler=_prepare_call_handler,
            ),
        ],
    )


__all__ = ["program_toolkit"]
