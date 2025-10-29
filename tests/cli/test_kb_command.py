from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console

from solcoder.cli.app import CLIApp
from solcoder.cli.stub_llm import StubLLM
from solcoder.core.knowledge_base import KnowledgeBaseError
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


def _build_app(
    console: Console,
    session_bundle: tuple[SessionManager, object, WalletManager],
) -> CLIApp:
    session_manager, session_context, wallet_manager = session_bundle
    return CLIApp(
        console=console,
        llm=StubLLM(),
        tool_registry=build_default_registry(),
        session_manager=session_manager,
        session_context=session_context,
        wallet_manager=wallet_manager,
    )


def test_kb_command_returns_answer(console: Console, session_bundle) -> None:
    app = _build_app(console, session_bundle)

    class FakeClient:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def query(self, question: str):
            self.calls.append(question)
            return type(
                "Answer",
                (),
                {"text": "Proof of History enables ordering.", "citations": ["Solana Whitepaper"]},
            )

    fake_client = FakeClient()
    setattr(app, "_knowledge_base_client", fake_client)

    response = app.handle_line('/kb "Explain Proof of History"')
    assert any("Proof of History enables ordering." in msg for _, msg in response.messages)
    assert any("Sources" in msg for _, msg in response.messages)
    assert fake_client.calls == ["Explain Proof of History"]


def test_kb_command_requires_query(console: Console, session_bundle) -> None:
    app = _build_app(console, session_bundle)
    response = app.handle_line("/kb")
    assert any("Usage: /kb" in message for _, message in response.messages)


def test_kb_command_handles_errors(console: Console, session_bundle) -> None:
    app = _build_app(console, session_bundle)

    class FailingClient:
        def query(self, _question: str):
            raise KnowledgeBaseError("missing knowledge pack")

    setattr(app, "_knowledge_base_client", FailingClient())
    response = app.handle_line('/kb "status?"')
    assert any("missing knowledge pack" in message for _, message in response.messages)
