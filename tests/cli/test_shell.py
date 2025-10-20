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
from solcoder.core.installers import InstallerResult
from solcoder.core.llm import LLMResponse
from solcoder.core.tool_registry import Tool, ToolResult, build_default_registry
from solcoder.session import SessionManager
from solcoder.solana import WalletManager

cli_app_module = importlib.import_module("solcoder.cli.app")


class RPCStub:
    def __init__(self, balances: list[float] | None = None) -> None:
        self.balances = balances or []
        self.endpoint = "https://api.devnet.solana.com"

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


def expect_plan_ack(expect_todo: bool | None = None) -> Callable[[str], None]:
    def _check(actual: str) -> None:
        payload = json.loads(actual)
        assert payload.get("type") == "plan_ack"
        assert payload.get("status") == "ready"
        has_todo = "todo_tasks" in payload and bool(payload.get("todo_tasks"))
        if expect_todo is True:
            assert has_todo, "Expected todo_tasks in plan_ack payload"
        elif expect_todo is False:
            assert not has_todo, f"Did not expect todo_tasks but received {payload.get('todo_tasks')}"

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
    combined = "\n".join(message for _, message in response.messages)
    assert "/help" in combined
    assert "/wallet" in combined
    assert "Wallet management" in combined


def test_status_bar_snapshot_reflects_metadata(
    console: Console,
    session_bundle: tuple[SessionManager, object, WalletManager, RPCStub],
    config_context: ConfigContext,
) -> None:
    manager, context, wallet_manager, rpc_stub = session_bundle
    app = CLIApp(
        console=console,
        session_manager=manager,
        session_context=context,
        wallet_manager=wallet_manager,
        rpc_client=rpc_stub,
        config_context=config_context,
    )

    metadata = app.session_context.metadata
    metadata.active_project = "/project/root"
    metadata.wallet_status = "Unlocked (ABCD…1234)"
    metadata.wallet_balance = 1.234
    metadata.spend_amount = 0.75
    metadata.llm_last_input_tokens = 1_000
    metadata.llm_output_tokens = 2_000
    config_context.config.network = "testnet"
    app.log_event("wallet", "Test wallet log")

    snapshot = app.status_bar.snapshot()

    assert snapshot.workspace == "/project/root"
    assert snapshot.network == "testnet"
    assert snapshot.agent_mode == "assistive"
    assert snapshot.wallet.startswith("connected")
    assert snapshot.wallet.endswith("✅")
    assert snapshot.balance == "1.234 SOL"
    assert snapshot.tokens.startswith("in 1,000 • out 2,000")
    assert snapshot.context.endswith("context free")
    assert snapshot.last_log == "wallet/INFO"


def test_logs_command_filters_and_redacts(
    console: Console,
    session_bundle: tuple[SessionManager, object, WalletManager, RPCStub],
    config_context: ConfigContext,
) -> None:
    manager, context, wallet_manager, rpc_stub = session_bundle
    app = CLIApp(
        console=console,
        session_manager=manager,
        session_context=context,
        wallet_manager=wallet_manager,
        rpc_client=rpc_stub,
        config_context=config_context,
    )

    app.log_event("wallet", "Wallet key VkgXGe7czUXXcWzeWgt6H9VxLJhqioU5AnqRC1Ry2GK")
    app.log_event("deploy", "Deploy finished successfully")

    response = app.handle_line("/logs wallet")

    message = "\n".join(text for _, text in response.messages)
    assert "wallet" in message
    assert "deploy" not in message
    assert "VkgX…y2GK" in message

    invalid = app.handle_line("/logs unknown")
    assert any("Unknown log category" in text for _, text in invalid.messages)


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

    assert len(llm.calls) == 2
    assert llm.calls[0] == "hello solcoder"
    ack_payload = json.loads(llm.calls[1])
    assert ack_payload["type"] == "plan_ack"
    assert ack_payload["status"] == "ready"
    assert ack_payload.get("todo_tasks")
    assert response.continue_loop is True
    assert response.messages and response.messages[0][0] == "agent"
    plan_message = response.messages[0][1]
    assert plan_message == "[[RENDER_TODO_PANEL]]"
    assert response.messages[-2][0] == "agent"
    assert "[stub] Completed request" in response.messages[-2][1]
    assert response.messages[-1][0] == "system"
    assert "unfinished items" in response.messages[-1][1]
    assert response.rendered_roles == {"agent", "system"}
    assert any(task.status != "done" for task in app.todo_manager.tasks())
    assert response.tool_calls and response.tool_calls[0]["type"] == "llm"
    assert response.tool_calls[0]["status"] == "cached"
    assert response.tool_calls[0]["reasoning_effort"] == config_context.config.llm_reasoning_effort
    assert context.metadata.llm_input_tokens > 0
    assert context.metadata.llm_output_tokens > 0
    assert context.metadata.llm_last_input_tokens > 0
    assert context.metadata.llm_last_output_tokens > 0
    state_path = manager.root / context.metadata.session_id / "state.json"
    assert "hello solcoder" in state_path.read_text()


