from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path

import solcoder.solana.deploy as deploy


def _make_workspace(tmp_path: Path, program_name: str = "demo") -> Path:
    workspace = tmp_path / "workspace"
    (workspace / "programs" / program_name / "src").mkdir(parents=True)
    (workspace / "programs" / program_name / "src" / "lib.rs").write_text(
        'use anchor_lang::prelude::*;\n\ndeclare_id!("replace-me");\n'
    )
    (workspace / "Anchor.toml").write_text(
        "[programs.devnet]\n"
        f"{program_name} = \"replace-me\"\n\n"
        "[provider]\n"
        "cluster = \"devnet\"\n"
    )
    return workspace


def test_ensure_program_keypair_updates_declare_id(tmp_path: Path) -> None:
    workspace = _make_workspace(tmp_path)
    program_root = workspace / "programs" / "demo"
    anchor_path = workspace / "Anchor.toml"
    cfg = deploy.load_anchor_config(anchor_path)

    key_path, program_id = deploy.ensure_program_keypair(workspace, "demo")
    assert key_path.exists()
    assert len(program_id) >= 32

    deploy.update_declare_id(program_root, program_id)
    content = (program_root / "src" / "lib.rs").read_text()
    assert program_id in content

    deploy.update_anchor_mapping(anchor_path, cfg, program_name="demo", program_id=program_id, cluster="devnet")
    cfg_after = deploy.load_anchor_config(anchor_path)
    assert cfg_after["programs"]["devnet"]["demo"] == program_id


