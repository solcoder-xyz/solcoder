import importlib
import json
import os
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from rich.console import Console

from solcoder.core.agent_loop import AGENT_PLAN_ACK
from solcoder.cli.app import CLIApp
from solcoder.cli.stub_llm import StubLLM
from solcoder.cli.commands import env as env_commands
from solcoder.core.config import ConfigContext, ConfigManager, SolCoderConfig
from solcoder.core.env_diag import DiagnosticResult
from solcoder.core.llm import LLMResponse
from solcoder.core.tool_registry import Tool, ToolResult, build_default_registry
from solcoder.session import SessionManager
from solcoder.solana import WalletManager

cli_app_module = importlib.import_module("solcoder.cli.app")


class RPCStub:
    def __init__(self, balances: list[float] | None = None) -> None:
        self.balances = balances or []

    def get_balance(self, _public_key: str) -> float:
        if self.balances:
            return self.balances.pop(0)
        return 0.0


class ScriptedLLM:
    """LLM stub that replays scripted JSON directives."""

    def __init__(self, script: list[dict[str, Any]]) -> None:
        self.script = script
        self.calls: list[str] = []
        self.model = "scripted-model"
        self.reasoning_effort = "medium"

    def stream_chat(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        history: Sequence[dict[str, str]] | None = None,
        on_chunk: Callable[[str], None] | None = None,
    ) -> LLMResponse:
        if not self.script:
            raise AssertionError("No scripted responses remaining")
        entry = self.script.pop(0)
        expect = entry.get("expect")
        if expect:
            expect(prompt)

        reply_value = entry["reply"]
        if callable(reply_value):
            reply_value = reply_value(prompt)
        reply = json.dumps(reply_value) if isinstance(reply_value, dict) else str(reply_value)

        self.calls.append(prompt)
        if on_chunk:
            on_chunk(reply)

        token_usage = entry.get("token_usage")
        if token_usage is None:
            in_tokens = max(len(prompt.split()), 1)
            out_tokens = max(len(reply.split()), 1)
            token_usage = {
                "input_tokens": in_tokens,
                "output_tokens": out_tokens,
                "total_tokens": in_tokens + out_tokens,
            }

        return LLMResponse(
            text=reply,
            latency_seconds=entry.get("latency", 0.0),
            finish_reason=entry.get("finish_reason"),
            token_usage=token_usage,
            cached=entry.get("cached", True),
        )

    def update_settings(self, *, model: str | None = None, reasoning_effort: str | None = None) -> None:
        if model:
            self.model = model
        if reasoning_effort:
            self.reasoning_effort = reasoning_effort


def expect_equals(expected: str) -> Callable[[str], None]:
    def _check(actual: str) -> None:
        assert actual == expected, f"Expected prompt '{expected}' but received '{actual}'"

    return _check


def expect_tool_result(tool_name: str) -> Callable[[str], None]:
    def _check(actual: str) -> None:
        payload = json.loads(actual)
        assert payload["type"] == "tool_result"
        assert payload["tool_name"] == tool_name

    return _check


def expect_contains(fragment: str) -> Callable[[str], None]:
    def _check(actual: str) -> None:
        assert fragment in actual

    return _check


@pytest.fixture()
def console() -> Console:
    return Console(file=StringIO(), force_terminal=True, color_system=None)


@pytest.fixture()
def wallet_manager(tmp_path: Path) -> WalletManager:
    return WalletManager(keys_dir=tmp_path / "global_keys")


@pytest.fixture()
def rpc_stub() -> RPCStub:
    return RPCStub()


@pytest.fixture()
def session_bundle(
    tmp_path: Path, wallet_manager: WalletManager, rpc_stub: RPCStub
) -> tuple[SessionManager, object, WalletManager, RPCStub]:
    manager = SessionManager(root=tmp_path / "sessions")
    context = manager.start()
    return manager, context, wallet_manager, rpc_stub


@pytest.fixture()
def config_context() -> ConfigContext:
    return ConfigContext(config=SolCoderConfig(), llm_api_key="dummy-key", passphrase="pass")


