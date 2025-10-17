from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console

from solcoder.cli.app import CLIApp, StubLLM
from solcoder.core.tool_registry import build_default_registry
from solcoder.session import SessionManager
from solcoder.solana import WalletManager


@pytest.fixture()
def console() -> Console:
    return Console(file=StringIO(), force_terminal=True, color_system=None)


@pytest.fixture()
def session_bundle(tmp_path: Path) -> tuple[SessionManager, object, WalletManager]:
    manager = SessionManager(root=tmp_path / "sessions")
    context = manager.start()
    return manager, context, WalletManager(keys_dir=tmp_path / "keys")


def test_toolkits_list_shows_registered_toolkits(
    console: Console,
    session_bundle: tuple[SessionManager, object, WalletManager],
) -> None:
    session_manager, session_context, wallet_manager = session_bundle
    app = CLIApp(
        console=console,
        llm=StubLLM(),
        tool_registry=build_default_registry(),
        session_manager=session_manager,
        session_context=session_context,
        wallet_manager=wallet_manager,
    )

    response = app.handle_line("/toolkits list")

    assert any("solcoder.planning" in message for _, message in response.messages)
    assert any("solcoder.command" in message for _, message in response.messages)


def test_toolkits_tools_lists_tools_for_toolkit(
    console: Console,
    session_bundle: tuple[SessionManager, object, WalletManager],
) -> None:
    session_manager, session_context, wallet_manager = session_bundle
    app = CLIApp(
        console=console,
        llm=StubLLM(),
        tool_registry=build_default_registry(),
        session_manager=session_manager,
        session_context=session_context,
        wallet_manager=wallet_manager,
    )

    response = app.handle_line("/toolkits solcoder.planning tools")

    assert any("generate_plan" in message for _, message in response.messages)
