from __future__ import annotations

from pathlib import Path

from rich.console import Console

from solcoder.cli.app import CLIApp
from solcoder.session.manager import SessionManager
from solcoder.solana.wallet import WalletManager


def _make_app(tmp_path: Path) -> CLIApp:
    # Isolate session and wallet under tmp_path
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


def _patch_anchor_version(monkeypatch, value: str = "0.32.1") -> None:
    monkeypatch.setattr(
        "solcoder.cli.commands.init.deploy_mod.detect_anchor_cli_version",
        lambda: value,
    )


def test_init_offline_scaffold_in_dir(tmp_path: Path, monkeypatch) -> None:
    app = _make_app(tmp_path)
    _patch_anchor_version(monkeypatch)
    target = tmp_path / "ws"
    resp = app.handle_line(f"/init {target} --offline")
    assert any("initialized" in msg.lower() for _r, msg in resp.messages)
    # Files exist
    assert (target / "Anchor.toml").exists()
    assert (target / "Cargo.toml").exists()
    assert (target / "programs").is_dir()
    # Session active project updated
    assert app.session_context.metadata.active_project == str(target)
    anchor_text = (target / "Anchor.toml").read_text()
    assert 'anchor_version = "0.32.1"' in anchor_text


def test_init_detect_existing_workspace_noop(tmp_path: Path, monkeypatch) -> None:
    app = _make_app(tmp_path)
    _patch_anchor_version(monkeypatch)
    target = tmp_path / "ws2"
    # First init
    app.handle_line(f"/init {target} --offline")
    # Second init should detect existing Anchor.toml
    resp = app.handle_line(f"/init {target}")
    assert any("already initialized" in msg.lower() for _r, msg in resp.messages)
    assert app.session_context.metadata.active_project == str(target)


def test_init_non_empty_dir_requires_force(tmp_path: Path, monkeypatch) -> None:
    app = _make_app(tmp_path)
    _patch_anchor_version(monkeypatch)
    target = tmp_path / "ws3"
    target.mkdir(parents=True, exist_ok=True)
    (target / "README.txt").write_text("hello")
    resp = app.handle_line(f"/init {target} --offline")
    assert any("not empty" in msg.lower() for _r, msg in resp.messages)
    # With --force succeeds
    resp2 = app.handle_line(f"/init {target} --offline --force")
    assert any("initialized" in msg.lower() for _r, msg in resp2.messages)
    assert (target / "Anchor.toml").exists()
    anchor_text = (target / "Anchor.toml").read_text()
    assert 'anchor_version = "0.32.1"' in anchor_text


def test_init_default_current_directory(tmp_path: Path, monkeypatch) -> None:
    app = _make_app(tmp_path)
    _patch_anchor_version(monkeypatch)
    cwd = tmp_path / "here"
    cwd.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(cwd)
    resp = app.handle_line("/init --offline")
    assert any("initialized" in msg.lower() for _r, msg in resp.messages)
    assert (cwd / "Anchor.toml").exists()
    assert app.session_context.metadata.active_project == str(cwd)
    anchor_text = (cwd / "Anchor.toml").read_text()
    assert 'anchor_version = "0.32.1"' in anchor_text
