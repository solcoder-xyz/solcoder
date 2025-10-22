from __future__ import annotations

from pathlib import Path

from rich.console import Console

from solcoder.cli.app import CLIApp
from solcoder.session.manager import SessionManager
from solcoder.solana.wallet import WalletManager


def _make_app(tmp_path: Path) -> CLIApp:
    session_manager = SessionManager(root=tmp_path / "sessions")
    wallet_manager = WalletManager(keys_dir=tmp_path / "keys")
    console = Console(file=None, force_terminal=False)
    app = CLIApp(
        console=console,
        session_manager=session_manager,
        session_context=session_manager.start(),
        wallet_manager=wallet_manager,
    )
    return app


def _touch_anchor_workspace(root: Path) -> None:
    (root / "programs").mkdir(parents=True, exist_ok=True)
    (root / "Anchor.toml").write_text("[workspace]\n")
    (root / "Cargo.toml").write_text("[workspace]\nmembers = []\n")


def test_session_set_project_updates_active_and_persists(tmp_path: Path, monkeypatch) -> None:
    app = _make_app(tmp_path)
    # Create two fake workspaces
    ws1 = tmp_path / "ws1"
    ws2 = tmp_path / "ws2"
    ws1.mkdir(parents=True, exist_ok=True)
    ws2.mkdir(parents=True, exist_ok=True)
    _touch_anchor_workspace(ws1)
    _touch_anchor_workspace(ws2)

    # Start in tmp_path so .solcoder resolves here
    monkeypatch.chdir(tmp_path)

    # First set to ws1 via /init-like behavior to simulate prior state
    app.session_context.metadata.active_project = str(ws1)
    app.session_manager.save(app.session_context)

    # Now switch to ws2 using the new command
    resp = app.handle_line(f"/session set project {ws2}")
    assert any("active workspace set" in msg.lower() for _r, msg in resp.messages)
    assert app.session_context.metadata.active_project == str(ws2.resolve())

    # Verify persisted file
    persisted = tmp_path / ".solcoder" / "active_workspace"
    assert persisted.exists()
    assert persisted.read_text().strip() == str(ws2.resolve())


def test_session_set_project_rejects_non_workspace(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    bad = tmp_path / "not_a_workspace"
    bad.mkdir(parents=True, exist_ok=True)
    resp = app.handle_line(f"/session set project {bad}")
    assert any("missing anchor.toml" in msg.lower() for _r, msg in resp.messages)
