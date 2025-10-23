from __future__ import annotations

from pathlib import Path
from rich.console import Console

from solcoder.cli.app import CLIApp
from solcoder.session.manager import SessionManager
from solcoder.solana.wallet import WalletManager, WalletStatus
import solcoder.cli.commands.deploy as deploy_cmd
import solcoder.solana.deploy as deploy_mod


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
    app._prompt_text = lambda message: "deploy"  # type: ignore[assignment]
    app._prompt_secret = lambda *args, **kwargs: "passphrase"  # type: ignore[assignment]
    app._maybe_auto_airdrop = lambda: None  # type: ignore[assignment]
    return app


def _make_workspace(tmp_path: Path, program_name: str = "demo") -> Path:
    workspace = tmp_path / "workspace"
    (workspace / "programs" / program_name / "src").mkdir(parents=True)
    (workspace / "programs" / program_name / "src" / "lib.rs").write_text(
        'use anchor_lang::prelude::*;\n\ndeclare_id!("replace-me");\n'
    )
    (workspace / "target" / "idl").mkdir(parents=True, exist_ok=True)
    (workspace / "target" / "idl" / f"{program_name}.json").write_text('{"name":"demo"}')
    (workspace / "Anchor.toml").write_text(
        "[programs.devnet]\n"
        f"{program_name} = \"replace-me\"\n\n"
        "[provider]\n"
        "cluster = \"devnet\"\n"
    )
    return workspace


def test_deploy_command_success(monkeypatch, tmp_path: Path) -> None:
    workspace = _make_workspace(tmp_path)
    app = _make_app(tmp_path)
    app.session_context.metadata.active_project = str(workspace)
    app.session_manager.save(app.session_context)

    status = WalletStatus(
        exists=True,
        public_key="Wallet111111111111111111111111111111111111111",
        is_unlocked=False,
        wallet_path=app.wallet_manager.wallet_path,
    )
    monkeypatch.setattr(app.wallet_manager, "status", lambda: status)
    monkeypatch.setattr(app.wallet_manager, "export_wallet", lambda *_: "[1,2,3,4]")

    balances = [10.0, 9.6]

    def fake_balance(_public_key: str | None) -> float:
        return balances.pop(0) if balances else 9.6

    app._fetch_balance = fake_balance  # type: ignore[assignment]

    monkeypatch.setattr(
        deploy_mod,
        "verify_workspace",
        lambda **kwargs: deploy_mod.DeployVerification(errors=[], warnings=[], infos=[]),
    )

    program_keypair = workspace / ".solcoder" / "keys" / "programs" / "demo.json"
    program_keypair.parent.mkdir(parents=True, exist_ok=True)
    program_keypair.write_text("[]")

    monkeypatch.setattr(
        deploy_cmd,
        "_prepare_program",
        lambda *_args, **_kwargs: (program_keypair, "Demo111111111111111111111111111111111111111"),
    )

    monkeypatch.setattr(
        deploy_mod,
        "run_anchor_deploy",
        lambda **kwargs: deploy_mod.AnchorDeployResult(
            command=["anchor", "deploy"],
            cwd=workspace,
            duration_secs=1.2,
            returncode=0,
            stdout="Program Id: Demo111111111111111111111111111111111111111",
            stderr="",
            program_id="Demo111111111111111111111111111111111111111",
        ),
    )

    monkeypatch.setattr(
        deploy_mod,
        "run_anchor_build",
        lambda **kwargs: deploy_mod.CommandResult(
            command=["anchor", "build"],
            cwd=workspace,
            duration_secs=0.0,
            returncode=0,
            stdout="",
            stderr="",
        ),
    )

    response = app.handle_line("/deploy --skip-build")
    combined = "\n".join(message for _, message in response.messages)
    assert "Deploy succeeded" in combined
    assert "Demo111111111111111111111111111111111111111" in combined
    copied_idl = workspace / ".solcoder" / "idl" / "demo.json"
    assert copied_idl.exists()
