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
    app._prompt_text = lambda message: ""  # type: ignore[assignment]
    return app


def test_new_nft_includes_script(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    dest = tmp_path / "nft_ws"
    app.handle_line(f"/new nft --dir {dest} --program demo_nft --force")
    assert (dest / "blueprint.answers.json").exists()
    assert (dest / "scripts" / "mint.ts").exists()


def test_new_registry_includes_script(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    dest = tmp_path / "reg_ws"
    app.handle_line(f"/new registry --dir {dest} --program reg_prog --force")
    assert (dest / "blueprint.answers.json").exists()
    assert (dest / "scripts" / "registry_demo.ts").exists()


def test_new_escrow_includes_script(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    dest = tmp_path / "escrow_ws"
    app.handle_line(f"/new escrow --dir {dest} --program esc_prog --force")
    assert (dest / "blueprint.answers.json").exists()
    assert (dest / "scripts" / "escrow_demo.ts").exists()

