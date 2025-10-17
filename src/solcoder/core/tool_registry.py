"""Tool registry for deterministic agent actions."""

from __future__ import annotations

from typing import Any

from solcoder.core.tools import DEFAULT_MODULE_FACTORIES
from solcoder.core.tools.base import (
    Module,
    ModuleAlreadyRegisteredError,
    Tool,
    ToolAlreadyRegisteredError,
    ToolInvocationError,
    ToolNotFoundError,
    ToolRegistryError,
    ToolResult,
)


class ToolRegistry:
    """Stores tool handlers grouped by modules."""

    def __init__(self, modules: list[Module] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        self._modules: dict[str, Module] = {}
        if modules:
            for module in modules:
                self.add_module(module)

    def add_module(self, module: Module, *, overwrite: bool = False) -> None:
        if not overwrite and module.name in self._modules:
            raise ModuleAlreadyRegisteredError(f"Module '{module.name}' already registered")
        self._modules[module.name] = module
        for tool in module.tools:
            self.register(tool, overwrite=overwrite)

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

    def available_modules(self) -> dict[str, Module]:
        return dict(self._modules)

    def invoke(self, name: str, payload: dict[str, Any] | None = None) -> ToolResult:
        tool = self.get(name)
        try:
            return tool.handler(payload or {})
        except ToolInvocationError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ToolInvocationError(f"Tool '{name}' failed: {exc}") from exc


def build_default_registry() -> ToolRegistry:
    """Return a registry pre-populated with the built-in tools."""
    modules = [factory() for factory in DEFAULT_MODULE_FACTORIES]
    return ToolRegistry(modules=modules)


__all__ = [
    "ToolRegistry",
    "Tool",
    "ToolResult",
    "ToolRegistryError",
    "ToolNotFoundError",
    "ToolAlreadyRegisteredError",
    "ToolInvocationError",
    "Module",
    "ModuleAlreadyRegisteredError",
    "build_default_registry",
]
