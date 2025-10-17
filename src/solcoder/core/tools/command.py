from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from solcoder.core.tools.base import Tool, ToolInvocationError, Toolkit, ToolResult


def _command_handler(payload: dict[str, Any]) -> ToolResult:
    command = payload.get("command")
    if not command or not isinstance(command, str):
        raise ToolInvocationError("Payload must include 'command' as a string.")

    cwd_value = payload.get("cwd")
    cwd_path = Path(cwd_value).expanduser() if isinstance(cwd_value, str) else None
    timeout = payload.get("timeout")
    try:
        timeout_value = float(timeout) if timeout is not None else 15.0
    except (TypeError, ValueError):
        raise ToolInvocationError("Timeout must be numeric if provided.") from None

    try:
        completed = subprocess.run(  # noqa: S602,S603,S607 - controlled inputs
            command,
            shell=True,  # noqa: S602
            check=False,
            capture_output=True,
            text=True,
            cwd=cwd_path,
            timeout=timeout_value,
        )
    except subprocess.TimeoutExpired as exc:  # type: ignore[attr-defined]
        raise ToolInvocationError(f"Command timed out after {timeout_value} seconds.") from exc
    except FileNotFoundError as exc:
        raise ToolInvocationError(f"Working directory not found: {cwd_path}") from exc
    except Exception as exc:  # noqa: BLE001
        raise ToolInvocationError(f"Failed to execute command: {exc}") from exc

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    content_lines = [
        f"$ {command}",
        f"(exit code {completed.returncode})",
        "",
        stdout or "(no stdout)",
    ]
    if stderr:
        content_lines.extend(["", "stderr:", stderr])

    summary = f"Command exited with {completed.returncode}"
    return ToolResult(
        content="\n".join(content_lines),
        summary=summary,
        data={
            "command": command,
            "returncode": completed.returncode,
            "stdout": stdout,
            "stderr": stderr,
        },
    )


def command_toolkit() -> Toolkit:
    tool = Tool(
        name="execute_shell_command",
        description="Run a shell command within the SolCoder workspace and capture output.",
        input_schema={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute.",
                },
                "cwd": {
                    "type": "string",
                    "description": "Optional working directory for command execution.",
                },
                "timeout": {
                    "type": "number",
                    "description": "Optional timeout in seconds (default 15).",
                },
            },
            "required": ["command"],
        },
        output_schema={"type": "object"},
        handler=_command_handler,
    )
    return Toolkit(
        name="solcoder.command",
        version="1.0.0",
        description="Command execution utilities for SolCoder agents.",
        tools=[tool],
    )
