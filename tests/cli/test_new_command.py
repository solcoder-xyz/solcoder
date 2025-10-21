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
    # Stub prompt_text to return defaults during tests (avoid interactive wizard)
    app._prompt_text = lambda message: ""  # type: ignore[assignment]
    return app


def test_new_inserts_program_into_existing_anchor_workspace(tmp_path: Path) -> None:
    app = _make_app(tmp_path)

    # Prepare a minimal Anchor workspace
    ws = tmp_path / "ws"
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "Anchor.toml").write_text("[workspace]\n\n[provider]\ncluster = \"devnet\"\n")
    (ws / "Cargo.toml").write_text("[workspace]\nmembers = [\n]\n")
    (ws / "programs").mkdir()

    # Insert token blueprint as program named my_token
    app.handle_line(f"/new token --dir {ws} --program my_token --force")

    # Program folder created
    assert (ws / "programs" / "my_token").is_dir()
    # Anchor.toml patched with programs.devnet entry
    anchor_text = (ws / "Anchor.toml").read_text()
    assert "[programs.devnet]" in anchor_text
    assert "my_token = \"replace-with-program-id\"" in anchor_text
    # Cargo workspace includes member
    cargo_text = (ws / "Cargo.toml").read_text()
    assert '"programs/my_token"' in cargo_text
    # Test file copied
    assert any(p.name.endswith(".ts") for p in (ws / "tests").glob("*.ts"))


def test_new_scaffolds_workspace_when_no_anchor_detected(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    dest = tmp_path / "fresh"
    app.handle_line(f"/new token --dir {dest} --program demo_token --force")
    # Full workspace created at dest
    assert (dest / "Anchor.toml").exists()
    assert (dest / "programs" / "demo_token").is_dir()
    # Answers persisted and script present
    assert (dest / "blueprint.answers.json").exists()
    assert (dest / "scripts" / "mint.ts").exists()
    # Active project updated
    assert app.session_context.metadata.active_project == str(dest)
