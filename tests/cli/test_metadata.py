from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from rich.console import Console

from solcoder.cli.app import CLIApp
from solcoder.session.manager import SessionManager
from solcoder.solana.wallet import WalletManager, WalletStatus
import solcoder.cli.storage as storage


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
    # Non-interactive defaults
    app._prompt_text = lambda message: ""  # type: ignore[assignment]
    app._prompt_secret = lambda *args, **kwargs: "passphrase"  # type: ignore[assignment]
    return app


def test_metadata_set_writes_local_file(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    # Place a workspace
    ws = tmp_path / "ws"
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "Anchor.toml").write_text("[workspace]\n")
    app.session_context.metadata.active_project = str(ws)
    app.session_manager.save(app.session_context)

    mint = "Mint11111111111111111111111111111111111111111"
    uri = "file:///tmp/metadata.json"
    resp = app.handle_line(f"/metadata set --mint {mint} --name Demo --symbol DMO --uri {uri}")
    assert any("Saved:" in msg for _, msg in resp.messages)
    out = ws / ".solcoder" / "metadata" / f"{mint}.json"
    assert out.exists()
    content = out.read_text()
    assert "\"name\": \"Demo\"" in content


def test_metadata_upload_ipfs(monkeypatch, tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    # Minimal config with IPFS key
    app.config_context = SimpleNamespace(config=SimpleNamespace(nft_storage_api_key="TEST_KEY", rpc_url="https://api.devnet.solana.com"))
    # Create a file to upload
    src = tmp_path / "metadata.json"
    src.write_text("{\"name\":\"X\"}")

    # Mock httpx.post
    class FakeResp:
        def __init__(self) -> None:
            self.status_code = 200

        def raise_for_status(self) -> None:  # pragma: no cover
            return

        def json(self) -> dict[str, object]:  # pragma: no cover
            return {"ok": True, "value": {"cid": "bafyTEST"}}

    monkeypatch.setattr(storage.httpx, "post", lambda *a, **k: FakeResp())

    resp = app.handle_line(f"/metadata upload --file {src} --storage ipfs")
    combined = "\n".join(m for _, m in resp.messages)
    assert "https://ipfs.io/ipfs/bafyTEST" in combined


def test_metadata_upload_bundlr(monkeypatch, tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    # Active workspace for runner location
    ws = tmp_path / "ws"
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "Anchor.toml").write_text("[workspace]\n")
    app.session_context.metadata.active_project = str(ws)
    app.session_manager.save(app.session_context)

    # Create file
    src = tmp_path / "metadata.json"
    src.write_text("{\"name\":\"X\"}")

    # Mock bundlr upload
    import solcoder.cli.commands.metadata as md
    import solcoder.cli.storage as storage

    monkeypatch.setattr(md, "bundlr_upload", lambda *a, **k: "https://arweave.net/FAKE")
    # Mock wallet
    ws_status = WalletStatus(exists=True, public_key="PUBKEY11111111111111111111111111111111", is_unlocked=False, wallet_path=tmp_path / "k.json")
    monkeypatch.setattr(app.wallet_manager, "status", lambda: ws_status)
    monkeypatch.setattr(app.wallet_manager, "export_wallet", lambda passphrase: "[1,2,3]")

    resp = app.handle_line(f"/metadata upload --file {src} --storage bundlr")
    combined = "\n".join(m for _, m in resp.messages)
    assert "https://arweave.net/FAKE" in combined


def test_bundlr_upload_invokes_runner(monkeypatch, tmp_path: Path) -> None:
    # Create dummy file to upload
    asset = tmp_path / "meta.json"
    asset.write_text("{\"name\": \"demo\"}")

    # Pretend npm/npx exist
    monkeypatch.setattr(storage.shutil, "which", lambda cmd: f"/usr/bin/{cmd}")

    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        if cmd and cmd[0] == "npm":
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if cmd and cmd[0] == "npx":
            return SimpleNamespace(returncode=0, stdout="https://arweave.net/UPLOADED\n", stderr="")
        raise AssertionError(f"Unexpected command {cmd}")

    monkeypatch.setattr(storage.subprocess, "run", fake_run)

    url = storage.bundlr_upload(
        asset,
        rpc_url="https://api.devnet.solana.com",
        key_json="[1,2,3,4]",
        workspace_root=tmp_path,
    )

    assert url == "https://arweave.net/UPLOADED"
    assert len(calls) == 2
    npm_cmd, npm_kwargs = calls[0]
    assert npm_cmd == ["npm", "install"]
    assert npm_kwargs["cwd"] == str(tmp_path / ".solcoder" / "uploader_runner")
    npx_cmd, _ = calls[1]
    assert "--contentType" in npx_cmd
    idx = npx_cmd.index("--contentType")
    assert npx_cmd[idx + 1] == "application/json"
