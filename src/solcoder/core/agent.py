"""Agent loop schemas and manifest helpers."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, model_validator

from .tool_registry import ToolRegistry


class AgentMessageError(RuntimeError):
    """Raised when an agent directive payload fails validation."""


class AgentToolCall(BaseModel):
    """Represents a tool invocation requested by the LLM."""

    name: str
    args: dict[str, Any] = Field(default_factory=dict)


class AgentDirective(BaseModel):
    """Pydantic model describing LLM directives for the agent loop."""

    type: Literal["plan", "tool_request", "reply", "cancel"]  # tool_result reserved for orchestrator
    message: str | None = None
    step_title: str | None = None
    tool: AgentToolCall | None = None
    steps: list[str] | None = None

    @model_validator(mode="after")
    def _validate_payload(self) -> AgentDirective:
        if self.type == "plan" and not self.steps:
            raise ValueError("plan directives must include at least one step")
        if self.type == "tool_request":
            if self.tool is None:
                raise ValueError("tool_request directives must include a tool object")
            if not self.step_title:
                raise ValueError("tool_request directives must include a step_title")
        if self.type == "reply" and not self.message:
            raise ValueError("reply directives must include a message")
        return self


class AgentToolResult(BaseModel):
    """Message emitted back to the LLM after running a tool."""

    type: Literal["tool_result"] = "tool_result"
    tool_name: str
    step_title: str
    status: Literal["success", "error"]
    output: str
    data: Any | None = None


@dataclass(slots=True)
class ToolManifestTool:
    """Manifest entry for a single tool."""

    name: str
    description: str
    input_schema: dict[str, Any]
    required: list[str]


@dataclass(slots=True)
class ToolManifestToolkit:
    """Manifest entry describing a toolkit and its tools."""

    name: str
    description: str
    version: str
    tools: list[ToolManifestTool]


def build_tool_manifest(registry: ToolRegistry) -> list[ToolManifestToolkit]:
    """Serialise the registry to a manifest suitable for LLM prompts."""
    manifest: list[ToolManifestToolkit] = []
    for toolkit in sorted(registry.available_toolkits().values(), key=lambda tk: tk.name):
        tools = []
        for tool in toolkit.tools:
            required_fields = tool.input_schema.get("required")
            required_list = list(required_fields) if isinstance(required_fields, list) else []
            tools.append(
                ToolManifestTool(
                    name=tool.name,
                    description=tool.description,
                    input_schema=tool.input_schema,
                    required=required_list,
                )
            )
        manifest.append(
            ToolManifestToolkit(
                name=toolkit.name,
                description=toolkit.description,
                version=toolkit.version,
                tools=tools,
            )
        )
    return manifest


def manifest_to_prompt_section(toolkits: Iterable[ToolManifestToolkit]) -> str:
    """Render the manifest as compact JSON for the system prompt."""
    serialisable: list[dict[str, Any]] = []
    for toolkit in toolkits:
        serialisable.append(
            {
                "toolkit": toolkit.name,
                "version": toolkit.version,
                "description": toolkit.description,
                "tools": [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "input_schema": tool.input_schema,
                        "required": tool.required,
                    }
                    for tool in toolkit.tools
                ],
            }
        )
    return json.dumps(serialisable, separators=(",", ":"))


def parse_agent_directive(raw_payload: str) -> AgentDirective:
    """Parse and validate an LLM directive payload."""
    try:
        data = json.loads(raw_payload)
    except json.JSONDecodeError as exc:  # pragma: no cover - handled by caller retry logic
        raise AgentMessageError(f"Invalid JSON: {exc}") from exc

    try:
        return AgentDirective.model_validate(data)
    except ValidationError as exc:
        raise AgentMessageError(str(exc)) from exc


__all__ = [
    "AgentDirective",
    "AgentToolCall",
    "AgentToolResult",
    "AgentMessageError",
    "ToolManifestToolkit",
    "ToolManifestTool",
    "build_tool_manifest",
    "manifest_to_prompt_section",
    "parse_agent_directive",
]
