from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pytest

from solcoder.core.agent import build_tool_manifest
from solcoder.core.env_diag import DiagnosticResult
from solcoder.core.tool_registry import (
    Tool,
    ToolAlreadyRegisteredError,
    Toolkit,
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
    assert "knowledge_base_lookup" in tool_names
    assert "execute_shell_command" in tool_names

    toolkits = registry.available_toolkits()
    assert "solcoder.planning" in toolkits
    assert toolkits["solcoder.planning"].tools[0].name == "generate_plan"


def test_command_run_executes_shell(tmp_path: Path) -> None:
    registry = build_default_registry()
    result = registry.invoke(
        "execute_shell_command",
        {"command": "echo hello", "cwd": str(tmp_path)},
    )
    assert "hello" in result.content
    assert result.data["returncode"] == 0


def test_knowledge_tool_invokes_client(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = build_default_registry()
    tool = registry.get("knowledge_base_lookup")
    assert tool.name == "knowledge_base_lookup"

    calls: list[str] = []

    class FakeClient:
        def query(self, question: str):
            calls.append(question)
            return type("Answer", (), {"text": "Solana answer", "citations": [{"title": "Doc", "url": "http://docs"}]})

    monkeypatch.setattr("solcoder.core.tools.knowledge._KB_CLIENT", FakeClient())
    result = registry.invoke("knowledge_base_lookup", {"query": "Test query"})

    assert calls == ["Test query"]
    assert "Solana answer" in result.content
    assert "Doc" in result.content
    assert result.data["query"] == "Test query"


def test_diagnostics_tool_serializes_dataclass(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = build_default_registry()
    fake_results = [
        DiagnosticResult(
            name="Tool A",
            status="ok",
            found=True,
            version="1.2.3",
            remediation=None,
        )
    ]

    monkeypatch.setattr(
        "solcoder.core.tools.diagnostics.collect_environment_diagnostics",
        lambda: fake_results,
    )

    result = registry.invoke("collect_env_diagnostics")

    assert result.summary == "1 of 1 tools detected"
    assert result.data == [asdict(fake_results[0])]


def test_module_registration_rolls_back_on_tool_conflict() -> None:
    registry = build_default_registry()
    duplicate_tool = Tool(
        name="generate_plan",  # already present in default registry
        description="conflict",
        input_schema={},
        output_schema={},
        handler=lambda _: ToolResult(content="noop"),
    )
    conflicting_toolkit = Toolkit(
        name="custom.module",
        version="1.0.0",
        description="Conflicting tools",
        tools=[duplicate_tool],
    )

    with pytest.raises(ToolAlreadyRegisteredError):
        registry.add_toolkit(conflicting_toolkit)

    toolkits = registry.available_toolkits()
    assert "custom.module" not in toolkits
    assert registry.get("generate_plan")  # original tool still available


def test_manifest_contains_required_fields() -> None:
    registry = build_default_registry()
    manifest = build_tool_manifest(registry)

    planning = next(tk for tk in manifest if tk.name == "solcoder.planning")
    assert planning.tools[0].required == ["goal"]

    diagnostics = next(tk for tk in manifest if tk.name == "solcoder.diagnostics")
    assert diagnostics.tools[0].required == []