def test_agent_can_reply_without_plan(
    console: Console,
    session_bundle: tuple[SessionManager, object, WalletManager, RPCStub],
) -> None:
    manager, context, wallet_manager, rpc_stub = session_bundle
    script = [
        {"expect": expect_equals("quick hello"), "reply": {"type": "reply", "message": "Hello there!"}},
    ]
    llm = ScriptedLLM(script)

    app = CLIApp(
        console=console,
        llm=llm,
        session_manager=manager,
        session_context=context,
        wallet_manager=wallet_manager,
        rpc_client=rpc_stub,
    )

    response = app.handle_line("quick hello")

    assert llm.script == []
    assert llm.calls == ["quick hello"]
    assert response.messages[0][0] == "agent"
    assert "Hello there" in response.messages[0][1]
    assert not app.todo_manager.tasks()
    assert response.tool_calls[0]["type"] == "llm"


def test_agent_requires_plan_when_todo_exists(
    console: Console,
    session_bundle: tuple[SessionManager, object, WalletManager, RPCStub],
) -> None:
    manager, context, wallet_manager, rpc_stub = session_bundle
    script = [
        {"expect": expect_equals("work todo"), "reply": {"type": "reply", "message": "Sure"}},
        {"expect": expect_contains('"type": "error"'), "reply": {"type": "plan", "message": "Plan todo", "steps": ["Complete tasks"]}},
        {"expect": expect_plan_ack(False), "reply": {"type": "reply", "message": "Done"}},
    ]
    llm = ScriptedLLM(script)

    app = CLIApp(
        console=console,
        llm=llm,
        session_manager=manager,
        session_context=context,
        wallet_manager=wallet_manager,
        rpc_client=rpc_stub,
    )

    app.handle_line("/todo add Finish docs")
    response = app.handle_line("work todo")

    assert llm.script == []
    assert app.todo_manager.tasks()
    assert any("[[RENDER_TODO_PANEL]]" in message for _, message in response.messages)


def test_single_step_plan_isnt_bootstrapped(
    console: Console,
    session_bundle: tuple[SessionManager, object, WalletManager, RPCStub],
) -> None:
    manager, context, wallet_manager, rpc_stub = session_bundle
    script = [
        {
            "expect": expect_equals("single step"),
            "reply": {"type": "plan", "message": "One step only", "steps": ["Only step"]},
        },
        {
            "expect": expect_plan_ack(False),
            "reply": {"type": "reply", "message": "Done"},
        },
    ]
    llm = ScriptedLLM(script)

    app = CLIApp(
        console=console,
        llm=llm,
        session_manager=manager,
        session_context=context,
        wallet_manager=wallet_manager,
        rpc_client=rpc_stub,
    )

    response = app.handle_line("single step")

    assert llm.script == []
    assert not app.todo_manager.tasks()
    assert all("One step only" not in message for _, message in response.messages)
    assert all("[[RENDER_TODO_PANEL]]" not in message for _, message in response.messages)


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
        {"expect": expect_plan_ack(False), "reply": {"type": "tool_request", "step_title": "Echo step", "tool": {"name": "test_echo", "args": {"text": "hi"}}}},
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
    ack_payload = json.loads(llm.calls[1])
    assert ack_payload["type"] == "plan_ack"
    assert ack_payload["status"] == "ready"


