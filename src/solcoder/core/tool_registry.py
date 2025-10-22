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
        previous_toolkit = self._toolkits.get(toolkit.name)
        previous_tools: list[str] = []
        if previous_toolkit is not None:
            if not overwrite:
                raise ToolkitAlreadyRegisteredError(
                    f"Toolkit '{toolkit.name}' already registered"
                )
            previous_tools = [tool.name for tool in previous_toolkit.tools]
            for tool_name in previous_tools:
                self.unregister(tool_name)

        registered: list[str] = []
        try:
            for tool in toolkit.tools:
                # Register tool by its short name
                self.register(tool, overwrite=overwrite)
                registered.append(tool.name)
                # Also register a namespaced alias: "<toolkit>.<tool>"
                alias_name = f"{toolkit.name}.{tool.name}"
                alias_tool = Tool(
                    name=alias_name,
                    description=tool.description,
                    input_schema=tool.input_schema,
                    output_schema=tool.output_schema,
                    handler=tool.handler,
                )
                try:
                    self.register(alias_tool, overwrite=False)
                    registered.append(alias_name)
                except ToolAlreadyRegisteredError:
                    # Ignore if an alias already exists
                    pass
        except Exception:
            for tool_name in registered:
                self.unregister(tool_name)
            if previous_toolkit is not None:
                for tool in previous_toolkit.tools:
                    self.register(tool, overwrite=True)
                self._toolkits[toolkit.name] = previous_toolkit
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
