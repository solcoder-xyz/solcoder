from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from rich.console import Console

from solcoder.cli.app import CLIApp
from solcoder.session.manager import SessionManager
from solcoder.solana.wallet import WalletManager, WalletStatus
from solcoder.solana.constants import TOKEN_2022_PROGRAM_ID


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
    def _default_prompt(message: str) -> str:
        if "Token type" in message:
            return "program"
        return ""

    app._prompt_text = _default_prompt  # type: ignore[assignment]
    return app


def _patch_anchor_version(monkeypatch, value: str = "0.32.1") -> None:
    monkeypatch.setattr(
        "solcoder.cli.commands.blueprint.deploy_mod.detect_anchor_cli_version",
        lambda: value,
    )


def test_new_inserts_program_into_existing_anchor_workspace(tmp_path: Path, monkeypatch) -> None:
    app = _make_app(tmp_path)
    _patch_anchor_version(monkeypatch)
    monkeypatch.chdir(tmp_path)

    # Prepare a minimal Anchor workspace
    ws = tmp_path / "ws"
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "Anchor.toml").write_text("[workspace]\n\n[provider]\ncluster = \"devnet\"\n")
    (ws / "Cargo.toml").write_text("[workspace]\nmembers = [\n]\n")
    (ws / "programs").mkdir()

    # Insert token blueprint as program named my_token
    app.handle_line(f"/new token --dir {ws} --program my_token --force")

    # Program folder and scripts created
    assert (ws / "programs" / "my_token").is_dir()
    assert (ws / "scripts").is_dir()
    # Anchor.toml patched with programs.devnet entry
    anchor_text = (ws / "Anchor.toml").read_text()
    assert "[programs.devnet]" in anchor_text
    assert "my_token = \"replace-with-program-id\"" in anchor_text
    assert 'anchor_version = "0.32.1"' in anchor_text
    # Cargo workspace includes member
    cargo_text = (ws / "Cargo.toml").read_text()
    assert '"programs/my_token"' in cargo_text
    # Test file copied
    assert any(p.name.endswith(".ts") for p in (ws / "tests").glob("*.ts"))


def test_new_scaffolds_workspace_when_no_anchor_detected(tmp_path: Path, monkeypatch) -> None:
    app = _make_app(tmp_path)
    _patch_anchor_version(monkeypatch)
    monkeypatch.chdir(tmp_path)
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
    anchor_text = (dest / "Anchor.toml").read_text()
    assert 'anchor_version = "0.32.1"' in anchor_text


def test_new_uses_active_workspace_when_no_dir_specified(tmp_path: Path, monkeypatch) -> None:
    app = _make_app(tmp_path)
    _patch_anchor_version(monkeypatch)
    monkeypatch.chdir(tmp_path)
    # Create an Anchor workspace and set as active project
    ws = tmp_path / "active_ws"
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "Anchor.toml").write_text("[workspace]\n\n[provider]\ncluster = \"devnet\"\n")
    (ws / "Cargo.toml").write_text("[workspace]\nmembers = [\n]\n")
    (ws / "programs").mkdir()
    app.session_context.metadata.active_project = str(ws)
    app.session_manager.save(app.session_context)

    # Run /new without --dir; should insert into active workspace
    app.handle_line("/new token --program my_tok --force")
    assert (ws / "programs" / "my_tok").is_dir()
    anchor_text = (ws / "Anchor.toml").read_text()
    assert 'anchor_version = "0.32.1"' in anchor_text


def test_new_token_quick_flow(monkeypatch, tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    _patch_anchor_version(monkeypatch)
    monkeypatch.chdir(tmp_path)

    mint_address = "Mint1111111111111111111111111111111111"
    ata_address = "ATA11111111111111111111111111111111111"

    prompts = {
        "Token type": "quick",
        "Decimals": "6",
        "Initial supply": "123.45",
        "Write metadata on-chain now? [Y/n]": "y",
        "Confirm (mint)": "mint",
    }

    def _prompt_text(message: str) -> str:
        for key, value in prompts.items():
            if message.startswith(key):
                return value
        return ""

    app._prompt_text = _prompt_text  # type: ignore[assignment]
    app._prompt_secret = lambda *args, **kwargs: "passphrase"  # type: ignore[assignment]

    wallet_status = WalletStatus(
        exists=True,
        public_key="FAKEPUBKEY1234567890",
        is_unlocked=False,
        wallet_path=tmp_path / "wallet.json",
    )
    monkeypatch.setattr(app.wallet_manager, "status", lambda: wallet_status)
    monkeypatch.setattr(app.wallet_manager, "export_wallet", lambda passphrase: "[1,2,3]")
    monkeypatch.setattr("solcoder.cli.commands.new.shutil.which", lambda _: "/usr/bin/spl-token")

    import solcoder.cli.commands.metadata as metadata_cmd

    monkeypatch.setattr(metadata_cmd, "_is_token2022_mint", lambda mint, rpc: True)

    monkeypatch.setattr(
        metadata_cmd,
        "_write_metadata_via_spl_token",
        lambda *args, **kwargs: (
            True,
            ["Token-2022 metadata initialized on-chain via spl-token."],
            "https://arweave.net/token",
        ),
    )

    commands: list[list[str]] = []

    def _fake_run(cmd, *, capture_output, text, check):
        commands.append(cmd)
        if cmd[1] == "create-token":
            stdout = f"{{\n  \"address\": \"{mint_address}\", \"signature\": \"SigToken\"\n}}\n"
        elif cmd[1] == "create-account":
            stdout = f"{{\n  \"address\": \"{ata_address}\", \"signature\": \"SigAccount\"\n}}\n"
        elif cmd[1] == "mint":
            stdout = "{\n  \"signature\": \"SigMint\"\n}\n"
        else:
            raise AssertionError(f"Unexpected command {cmd}")
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr("solcoder.cli.commands.new.subprocess.run", _fake_run)

    response = app.handle_line("/new token")

    assert [cmd[1] for cmd in commands] == ["create-token", "create-account", "mint"]
    assert "--decimals" in commands[0] and "6" in commands[0]
    for cmd in commands[:3]:
        assert "--program-id" in cmd
        assert TOKEN_2022_PROGRAM_ID in cmd
    assert commands[2][-1] == ata_address

    combined = "\n".join(message for _, message in response.messages)
    assert "Quick SPL token created" in combined
    assert f"Mint: {mint_address}" in combined
    assert "Minted 123.45 tokens" in combined
    assert f"Explorer: https://explorer.solana.com/address/{mint_address}?cluster=devnet" in combined
