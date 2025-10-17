"""Shared types for tool implementations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


class ToolRegistryError(RuntimeError):
    """Base error for tool registry failures."""


class ToolAlreadyRegisteredError(ToolRegistryError):
    """Raised when attempting to register a tool with a duplicate name."""


class ToolNotFoundError(ToolRegistryError):
    """Raised when invoking an unknown tool."""


class ToolInvocationError(ToolRegistryError):
    """Raised when a tool handler fails."""


class ToolkitAlreadyRegisteredError(ToolRegistryError):
    """Raised when attempting to register a toolkit twice."""


@dataclass(slots=True)
class ToolResult:
    """Represents the outcome of invoking a tool."""

    content: str
    summary: str | None = None
    data: Any | None = None


@dataclass(slots=True)
class Tool:
    """Metadata for a registered tool."""

    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], ToolResult]


@dataclass(slots=True)
class Toolkit:
    """Groups related tools together."""

    name: str
    version: str
    description: str
    tools: list[Tool]