def test_agent_loop_recovers_from_invalid_json(
    console: Console,
    session_bundle: tuple[SessionManager, object, WalletManager, RPCStub],
    config_context: ConfigContext,
) -> None:
    manager, context, wallet_manager, rpc_stub = session_bundle
    script = [
        {"expect": expect_equals("walk me through"), "reply": "not json"},
        {
            "expect": expect_contains('"type": "error"'),
            "reply": {
                "type": "plan",
                "message": "Recovered plan",
                "steps": ["Retry step", "Verify outcome"],
            },
        },
        {"expect": expect_plan_ack(True), "reply": {"type": "reply", "message": "Recovered"}},
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
    assert any(role == "system" for role, _ in response.messages)
    assert response.messages[0][0] == "agent"
    assert response.messages[0][1] == "[[RENDER_TODO_PANEL]]"
    assert any(role == "agent" and message.startswith("Recovered") for role, message in response.messages)
    assert response.messages[-2][0] == "system"
    assert "unfinished items" in response.messages[-2][1]
    assert response.messages[-1][0] == "system"
    assert "invalid directive" in response.messages[-1][1].lower()
    assert any(task.status != "done" for task in app.todo_manager.tasks())


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
    assert "invalid directive" in response.messages[-1][1].lower()
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
    assert any("[[RENDER_TODO_PANEL]]" in message for _, message in response.messages)
    assert len(app.todo_manager.tasks()) == 1
    task_id = app.todo_manager.tasks()[0].id
    assert app.todo_manager.tasks()[0].status == "in_progress"

    complete_response = app.handle_line(f"/todo done {task_id}")
    assert any("marked complete" in message for _, message in complete_response.messages)
    assert "[[RENDER_TODO_PANEL]]" in complete_response.messages[0][1]
    assert app.todo_manager.tasks()[0].status == "done"

    plan_response = app.handle_line("hello solcoder")
    assert app.todo_manager.tasks()
    assert any("[[RENDER_TODO_PANEL]]" in message for _, message in plan_response.messages)


def test_todo_command_respects_quotes(
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

    response = app.handle_line("/todo add \"Fix bug\" --desc 'repro steps in staging'")
    assert response.messages
    tasks = app.todo_manager.tasks()
    assert len(tasks) == 1
    task = tasks[0]
    assert task.title == "Fix bug"
    assert task.description == "repro steps in staging"


def test_todo_persistence_across_sessions(
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

    app.handle_line("/todo add Persist me")
    session_id = context.metadata.session_id

    new_context = manager.start(session_id=session_id)
    new_app = CLIApp(
        console=console,
        session_manager=manager,
        session_context=new_context,
        wallet_manager=wallet_manager,
        rpc_client=rpc_stub,
    )

    titles = [task.title for task in new_app.todo_manager.tasks()]
    assert "Persist me" in titles


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


def test_wallet_status_includes_qr(
    console: Console, session_bundle: tuple[SessionManager, object, WalletManager, RPCStub]
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
    rpc_stub.balances = [2.0]

    response = app.handle_line("/wallet status")

    assert any("Address QR" in message for _, message in response.messages)
    assert context.metadata.wallet_balance == pytest.approx(2.0)


def test_wallet_address_command_renders_qr(
    console: Console, session_bundle: tuple[SessionManager, object, WalletManager, RPCStub]
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

    response = app.handle_line("/wallet address")

    assert any("Wallet address:" in message for _, message in response.messages)
    assert any("Address QR" in message for _, message in response.messages)


def test_wallet_help_lists_subcommands(
    console: Console, session_bundle: tuple[SessionManager, object, WalletManager, RPCStub]
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

    response = app.handle_line("/wallet help")

    combined = "\n".join(message for _, message in response.messages)
    assert "send <addr> <amt" in combined
    assert "address" in combined


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


def test_wallet_send_happy_path(
    monkeypatch: pytest.MonkeyPatch,
    console: Console,
    session_bundle: tuple[SessionManager, object, WalletManager, RPCStub],
    config_context: ConfigContext,
) -> None:
    manager, context, wallet_manager, rpc_stub = session_bundle
    wallet_manager.create_wallet("passphrase", force=True)
    app = CLIApp(
        console=console,
        session_manager=manager,
        session_context=context,
        wallet_manager=wallet_manager,
        rpc_client=rpc_stub,
        config_context=config_context,
    )
    rpc_stub.balances = [0.9]

    monkeypatch.setattr(
        wallet_manager,
        "send_transfer",
        lambda *args, **kwargs: "FakeSignature",  # type: ignore[return-value]
    )
    app._prompt_secret = lambda *_args, **_kwargs: "passphrase"  # type: ignore[assignment]
    app._prompt_text = lambda *_args, **_kwargs: "send"  # type: ignore[assignment]

    response = app.handle_line("/wallet send Destination11111111111111111111111111 0.1")

    assert any("FakeSignature" in message for _, message in response.messages)
    assert context.metadata.spend_amount == pytest.approx(0.1)
    assert context.metadata.wallet_balance == pytest.approx(0.9)


def test_wallet_send_blocks_over_spend_cap(
    console: Console,
    session_bundle: tuple[SessionManager, object, WalletManager, RPCStub],
    config_context: ConfigContext,
) -> None:
    manager, context, wallet_manager, rpc_stub = session_bundle
    wallet_manager.create_wallet("passphrase", force=True)
    config_context.config.max_session_spend = 0.05
    context.metadata.spend_amount = 0.04
    app = CLIApp(
        console=console,
        session_manager=manager,
        session_context=context,
        wallet_manager=wallet_manager,
        rpc_client=rpc_stub,
        config_context=config_context,
    )

    response = app.handle_line("/wallet send AnyAddr111111111111111111111111111111 0.02")

    assert any("Session spend cap exceeded" in message for _, message in response.messages)
    assert context.metadata.spend_amount == pytest.approx(0.04)


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

    assert any("Usage: /env <diag|install>" in message for _, message in response.messages)


def test_env_install_invokes_installer(
    monkeypatch: pytest.MonkeyPatch,
    console: Console,
    session_bundle: tuple[SessionManager, object, WalletManager, RPCStub],
) -> None:
    manager, context, wallet_manager, rpc_stub = session_bundle
    calls: list[tuple[str, bool]] = []

    def fake_install(tool: str, *, console=None, dry_run: bool = False, runner=None) -> InstallerResult:  # type: ignore[override]
        calls.append((tool, dry_run))
        return InstallerResult(
            tool=tool,
            display_name="Anchor CLI",
            success=True,
            verification_passed=True,
            commands=("fake",),
            logs=("ok",),
        )

    monkeypatch.setattr(env_commands, "install_tool", fake_install)

    app = CLIApp(
        console=console,
        session_manager=manager,
        session_context=context,
        wallet_manager=wallet_manager,
        rpc_client=rpc_stub,
    )

    response = app.handle_line("/env install anchor")

    assert calls == [("anchor", False)]
    combined = "\n".join(message for _, message in response.messages)
    assert "Anchor CLI" in combined


def test_env_install_handles_unknown_tool(
    console: Console,
    session_bundle: tuple[SessionManager, object, WalletManager, RPCStub],
) -> None:
    manager, context, wallet_manager, rpc_stub = session_bundle
    app = CLIApp(
        console=console,
        session_manager=manager,
        session_context=context,
        wallet_manager=wallet_manager,
        rpc_client=rpc_stub,
    )

    response = app.handle_line("/env install unknown")

    assert any("Unknown installer" in message for _, message in response.messages)


def test_bootstrap_prompts_for_missing_tools(
    monkeypatch: pytest.MonkeyPatch,
    console: Console,
    session_bundle: tuple[SessionManager, object, WalletManager, RPCStub],
) -> None:
    manager, context, wallet_manager, rpc_stub = session_bundle

    missing_sequence = [["solana"], []]

    def fake_collect() -> list[DiagnosticResult]:
        return []

    def fake_detect(_diagnostics, *, only_required: bool = False) -> list[str]:
        return missing_sequence.pop(0) if missing_sequence else []

    records: list[str] = []

    def fake_install(tool: str, **kwargs):  # type: ignore[override]
        records.append(tool)
        return InstallerResult(
            tool=tool,
            display_name="Solana CLI",
            success=True,
            verification_passed=True,
            commands=("fake",),
            logs=("installed",),
        )

    responses = ["y", ""]

    def scripted_prompt(_session, _message: str) -> str:
        return responses.pop(0)

    monkeypatch.setattr(cli_app_module, "collect_environment_diagnostics", fake_collect)
    monkeypatch.setattr(cli_app_module, "detect_missing_tools", fake_detect)
    monkeypatch.setattr(cli_app_module, "install_tool", fake_install)
    monkeypatch.setattr(cli_app_module, "installer_display_name", lambda tool: "Solana CLI")
    monkeypatch.setattr(cli_app_module, "prompt_text", scripted_prompt)
    monkeypatch.setattr(cli_app_module, "required_tools", lambda: ["solana"])

    app = CLIApp(
        console=console,
        session_manager=manager,
        session_context=context,
        wallet_manager=wallet_manager,
        rpc_client=rpc_stub,
    )

    app._handle_environment_bootstrap()

    assert records == ["solana"]
    assert not responses


def test_bootstrap_requires_explicit_anchor_skip(
    monkeypatch: pytest.MonkeyPatch,
    console: Console,
    session_bundle: tuple[SessionManager, object, WalletManager, RPCStub],
) -> None:
    manager, context, wallet_manager, rpc_stub = session_bundle

    missing_sequence = [["anchor"], ["anchor"], []]

    def fake_collect() -> list[DiagnosticResult]:
        return []

    def fake_detect(_diagnostics, *, only_required: bool = False) -> list[str]:
        return missing_sequence.pop(0) if missing_sequence else []

    install_calls: list[str] = []

    def fake_install(tool: str, **kwargs):  # type: ignore[override]
        install_calls.append(tool)
        pytest.fail("Anchor installer should not run when user skips.")

    responses = ["n", "skip", "skip", ""]
    prompts: list[str] = []

    def scripted_prompt(_session, message: str) -> str:
        prompts.append(message)
        return responses.pop(0)

    monkeypatch.setattr(cli_app_module, "collect_environment_diagnostics", fake_collect)
    monkeypatch.setattr(cli_app_module, "detect_missing_tools", fake_detect)
    monkeypatch.setattr(cli_app_module, "install_tool", fake_install)
    monkeypatch.setattr(cli_app_module, "installer_display_name", lambda tool: "Anchor CLI")
    monkeypatch.setattr(cli_app_module, "prompt_text", scripted_prompt)
    monkeypatch.setattr(cli_app_module, "required_tools", lambda: ["anchor"])

    app = CLIApp(
        console=console,
        session_manager=manager,
        session_context=context,
        wallet_manager=wallet_manager,
        rpc_client=rpc_stub,
    )

    app._handle_environment_bootstrap()

    assert install_calls == []
    assert not responses
    assert sum("Anchor CLI is missing" in prompt for prompt in prompts) == 2
    assert len(prompts) == 4
    assert any(prompt.startswith("Anchor powers Solana deploy flows") for prompt in prompts)
    assert prompts[-1].startswith("Diagnostics complete")


def test_bootstrap_prompts_for_shell_reload_when_tool_off_path(
    monkeypatch: pytest.MonkeyPatch,
    console: Console,
    session_bundle: tuple[SessionManager, object, WalletManager, RPCStub],
    tmp_path: Path,
) -> None:
    manager, context, wallet_manager, rpc_stub = session_bundle
    location = tmp_path / ".cargo" / "bin" / "anchor"

    diagnostics = [
        DiagnosticResult(
            name="Anchor",
            status="missing",
            found=False,
            version="anchor-cli 0.32.1",
            remediation="Add the directory to PATH.",
            details=f"Detected at {location}, but it is not on PATH.",
        )
    ]

    monkeypatch.setattr(cli_app_module, "collect_environment_diagnostics", lambda: diagnostics)

    def fake_detect(*args, **kwargs):  # pragma: no cover
        raise AssertionError("detect_missing_tools should not be called when exiting early")

    monkeypatch.setattr(cli_app_module, "detect_missing_tools", fake_detect)
    monkeypatch.setattr(cli_app_module, "installer_display_name", lambda tool: "Anchor CLI")
    monkeypatch.setattr(
        cli_app_module,
        "installer_key_for_diagnostic",
        lambda name: "anchor" if name == "Anchor" else None,
    )
    monkeypatch.setattr(cli_app_module, "install_tool", lambda *args, **kwargs: None)

    responses = ["y"]

    def scripted_prompt(_session, message: str) -> str:
        return responses.pop(0)

    monkeypatch.setattr(cli_app_module, "prompt_text", scripted_prompt)

    app = CLIApp(
        console=console,
        session_manager=manager,
        session_context=context,
        wallet_manager=wallet_manager,
        rpc_client=rpc_stub,
    )

    with pytest.raises(SystemExit):
        app._handle_environment_bootstrap()

    assert not responses

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
