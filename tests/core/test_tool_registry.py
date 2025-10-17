from __future__ import annotations

import pytest

from pathlib import Path

from solcoder.core.tool_registry import (
    Tool,
    ToolAlreadyRegisteredError,
    ToolNotFoundError,
    ToolRegistry,
    ToolRegistryError,
    ToolResult,
    build_default_registry,
)


def test_register_and_invoke_tool() -> None:
    registry = ToolRegistry()

    def handler(payload: dict[str, str]) -> ToolResult:
        return ToolResult(content=f"Echo: {payload['text']}")

    registry.register(
        Tool(
            name="echo",
            description="Echo tool",
            input_schema={},
            output_schema={},
            handler=handler,
        )
    )

    result = registry.invoke("echo", {"text": "hello"})
    assert result.content == "Echo: hello"


def test_duplicate_registration_raises() -> None:
    registry = ToolRegistry()
    tool = Tool("sample", "", {}, {}, lambda _: ToolResult(content="ok"))
    registry.register(tool)
    with pytest.raises(ToolAlreadyRegisteredError):
        registry.register(tool)


def test_unknown_tool() -> None:
    registry = ToolRegistry()
    with pytest.raises(ToolNotFoundError):
        registry.invoke("missing")


def test_handler_error_wrapped() -> None:
    registry = ToolRegistry()

    def handler(_payload: dict[str, str]) -> ToolResult:
        raise ValueError("boom")

    registry.register(Tool("broken", "", {}, {}, handler))
    with pytest.raises(ToolRegistryError):
        registry.invoke("broken", {})


def test_default_registry_contains_expected_tools() -> None:
    registry = build_default_registry()
    tool_names = set(registry.available_tools().keys())
    assert "generate_plan" in tool_names
    assert "prepare_code_steps" in tool_names
    assert "generate_review_checklist" in tool_names
    assert "create_deploy_checklist" in tool_names
    assert "collect_env_diagnostics" in tool_names
    assert "lookup_knowledge" in tool_names
    assert "execute_shell_command" in tool_names

    modules = registry.available_modules()
    assert "solcoder.planning" in modules
    assert modules["solcoder.planning"].tools[0].name == "generate_plan"


def test_command_run_executes_shell(tmp_path: Path) -> None:
    registry = build_default_registry()
    result = registry.invoke(
        "execute_shell_command",
        {"command": "echo hello", "cwd": str(tmp_path)},
    )
    assert "hello" in result.content
    assert result.data["returncode"] == 0
