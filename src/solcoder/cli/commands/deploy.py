"""Build and deploy Anchor workspaces."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from solcoder.cli.types import CommandResponse, CommandRouter, SlashCommand
from solcoder.solana import deploy as deploy_mod

if TYPE_CHECKING:  # pragma: no cover
    from solcoder.cli.app import CLIApp


def register(app: CLIApp, router: CommandRouter) -> None:
    """Register the /deploy command."""

    def handle(app: CLIApp, args: list[str]) -> CommandResponse:
        if args and args[0] == "verify":
            return _handle_verify(app, args[1:])
        return _handle_deploy(app, args)

    router.register(
        SlashCommand(
            "deploy",
            handle,
            "Build and deploy the active Anchor workspace. Usage: /deploy [--program <name>] [--cluster <cluster>] [--skip-build] | /deploy verify",
        )
    )


def _handle_verify(app: CLIApp, args: list[str]) -> CommandResponse:
    opts, err = _parse_options(args, allow_skip_build=False)
    if err:
        return CommandResponse(messages=[("system", err)])

    workspace = _resolve_workspace(app)
    if workspace is None:
        return CommandResponse(messages=[("system", "No Anchor workspace detected. Run `/new <key>` or `/init` first.")])

    anchor_path = workspace / "Anchor.toml"
    try:
        anchor_cfg = deploy_mod.load_anchor_config(anchor_path)
    except deploy_mod.DeployError as exc:
        return CommandResponse(messages=[("system", str(exc))])

    cluster = opts.get("cluster") or _configured_cluster(app) or deploy_mod.resolve_cluster(anchor_cfg)
    program_name = opts.get("program") or deploy_mod.infer_program_name(anchor_cfg, cluster=cluster)
    if not program_name:
        return CommandResponse(
            messages=[
                (
                    "system",
                    "Unable to determine program name from Anchor.toml. Provide one explicitly with `/deploy verify --program <name>`.",
                )
            ]
        )

    status = app.wallet_manager.status()
    report = deploy_mod.verify_workspace(
        project_root=workspace,
        program_name=program_name,
        cluster=cluster,
        wallet_exists=status.exists,
        wallet_unlocked=status.is_unlocked,
    )
    lines: list[str] = []
    lines.append("Deploy verification")
    lines.append("-------------------")
    for info in report.infos:
        lines.append(f"[info] {info}")
    for warning in report.warnings:
        lines.append(f"[warn] {warning}")
    if report.errors:
        for error in report.errors:
            lines.append(f"[error] {error}")
        lines.append("Status: FAILED")
    else:
        lines.append("Status: PASS")
    return CommandResponse(messages=[("system", "\n".join(lines))])


def _handle_deploy(app: CLIApp, args: list[str]) -> CommandResponse:
    opts, err = _parse_options(args, allow_skip_build=True)
    if err:
        return CommandResponse(messages=[("system", err)])

    workspace = _resolve_workspace(app)
    if workspace is None:
        return CommandResponse(messages=[("system", "No Anchor workspace detected. Run `/new <key>` or `/init` first.")])

    anchor_path = workspace / "Anchor.toml"
    try:
        anchor_cfg = deploy_mod.load_anchor_config(anchor_path)
    except deploy_mod.DeployError as exc:
        return CommandResponse(messages=[("system", str(exc))])

    cluster = opts.get("cluster") or _configured_cluster(app) or deploy_mod.resolve_cluster(anchor_cfg)
    program_name = opts.get("program") or deploy_mod.infer_program_name(anchor_cfg, cluster=cluster)
    if not program_name:
        return CommandResponse(
            messages=[
                (
                    "system",
                    "Unable to determine program name from Anchor.toml. Provide one explicitly with `/deploy --program <name>`.",
                )
            ]
        )

    status = app.wallet_manager.status()
    verification = deploy_mod.verify_workspace(
        project_root=workspace,
        program_name=program_name,
        cluster=cluster,
        wallet_exists=status.exists,
        wallet_unlocked=status.is_unlocked,
    )
    if verification.errors:
        details = "\n".join(f"- {msg}" for msg in verification.errors)
        return CommandResponse(
            messages=[
                (
                    "system",
                    f"Deploy verification failed:\n{details}\nFix the issues above or rerun `/deploy verify`.",
                )
            ]
        )

    rpc_url = _configured_rpc(app)
    skip_build = opts.get("skip_build", False)

    try:
        program_keypair, program_id = _prepare_program(workspace, program_name, cluster, anchor_path, anchor_cfg)
    except deploy_mod.DeployError as exc:
        return CommandResponse(messages=[("system", f"Program preparation failed: {exc}")])

    app._maybe_auto_airdrop()

    summary_lines = [
        "Deploy summary:",
        f"  Workspace : {workspace}",
        f"  Program   : {program_name}",
        f"  Cluster   : {cluster}",
        f"  Program ID: {program_id}",
        f"  RPC URL   : {rpc_url}",
    ]
    if skip_build:
        summary_lines.append("  Build     : skipped")
    else:
        summary_lines.append("  Build     : anchor build")
    summary_lines.append("Type 'deploy' to confirm or anything else to cancel.")
    app.console.print("\n".join(summary_lines))

    confirmation = app._prompt_text("Confirm").strip().lower()
    if confirmation != "deploy":
        return CommandResponse(messages=[("system", "Cancelled.")])

    try:
        passphrase = app._prompt_secret("Wallet passphrase", allow_master=False)
    except Exception:  # noqa: BLE001
        return CommandResponse(messages=[("system", "Cancelled.")])

    try:
        secret = app.wallet_manager.export_wallet(passphrase)
    except Exception as exc:  # noqa: BLE001
        return CommandResponse(messages=[("system", f"Wallet export failed: {exc}")])

    balance_before = None
    try:
        balance_before = app._fetch_balance(status.public_key)
    except Exception:  # noqa: BLE001
        balance_before = None

    env = os.environ.copy()
    tmp_key = None
    try:
        tmp_key = _write_temp_key(secret)
        env["ANCHOR_WALLET"] = str(tmp_key)
        env["ANCHOR_PROVIDER_URL"] = rpc_url

        build_result = None
        if not skip_build:
            app.console.print("Running anchor build…")
            app.log_buffer.record("deploy", "anchor build started")
            build_result = deploy_mod.run_anchor_build(project_root=workspace, env=env)
            if not build_result.success:
                _record_failure_logs(app, build_result, phase="build")
                return CommandResponse(
                    messages=[
                        (
                            "system",
                            _format_failure("anchor build failed", build_result),
                        )
                    ]
                )
            app.log_buffer.record(
                "build",
                f"anchor build completed in {build_result.duration_secs:.1f}s",
            )

        app.console.print("Running anchor deploy…")
        app.log_buffer.record("deploy", "anchor deploy started")
        deploy_result = deploy_mod.run_anchor_deploy(
            project_root=workspace,
            program_name=program_name,
            program_keypair=program_keypair,
            env=env,
        )
        if not deploy_result.success:
            _record_failure_logs(app, deploy_result, phase="deploy")
            return CommandResponse(
                messages=[
                    (
                        "system",
                        _format_failure("anchor deploy failed", deploy_result),
                    )
                ]
            )

        program_id_final = deploy_result.program_id or program_id
        explorer_url = _explorer_url(program_id_final, cluster)
        app.log_buffer.record(
            "deploy",
            f"anchor deploy completed in {deploy_result.duration_secs:.1f}s (program {program_id_final})",
        )
        lines = [
            "Deploy succeeded:",
            f"  Program ID : {program_id_final}",
            f"  Explorer   : {explorer_url}" if explorer_url else "  Explorer   : (unknown cluster)",
            f"  Duration   : {deploy_result.duration_secs:.1f}s",
        ]
        result_message = "\n".join(lines)

        try:
            status_after = app.wallet_manager.status()
            balance_after = app._fetch_balance(status_after.public_key)
            _update_spend_tracking(app, status_after, balance_before, balance_after)
        except Exception:  # noqa: BLE001
            pass

        try:
            _copy_idl_artifact(workspace, program_name, app.log_buffer)
        except Exception:  # noqa: BLE001
            app.log_buffer.record("deploy", "Failed to copy IDL artifact", severity="warning")

        app.session_manager.save(app.session_context)
        return CommandResponse(messages=[("system", result_message)])
    finally:
        if tmp_key is not None:
            try:
                tmp_key.unlink(missing_ok=True)
            except Exception:
                pass


def _resolve_workspace(app: CLIApp) -> Path | None:
    metadata = getattr(app.session_context, "metadata", None)
    candidates: list[Path] = []
    if metadata and metadata.active_project:
        candidates.append(Path(metadata.active_project).expanduser())
    candidates.append(Path.cwd())
    for candidate in candidates:
        root = deploy_mod.discover_anchor_root(candidate)
        if root is not None:
            return root
    return None


def _parse_options(args: list[str], *, allow_skip_build: bool) -> tuple[dict[str, object], str | None]:
    opts: dict[str, object] = {}
    i = 0
    while i < len(args):
        tok = args[i]
        if tok == "--program" and i + 1 < len(args):
            opts["program"] = args[i + 1]
            i += 2
            continue
        if tok == "--cluster" and i + 1 < len(args):
            opts["cluster"] = args[i + 1]
            i += 2
            continue
        if tok == "--skip-build":
            if not allow_skip_build:
                return {}, "--skip-build is not supported for this command."
            opts["skip_build"] = True
            i += 1
            continue
        return {}, f"Unknown option '{tok}'."
    return opts, None


def _configured_cluster(app: CLIApp) -> str | None:
    cfg_ctx = getattr(app, "config_context", None)
    cfg = getattr(cfg_ctx, "config", None)
    cluster = getattr(cfg, "network", None) if cfg is not None else None
    if isinstance(cluster, str) and cluster.strip():
        return cluster.strip()
    return None


def _configured_rpc(app: CLIApp) -> str:
    cfg_ctx = getattr(app, "config_context", None)
    cfg = getattr(cfg_ctx, "config", None)
    rpc_url = getattr(cfg, "rpc_url", None) if cfg is not None else None
    if isinstance(rpc_url, str) and rpc_url.strip():
        return rpc_url.strip()
    return "https://api.devnet.solana.com"


def _prepare_program(
    workspace: Path,
    program_name: str,
    cluster: str,
    anchor_path: Path,
    anchor_cfg: dict[str, object],
) -> tuple[Path, str]:
    keypair_path, program_id = deploy_mod.ensure_program_keypair(workspace, program_name)
    program_root = workspace / "programs" / program_name
    deploy_mod.update_declare_id(program_root, program_id)
    deploy_mod.update_anchor_mapping(
        anchor_path,
        anchor_cfg,
        program_name=program_name,
        program_id=program_id,
        cluster=cluster,
    )
    return keypair_path, program_id


def _write_temp_key(secret: str) -> Path:
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as handle:
        handle.write(secret)
        handle.flush()
        path = Path(handle.name)
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass
    return path


def _record_failure_logs(app: CLIApp, result, *, phase: str) -> None:
    app.log_buffer.record(
        "deploy",
        f"anchor {phase} failed with code {result.returncode}",
        severity="error",
    )
    if result.stdout:
        app.log_buffer.record("deploy", f"{phase} stdout: {result.stdout[-2000:]}")
    if result.stderr:
        app.log_buffer.record("deploy", f"{phase} stderr: {result.stderr[-2000:]}", severity="error")


def _format_failure(prefix: str, result) -> str:
    lines = [f"{prefix} (exit code {result.returncode})"]
    if result.stdout:
        lines.extend(["stdout:", result.stdout])
    if result.stderr:
        lines.extend(["stderr:", result.stderr])
    return "\n".join(lines)


def _explorer_url(program_id: str | None, cluster: str) -> str | None:
    if not program_id:
        return None
    base = f"https://explorer.solana.com/address/{program_id}"
    lower = cluster.lower()
    if lower in {"devnet", "testnet"}:
        return f"{base}?cluster={lower}"
    if lower not in {"mainnet", "mainnet-beta"}:
        return f"{base}?cluster={lower}"
    return base


def _update_spend_tracking(app: CLIApp, status, balance_before: float | None, balance_after: float | None) -> None:
    try:
        before = float(balance_before or 0.0)
        after = float(balance_after or 0.0)
    except Exception:
        before = balance_before if isinstance(balance_before, (int, float)) else 0.0
        after = balance_after if isinstance(balance_after, (int, float)) else 0.0
    delta = max(0.0, before - after)
    metadata = app.session_context.metadata
    metadata.spend_amount = float(getattr(metadata, "spend_amount", 0.0) or 0.0) + float(delta)
    app._update_wallet_metadata(status, balance=after)


def _copy_idl_artifact(workspace: Path, program_name: str, log_buffer) -> None:
    target_idl = workspace / "target" / "idl" / f"{program_name}.json"
    if not target_idl.exists():
        return
    dest_dir = workspace / ".solcoder" / "idl"
    dest_dir.mkdir(parents=True, exist_ok=True)
    destination = dest_dir / target_idl.name
    shutil.copy2(target_idl, destination)
    log_buffer.record("deploy", f"IDL copied to {destination}")


__all__ = ["register"]