def test_run_anchor_deploy_parses_program_id(monkeypatch, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    keypair = workspace / "demo.json"
    keypair.write_text("[]")

    def fake_run(cmd, cwd, capture_output, text, env=None, timeout=None, check=False):  # noqa: ARG001
        assert cmd[:2] == ["anchor", "deploy"]
        return SimpleNamespace(returncode=0, stdout="Program Id: Demo111111111111111111111111111111111111111", stderr="")

    monkeypatch.setattr(deploy.subprocess, "run", fake_run)
    result = deploy.run_anchor_deploy(project_root=workspace, program_name="demo", program_keypair=keypair)
    assert result.success
    assert result.program_id == "Demo111111111111111111111111111111111111111"


def test_run_anchor_build_primary_succeeds(monkeypatch, tmp_path: Path) -> None:
    workspace = _make_workspace(tmp_path)

    def fake_run(cmd, cwd, capture_output, text, env=None, timeout=None, check=False):  # noqa: ARG001
        assert cmd[:3] == ["solana", "program", "build"]
        return SimpleNamespace(returncode=0, stdout="Built successfully", stderr="")

    monkeypatch.setattr(deploy.subprocess, "run", fake_run)
    result = deploy.run_anchor_build(project_root=workspace, program_name="demo")
    assert result.success
    assert (result.metadata or {}).get("builder") == "solana program build"


def test_run_anchor_build_fallbacks_to_anchor_build(monkeypatch, tmp_path: Path) -> None:
    workspace = _make_workspace(tmp_path)
    calls: list[list[str]] = []

    def fake_run(cmd, cwd, capture_output, text, env=None, timeout=None, check=False):  # noqa: ARG001
        calls.append(cmd)
        if cmd[:3] == ["solana", "program", "build"]:
            return SimpleNamespace(returncode=1, stdout="", stderr="solana CLI build failed")
        if cmd[:2] == ["anchor", "build"]:
            return SimpleNamespace(returncode=0, stdout="Anchor build ok", stderr="")
        raise AssertionError(f"Unexpected command {cmd}")

    monkeypatch.setattr(deploy.subprocess, "run", fake_run)
    result = deploy.run_anchor_build(project_root=workspace, program_name="demo")
    assert result.success
    assert (result.metadata or {}).get("builder") == "anchor build"
    assert (result.metadata or {}).get("initial_error") is not None
    assert calls[0][:3] == ["solana", "program", "build"]
    assert calls[1][:2] == ["anchor", "build"]


def test_run_anchor_build_regenerates_lockfile(monkeypatch, tmp_path: Path) -> None:
    workspace = _make_workspace(tmp_path)
    calls: list[list[str]] = []
    lock_path = workspace / "Cargo.lock"
    lock_path.write_text(
        "# Autogen\nversion = 4\n"
        "dependencies = [\n \"toml_datetime 0.7.3\",\n]\n"
        "[[package]]\nname = \"toml_datetime\"\nversion = \"0.7.3\"\n"
    )

    def fake_downgrade(root: Path) -> tuple[bool, str | None]:
        return False, None

    def fake_pin(root: Path) -> tuple[bool, str | None]:
        text = lock_path.read_text()
        lock_path.write_text(
            text.replace("version = 4", "version = 3", 1).replace("toml_datetime 0.7.3", "toml_datetime 0.6.11")
        )
        return True, "pinned"

    def fake_run(cmd, cwd, capture_output, text, env=None, timeout=None, check=False):  # noqa: ARG001
        calls.append(cmd)
        if cmd[:3] == ["solana", "program", "build"]:
            if len(calls) == 1:
                return SimpleNamespace(
                    returncode=1,
                    stdout="",
                    stderr="error: failed to parse lock file\nlock file version 4 requires `-Znext-lockfile-bump`",
                )
            return SimpleNamespace(returncode=0, stdout="Built successfully", stderr="")
        if cmd[:3] == ["cargo", "+solana", "generate-lockfile"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        raise AssertionError(f"Unexpected command {cmd}")

    monkeypatch.setattr(deploy, "_downgrade_lockfile_version", fake_downgrade)
    monkeypatch.setattr(deploy, "_pin_incompatible_crates", fake_pin)
    monkeypatch.setattr(deploy.subprocess, "run", fake_run)
    result = deploy.run_anchor_build(project_root=workspace, program_name="demo")
    assert result.success
    assert (result.metadata or {}).get("lockfile_regenerated")
    assert calls[0][:3] == ["solana", "program", "build"]
    assert calls[1][:3] == ["solana", "program", "build"]
    lock_text = lock_path.read_text()
    assert "version = 3" in lock_text
    assert "toml_datetime 0.6.11" in lock_text


def test_pin_incompatible_crates(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    lock = ws / "Cargo.lock"
    lock.write_text(
        "# Autogen\nversion = 4\n"
        "[[package]]\nname = \"toml_datetime\"\nversion = \"0.7.3\"\n"
        "source = \"registry+https://example\"\nchecksum = \"abc\"\n"
        "dependencies = []\n"
        "[[package]]\nname = \"example\"\nversion = \"0.1.0\"\n"
        "dependencies = [\n \"toml_datetime 0.7.3\",\n]\n"
    )
    updated, message = deploy._pin_incompatible_crates(ws)
    assert updated
    assert message
    contents = lock.read_text()
    assert "toml_datetime 0.7.3" not in contents
    assert "toml_datetime 0.6.11" in contents


def test_downgrade_lockfile_version(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    lock = ws / "Cargo.lock"
    lock.write_text("# Autogen\nversion = 4\n")
    ok, msg = deploy._downgrade_lockfile_version(ws)
    assert ok
    assert msg
    assert "version = 3" in lock.read_text()


def test_ensure_provider_wallet_sets_defaults(tmp_path: Path) -> None:
    workspace = _make_workspace(tmp_path)
    anchor = workspace / "Anchor.toml"
    cfg = deploy.load_anchor_config(anchor)
    wallet_path = workspace / ".solcoder" / "keys" / "default_wallet.json"
    wallet_path.parent.mkdir(parents=True, exist_ok=True)
    wallet_path.write_text("[]")

    deploy.ensure_provider_wallet(anchor, cfg, wallet_path=wallet_path, cluster="devnet")
    updated = deploy.load_anchor_config(anchor)
    assert updated["provider"]["wallet"] == str(wallet_path)
    assert updated["provider"]["cluster"] == "devnet"


def test_ensure_provider_wallet_preserves_existing(tmp_path: Path) -> None:
    workspace = _make_workspace(tmp_path)
    anchor = workspace / "Anchor.toml"
    anchor.write_text(
        "[programs.devnet]\n"
        "demo = \"replace-me\"\n\n"
        "[provider]\n"
        "cluster = \"devnet\"\n"
        "wallet = \"/custom/wallet.json\"\n"
    )
    cfg = deploy.load_anchor_config(anchor)
    wallet_path = workspace / ".solcoder" / "keys" / "default_wallet.json"
    wallet_path.parent.mkdir(parents=True, exist_ok=True)
    wallet_path.write_text("[]")

    deploy.ensure_provider_wallet(anchor, cfg, wallet_path=wallet_path, cluster="devnet")
    updated = deploy.load_anchor_config(anchor)
    assert updated["provider"]["wallet"] == "/custom/wallet.json"
    assert updated["provider"]["cluster"] == "devnet"


def test_ensure_toolchain_version_sets_anchor_version(tmp_path: Path) -> None:
    workspace = _make_workspace(tmp_path)
    anchor = workspace / "Anchor.toml"
    cfg = deploy.load_anchor_config(anchor)

    deploy.ensure_toolchain_version(anchor, cfg, anchor_version="0.32.1")
    updated = deploy.load_anchor_config(anchor)
    assert updated["toolchain"]["anchor_version"] == "0.32.1"


def test_ensure_toolchain_version_updates_mismatch(tmp_path: Path) -> None:
    workspace = _make_workspace(tmp_path)
    anchor = workspace / "Anchor.toml"
    anchor.write_text(
        "[programs.devnet]\n"
        "demo = \"replace-me\"\n\n"
        "[provider]\n"
        "cluster = \"devnet\"\n\n"
        "[toolchain]\n"
        "anchor_version = \"0.30.1\"\n"
    )
    cfg = deploy.load_anchor_config(anchor)

    deploy.ensure_toolchain_version(anchor, cfg, anchor_version="0.32.1")
    updated = deploy.load_anchor_config(anchor)
    assert updated["toolchain"]["anchor_version"] == "0.32.1"


def test_verify_workspace_reports_missing_anchor(monkeypatch, tmp_path: Path) -> None:
    workspace = _make_workspace(tmp_path)

    def fake_which(binary: str) -> str | None:
        if binary == "anchor":
            return None
        return f"/usr/bin/{binary}"

    monkeypatch.setattr(deploy.shutil, "which", fake_which)
    report = deploy.verify_workspace(
        project_root=workspace,
        program_name="demo",
        cluster="devnet",
        wallet_exists=True,
        wallet_unlocked=True,
    )
    assert not report.ok
    assert any("anchor CLI" in error for error in report.errors)