def test_help_command_bypasses_llm(
    console: Console, session_bundle: tuple[SessionManager, object, WalletManager, RPCStub]
) -> None:
    manager, context, wallet_manager, rpc_stub = session_bundle
    llm = StubLLM()
    app = CLIApp(
        console=console,
        llm=llm,
        session_manager=manager,
        session_context=context,
        wallet_manager=wallet_manager,
        rpc_client=rpc_stub,
    )

    response = app.handle_line("/help")

    assert llm.calls == []
    assert response.continue_loop is True
    assert any("/help" in message for _, message in response.messages)


def test_chat_message_invokes_llm(
    console: Console,
    session_bundle: tuple[SessionManager, object, WalletManager, RPCStub],
    config_context: ConfigContext,
) -> None:
    manager, context, wallet_manager, rpc_stub = session_bundle
    llm = StubLLM()
    app = CLIApp(
        console=console,
        llm=llm,
        session_manager=manager,
        session_context=context,
        wallet_manager=wallet_manager,
        rpc_client=rpc_stub,
        config_context=config_context,
    )

    response = app.handle_line("hello solcoder")

    assert llm.calls == ["hello solcoder", AGENT_PLAN_ACK]
    assert response.continue_loop is True
    assert response.messages and response.messages[0][0] == "agent"
    plan_message = response.messages[0][1]
    assert "Stub plan" in plan_message
    assert response.messages[-1][0] == "agent"
    assert "[stub] Completed request" in response.messages[-1][1]
    assert response.rendered_roles == {"agent"}
    assert response.tool_calls and response.tool_calls[0]["type"] == "llm"
    assert response.tool_calls[0]["status"] == "cached"
    assert response.tool_calls[0]["reasoning_effort"] == config_context.config.llm_reasoning_effort
    assert context.metadata.llm_input_tokens > 0
    assert context.metadata.llm_output_tokens > 0
    assert context.metadata.llm_last_input_tokens > 0
    assert context.metadata.llm_last_output_tokens > 0
    state_path = manager.root / context.metadata.session_id / "state.json"
    assert "hello solcoder" in state_path.read_text()


