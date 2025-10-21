"""Blueprint scaffolding tool to hand off file creation to the CLI via dispatch."""

from __future__ import annotations

from typing import Any
import json
import shlex

from solcoder.core.tools.base import Tool, ToolInvocationError, Toolkit, ToolResult


def _scaffold_handler(payload: dict[str, Any]) -> ToolResult:
    key = payload.get("blueprint_key")
    target_dir = payload.get("target_dir")
    workspace_root = payload.get("workspace_root")
    answers = payload.get("answers") or {}
    if not isinstance(key, str) or not key:
        raise ToolInvocationError("'blueprint_key' is required")
    if not isinstance(target_dir, str) or not target_dir:
        raise ToolInvocationError("'target_dir' is required")
    if not isinstance(answers, (dict, list)):
        raise ToolInvocationError("'answers' must be an object or array")
    parts = ["/blueprint", "scaffold", "--key", key, "--target", target_dir]
    if isinstance(workspace_root, str) and workspace_root:
        parts += ["--workspace", workspace_root]
    try:
        answers_json = json.dumps(answers, separators=(",", ":"))
    except Exception as exc:  # noqa: BLE001
        raise ToolInvocationError(f"Unable to serialize answers: {exc}") from exc
    parts += ["--answers-json", answers_json]
    cmd = " ".join(shlex.quote(p) for p in parts)
    return ToolResult(
        content=f"Scaffolding blueprint via: {cmd}",
        summary="Scaffold blueprint",
        data={"dispatch_command": cmd, "suppress_preview": True},
    )


def blueprint_toolkit() -> Toolkit:
    return Toolkit(
        name="solcoder.blueprint",
        version="1.0.0",
        description="Agent handoff for blueprint scaffolding.",
        tools=[
            Tool(
                name="scaffold_blueprint",
                description=(
                    "Scaffold files for a blueprint by dispatching a CLI command. "
                    "Args: blueprint_key, target_dir, workspace_root?, answers (object)."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "blueprint_key": {"type": "string"},
                        "target_dir": {"type": "string"},
                        "workspace_root": {"type": "string"},
                        "answers": {"type": "object"}
                    },
                    "required": ["blueprint_key", "target_dir", "answers"],
                },
                output_schema={"type": "object"},
                handler=_scaffold_handler,
            )
        ],
    )


__all__ = ["blueprint_toolkit"]

