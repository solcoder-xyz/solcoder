"""Tool registry for deterministic agent actions."""

from __future__ import annotations

from typing import Any

from solcoder.core.tools import DEFAULT_TOOLKIT_FACTORIES
from solcoder.core.tools.base import (
    Tool,
    ToolAlreadyRegisteredError,
    ToolInvocationError,
    Toolkit,
    ToolkitAlreadyRegisteredError,
    ToolNotFoundError,
    ToolRegistryError,
    ToolResult,
)


class ToolRegistry:
    """Stores tool handlers grouped by toolkits."""

    def __init__(self, toolkits: list[Toolkit] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        self._toolkits: dict[str, Toolkit] = {}
        if toolkits:
            for toolkit in toolkits:
                self.add_toolkit(toolkit)

    def add_toolkit(self, toolkit: Toolkit, *, overwrite: bool = False) -> None:
        if not overwrite and toolkit.name in self._toolkits:
            raise ToolkitAlreadyRegisteredError(f"Toolkit '{toolkit.name}' already registered")
        registered: list[str] = []
        try:
            for tool in toolkit.tools:
                self.register(tool, overwrite=overwrite)
                registered.append(tool.name)
        except Exception:
            for tool_name in registered:
                self.unregister(tool_name)
            raise
        self._toolkits[toolkit.name] = toolkit

    def register(self, tool: Tool, *, overwrite: bool = False) -> None:
        if not overwrite and tool.name in self._tools:
            raise ToolAlreadyRegisteredError(f"Tool '{tool.name}' already registered")
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ToolNotFoundError(f"Unknown tool '{name}'") from exc

    def available_tools(self) -> dict[str, Tool]:
        return dict(self._tools)

    def available_toolkits(self) -> dict[str, Toolkit]:
        return dict(self._toolkits)

    def invoke(self, name: str, payload: dict[str, Any] | None = None) -> ToolResult:
        tool = self.get(name)
        try:
            return tool.handler(payload or {})
        except ToolInvocationError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ToolInvocationError(f"Tool '{name}' failed: {exc}") from exc


def build_default_registry() -> ToolRegistry:
    """Return a registry pre-populated with the built-in toolkits."""
    toolkits = [factory() for factory in DEFAULT_TOOLKIT_FACTORIES]
    return ToolRegistry(toolkits=toolkits)


__all__ = [
    "ToolRegistry",
    "Tool",
    "ToolResult",
    "ToolRegistryError",
    "ToolNotFoundError",
    "ToolAlreadyRegisteredError",
    "ToolInvocationError",
    "Toolkit",
    "ToolkitAlreadyRegisteredError",
    "build_default_registry",
]