def test_agent_loop_runs_tool(
    console: Console,
    session_bundle: tuple[SessionManager, object, WalletManager, RPCStub],
    config_context: ConfigContext,
) -> None:
    manager, context, wallet_manager, rpc_stub = session_bundle
    captured: list[dict[str, Any]] = []
    registry = build_default_registry()

    def handler(payload: dict[str, Any]) -> ToolResult:
        captured.append(payload)
        return ToolResult(content=f"Echo: {payload['text']}", data=payload)

    registry.register(
        Tool(
            name="test_echo",
            description="Test echo tool",
            input_schema={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
            output_schema={"type": "object"},
            handler=handler,
        )
    )

    script = [
        {"expect": expect_equals("run tool please"), "reply": {"type": "plan", "message": "Plan ready", "steps": ["Call test_echo"]}},
        {"expect": expect_equals(AGENT_PLAN_ACK), "reply": {"type": "tool_request", "step_title": "Echo step", "tool": {"name": "test_echo", "args": {"text": "hi"}}}},
        {"expect": expect_tool_result("test_echo"), "reply": {"type": "reply", "message": "All done"}},
    ]
    llm = ScriptedLLM(script)

    app = CLIApp(
        console=console,
        llm=llm,
        session_manager=manager,
        session_context=context,
        wallet_manager=wallet_manager,
        rpc_client=rpc_stub,
        config_context=config_context,
        tool_registry=registry,
    )

    response = app.handle_line("run tool please")

    assert captured == [{"text": "hi"}]
    assert any("Echo step" in message for _, message in response.messages)
    tool_entries = [entry for entry in response.tool_calls if entry.get("type") == "tool"]
    assert tool_entries and tool_entries[0]["name"] == "test_echo"
    assert tool_entries[0]["status"] == "success"
    assert llm.script == []
    assert llm.calls[0] == "run tool please"
    assert llm.calls[1] == AGENT_PLAN_ACK


def test_agent_loop_recovers_from_invalid_json(
    console: Console,
    session_bundle: tuple[SessionManager, object, WalletManager, RPCStub],
    config_context: ConfigContext,
) -> None:
    manager, context, wallet_manager, rpc_stub = session_bundle
    script = [
        {"expect": expect_equals("walk me through"), "reply": "not json"},
        {"expect": expect_contains('"type": "error"'), "reply": {"type": "plan", "message": "Recovered plan", "steps": ["Retry step"]}},
        {"expect": expect_equals(AGENT_PLAN_ACK), "reply": {"type": "reply", "message": "Recovered"}},
    ]
    llm = ScriptedLLM(script)

    app = CLIApp(
        console=console,
        llm=llm,
        session_manager=manager,
        session_context=context,
        wallet_manager=wallet_manager,
        rpc_client=rpc_stub,
        config_context=config_context,
    )

    response = app.handle_line("walk me through")

    assert llm.script == []
    assert all(role != "system" for role, _ in response.messages)
    assert response.messages[0][0] == "agent"
    assert "Recovered plan" in response.messages[0][1]
    assert response.messages[-1][1].startswith("Recovered")


def test_agent_loop_reports_invalid_json_twice(
    console: Console,
    session_bundle: tuple[SessionManager, object, WalletManager, RPCStub],
    config_context: ConfigContext,
) -> None:
    manager, context, wallet_manager, rpc_stub = session_bundle
    script = [
        {"expect": expect_equals("bad response please"), "reply": "still wrong"},
        {"expect": expect_contains('"type": "error"'), "reply": "also wrong"},
    ]
    llm = ScriptedLLM(script)

    app = CLIApp(
        console=console,
        llm=llm,
        session_manager=manager,
        session_context=context,
        wallet_manager=wallet_manager,
        rpc_client=rpc_stub,
        config_context=config_context,
    )

    response = app.handle_line("bad response please")

    assert response.messages[-1][0] == "system"
    assert "failed to provide a valid directive" in response.messages[-1][1]
    assert llm.script == []
def test_quit_command_exits(
    console: Console, session_bundle: tuple[SessionManager, object, WalletManager, RPCStub]
) -> None:
    manager, context, wallet_manager, rpc_stub = session_bundle
    llm = StubLLM()
    app = CLIApp(
        console=console,
        llm=llm,
        session_manager=manager,
        session_context=context,
        wallet_manager=wallet_manager,
        rpc_client=rpc_stub,
    )

    response = app.handle_line("/quit")

    assert response.continue_loop is False
    assert any("Exiting" in message for _, message in response.messages)


def test_settings_updates_wallet(
    console: Console, session_bundle: tuple[SessionManager, object, WalletManager, RPCStub]
) -> None:
    manager, context, wallet_manager, rpc_stub = session_bundle
    app = CLIApp(
        console=console,
        session_manager=manager,
        session_context=context,
        wallet_manager=wallet_manager,
        rpc_client=rpc_stub,
    )

    response = app.handle_line("/settings wallet Gk98abc")

    assert any("Wallet updated" in message for _, message in response.messages)
    assert context.metadata.wallet_status == "Gk98abc"
    state_path = manager.root / context.metadata.session_id / "state.json"
    persisted = json.loads(state_path.read_text())
    assert persisted["metadata"]["wallet_status"] == "Gk98abc"


def test_settings_sets_spend(
    console: Console, session_bundle: tuple[SessionManager, object, WalletManager, RPCStub]
) -> None:
    manager, context, wallet_manager, rpc_stub = session_bundle
    app = CLIApp(
        console=console,
        session_manager=manager,
        session_context=context,
        wallet_manager=wallet_manager,
        rpc_client=rpc_stub,
    )

    response = app.handle_line("/settings spend 0.75")

    assert any("Session spend set" in message for _, message in response.messages)
    assert context.metadata.spend_amount == 0.75
    state_path = manager.root / context.metadata.session_id / "state.json"
    persisted = json.loads(state_path.read_text())
    assert persisted["metadata"]["spend_amount"] == 0.75


def test_settings_updates_model(
    console: Console,
    session_bundle: tuple[SessionManager, object, WalletManager, RPCStub],
    config_context: ConfigContext,
) -> None:
    manager, context, wallet_manager, rpc_stub = session_bundle
    llm = StubLLM()
    app = CLIApp(
        console=console,
        llm=llm,
        session_manager=manager,
        session_context=context,
        wallet_manager=wallet_manager,
        rpc_client=rpc_stub,
        config_context=config_context,
    )

    response = app.handle_line("/settings model gpt-5")

    assert any("LLM model updated" in message for _, message in response.messages)
    assert config_context.config.llm_model == "gpt-5"
    assert llm.model == "gpt-5"


def test_settings_updates_reasoning(
    console: Console,
    session_bundle: tuple[SessionManager, object, WalletManager, RPCStub],
    config_context: ConfigContext,
) -> None:
    manager, context, wallet_manager, rpc_stub = session_bundle
    llm = StubLLM()
    app = CLIApp(
        console=console,
        llm=llm,
        session_manager=manager,
        session_context=context,
        wallet_manager=wallet_manager,
        rpc_client=rpc_stub,
        config_context=config_context,
    )

    response = app.handle_line("/settings reasoning high")

    assert any("Reasoning effort set" in message for _, message in response.messages)
    assert config_context.config.llm_reasoning_effort == "high"
    assert llm.reasoning_effort == "high"


def test_session_compact_command(
    console: Console,
    tmp_path: Path,
    session_bundle: tuple[SessionManager, object, WalletManager, RPCStub],
    config_context: ConfigContext,
) -> None:
    config_context.config.history_max_messages = 6
    config_context.config.history_summary_keep = 2
    config_context.config.history_summary_max_words = 50
    manager, context, wallet_manager, rpc_stub = session_bundle
    llm = StubLLM()
    app = CLIApp(
        console=console,
        llm=llm,
        session_manager=manager,
        session_context=context,
        wallet_manager=wallet_manager,
        rpc_client=rpc_stub,
        config_context=config_context,
        config_manager=ConfigManager(config_dir=tmp_path / "cfg"),
    )

    for i in range(6):
        app.context_manager.record("user", f"user-msg-{i}")
        app.context_manager.record("agent", f"agent-msg-{i}")

    response = app.handle_line("/session compact")

    assert any("Compacted history" in message for _, message in response.messages)
    assert len(context.transcript) == 4
    assert context.transcript[0]["role"] == "system"
    assert context.transcript[0].get("summary") is True
    assert context.transcript[-1]["message"].startswith("Compacted history")


def test_settings_persist_to_config(
    console: Console,
    tmp_path: Path,
    session_bundle: tuple[SessionManager, object, WalletManager, RPCStub],
) -> None:
    config_dir = tmp_path / "config"
    manager = ConfigManager(config_dir=config_dir)
    context = manager.ensure(interactive=False, llm_api_key="secret", passphrase="pass")

    session_manager, session_context, wallet_manager, rpc_stub = session_bundle
    llm = StubLLM()
    app = CLIApp(
        console=console,
        llm=llm,
        config_context=context,
        config_manager=manager,
        session_manager=session_manager,
        session_context=session_context,
        wallet_manager=wallet_manager,
        rpc_client=rpc_stub,
    )

    app.handle_line("/settings model gpt-5")
    app.handle_line("/settings reasoning high")

    reloaded = manager.ensure(interactive=False, passphrase="pass")
    assert reloaded.config.llm_model == "gpt-5"
    assert reloaded.config.llm_reasoning_effort == "high"


def test_todo_command_add_and_complete(
    console: Console, session_bundle: tuple[SessionManager, object, WalletManager, RPCStub]
) -> None:
    manager, context, wallet_manager, rpc_stub = session_bundle
    app = CLIApp(
        console=console,
        session_manager=manager,
        session_context=context,
        wallet_manager=wallet_manager,
        rpc_client=rpc_stub,
    )

    response = app.handle_line("/todo add Write docs --desc outline")
    assert any("TODO List" in message for _, message in response.messages)
    assert len(app.todo_manager.tasks()) == 1
    task_id = app.todo_manager.tasks()[0].id

    complete_response = app.handle_line(f"/todo done {task_id}")
    assert any("marked complete" in message for _, message in complete_response.messages)
    assert "[x]" in complete_response.messages[0][1]


def test_settings_summary(
    console: Console, session_bundle: tuple[SessionManager, object, WalletManager, RPCStub]
) -> None:
    manager, context, wallet_manager, rpc_stub = session_bundle
    app = CLIApp(
        console=console,
        session_manager=manager,
        session_context=context,
        wallet_manager=wallet_manager,
        rpc_client=rpc_stub,
    )
    context.metadata.wallet_status = "ExistingWallet"
    context.metadata.spend_amount = 1.23
    context.metadata.active_project = "/project/root"

    response = app.handle_line("/settings")

    assert any("Active project" in message for _, message in response.messages)
    assert any("ExistingWallet" in message for _, message in response.messages)


def test_wallet_status_no_wallet(
    console: Console, session_bundle: tuple[SessionManager, object, WalletManager, RPCStub]
) -> None:
    manager, context, wallet_manager, rpc_stub = session_bundle
    app = CLIApp(
        console=console,
        session_manager=manager,
        session_context=context,
        wallet_manager=wallet_manager,
        rpc_client=rpc_stub,
    )

    response = app.handle_line("/wallet status")

    assert any("No wallet found" in message for _, message in response.messages)
    assert context.metadata.wallet_status == "missing"
    assert context.metadata.wallet_balance is None


def test_wallet_unlock_command_updates_metadata(
    console: Console, session_bundle: tuple[SessionManager, object, WalletManager, RPCStub]
) -> None:
    manager, context, wallet_manager, rpc_stub = session_bundle
    wallet_manager.create_wallet("passphrase", force=True)
    wallet_manager.lock_wallet()
    app = CLIApp(
        console=console,
        session_manager=manager,
        session_context=context,
        wallet_manager=wallet_manager,
        rpc_client=rpc_stub,
    )
    rpc_stub.balances = [0.75]
    app._prompt_secret = lambda _msg, confirmation=False, **_kwargs: "passphrase"  # type: ignore[assignment]

    response = app.handle_line("/wallet unlock")

    assert any("Wallet unlocked" in message for _, message in response.messages)
    assert "Unlocked" in context.metadata.wallet_status
    assert context.metadata.wallet_balance == pytest.approx(0.75)


def test_wallet_export_to_file(
    console: Console, tmp_path: Path, session_bundle: tuple[SessionManager, object, WalletManager, RPCStub]
) -> None:
    manager, context, wallet_manager, rpc_stub = session_bundle
    wallet_manager.create_wallet("passphrase", force=True)
    app = CLIApp(
        console=console,
        session_manager=manager,
        session_context=context,
        wallet_manager=wallet_manager,
        rpc_client=rpc_stub,
    )
    app._prompt_secret = lambda _msg, confirmation=False, **_kwargs: "passphrase"  # type: ignore[assignment]

    export_path = tmp_path / "secret.json"
    response = app.handle_line(f"/wallet export {export_path}")

    assert any(str(export_path) in message for _, message in response.messages)
    assert export_path.read_text().startswith("[")
    mode = os.stat(export_path).st_mode & 0o777
    assert mode in {0o600, 0o666}


def test_wallet_phrase_command(
    console: Console, session_bundle: tuple[SessionManager, object, WalletManager, RPCStub]
) -> None:
    manager, context, wallet_manager, rpc_stub = session_bundle
    _, mnemonic = wallet_manager.create_wallet("passphrase", force=True)
    wallet_manager.lock_wallet()
    app = CLIApp(
        console=console,
        session_manager=manager,
        session_context=context,
        wallet_manager=wallet_manager,
        rpc_client=rpc_stub,
    )
    app._prompt_secret = lambda _msg, confirmation=False, **_kwargs: "passphrase"  # type: ignore[assignment]

    response = app.handle_line("/wallet phrase")

    assert mnemonic in "\n".join(message for _, message in response.messages)


def test_session_export_command(console: Console, session_bundle: tuple[SessionManager, object, WalletManager, RPCStub]) -> None:
    manager, context, wallet_manager, rpc_stub = session_bundle
    context.transcript.append(
        {
            "role": "user",
            "message": "Generated address VkgXGe7czUXXcWzeWgt6H9VxLJhqioU5AnqRC1Ry2GK",
            "timestamp": datetime.now(UTC).isoformat(),
        }
    )
    manager.save(context)
    app = CLIApp(
        console=console,
        session_manager=manager,
        session_context=context,
        wallet_manager=wallet_manager,
        rpc_client=rpc_stub,
    )

    response = app.handle_line(f"/session export {context.metadata.session_id}")

    assert any("Session Export" in message for _, message in response.messages)
    assert any("VkgX…y2GK" in message for _, message in response.messages)
    assert response.tool_calls is not None
    assert response.tool_calls[0]["status"] == "success"

def test_session_export_missing(console: Console, session_bundle: tuple[SessionManager, object, WalletManager, RPCStub]) -> None:
    manager, context, wallet_manager, rpc_stub = session_bundle
    app = CLIApp(
        console=console,
        session_manager=manager,
        session_context=context,
        wallet_manager=wallet_manager,
        rpc_client=rpc_stub,
    )

    response = app.handle_line("/session export unknown")

    assert any("not found" in message for _, message in response.messages)
    assert response.tool_calls is not None
    assert response.tool_calls[0]["status"] == "not_found"


def test_env_diag_command(
    console: Console,
    session_bundle: tuple[SessionManager, object, WalletManager, RPCStub],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, context, wallet_manager, rpc_stub = session_bundle
    fake_results = [
        DiagnosticResult(
            name="Solana CLI",
            status="ok",
            found=True,
            version="solana-cli 1.17",
            remediation=None,
        ),
        DiagnosticResult(
            name="Anchor",
            status="missing",
            found=False,
            version=None,
            remediation="Install Anchor.",
        ),
    ]
    monkeypatch.setattr(env_commands, "collect_environment_diagnostics", lambda: fake_results)
    app = CLIApp(
        console=console,
        session_manager=manager,
        session_context=context,
        wallet_manager=wallet_manager,
        rpc_client=rpc_stub,
    )

    response = app.handle_line("/env diag")

    combined = "\n".join(message for _, message in response.messages)
    assert "Environment Diagnostics" in combined
    assert "Solana CLI" in combined
    assert "Anchor" in combined
    assert response.tool_calls is not None
    assert response.tool_calls[0]["status"] == "missing"


def test_env_diag_usage(console: Console, session_bundle: tuple[SessionManager, object, WalletManager, RPCStub]) -> None:
    manager, context, wallet_manager, rpc_stub = session_bundle
    app = CLIApp(
        console=console,
        session_manager=manager,
        session_context=context,
        wallet_manager=wallet_manager,
        rpc_client=rpc_stub,
    )

    response = app.handle_line("/env")

    assert any("Usage: /env diag" in message for _, message in response.messages)


def test_template_counter_command(
    console: Console,
    session_bundle: tuple[SessionManager, object, WalletManager, RPCStub],
    tmp_path: Path,
) -> None:
    manager, context, wallet_manager, rpc_stub = session_bundle
    app = CLIApp(
        console=console,
        session_manager=manager,
        session_context=context,
        wallet_manager=wallet_manager,
        rpc_client=rpc_stub,
    )

    target = tmp_path / "scaffold"
    response = app.handle_line(f"/template counter {target}")

    assert target.exists()
    assert (target / "Anchor.toml").exists()
    assert response.tool_calls is not None
    assert response.tool_calls[0]["status"] == "success"
