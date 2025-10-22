"""Blueprint pipeline: /new <key> with optional wizard + render."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
import tempfile
import shutil
import re
import os
import subprocess
from typing import TYPE_CHECKING

from solcoder.cli.types import CommandResponse, CommandRouter, SlashCommand
from solcoder.core import RenderOptions, TemplateError, available_templates, render_template
from solcoder.cli.blueprints import (
    load_registry,
    load_wizard_schema,
    prompt_wizard,
    resolve_registry_template_path,
)
import json

if TYPE_CHECKING:  # pragma: no cover
    from solcoder.cli.app import CLIApp


KNOWN_KEYS = {"counter", "token", "nft", "registry", "escrow"}


def _prompt_or_default(app: CLIApp, prompt: str, default: str) -> str:
    try:
        resp = app._prompt_text(f"{prompt} [{default}]")
        return resp.strip() or default
    except Exception:
        return default


def register(app: CLIApp, router: CommandRouter) -> None:
    """Register the /new command."""

    def handle(app: CLIApp, args: list[str]) -> CommandResponse:
        if not args:
            keys = ", ".join(sorted(KNOWN_KEYS))
            return CommandResponse(messages=[("system", f"Usage: /new <key> [--dir <path>] [--program <name>] [--author <pubkey>] [--cluster <cluster>] [--program-id <id>] [--force]\nAvailable keys: {keys}")])

        key = args[0].strip().lower()
        # Parse flags
        dest: Path | None = None
        program_name: str | None = None
        author: str | None = None
        program_id: str | None = None
        cluster: str | None = None
        force = False

        i = 1
        while i < len(args):
            tok = args[i]
            if tok == "--dir" and i + 1 < len(args):
                dest = Path(args[i + 1]).expanduser()
                i += 2
                continue
            if tok == "--program" and i + 1 < len(args):
                program_name = args[i + 1]
                i += 2
                continue
            if tok == "--author" and i + 1 < len(args):
                author = args[i + 1]
                i += 2
                continue
            if tok == "--program-id" and i + 1 < len(args):
                program_id = args[i + 1]
                i += 2
                continue
            if tok == "--cluster" and i + 1 < len(args):
                cluster = args[i + 1]
                i += 2
                continue
            if tok == "--force":
                force = True
                i += 1
                continue
            return CommandResponse(messages=[("system", f"Unknown or misplaced argument '{tok}'.")])

        # Key mapping / selection
        templates = set(available_templates())
        registry = load_registry()
        if key not in KNOWN_KEYS:
            # Free-text: try LLM minimal selection first with strict JSON; fall back to prompt
            try:
                reg = load_registry()
                options_list = [e.key for e in reg if e.key]
                if not options_list:
                    options_list = sorted(KNOWN_KEYS)
                options_str = ", ".join(options_list)
                system = (
                    "You are a strict router. Select exactly one blueprint key from the provided list. "
                    "Respond ONLY with a minified JSON object of the form {\"key\":\"<value>\"} where <value> is one of the allowed keys."
                )
                user = (
                    f"Allowed keys: [{options_str}]\\n"
                    f"Request: {' '.join(args)}\\n"
                    "Return strictly: {\"key\":\"<one_of_allowed>\"}"
                )
                resp = app._llm.stream_chat(user, system_prompt=system, history=None)
                raw = (resp.text or "").strip()
                candidate_key: str | None = None
                # Try JSON parse first
                try:
                    obj = json.loads(raw)
                    val = obj.get("key") if isinstance(obj, dict) else None
                    if isinstance(val, str):
                        candidate_key = val.strip().lower()
                except Exception:
                    # Try to extract with a simple pattern
                    m = re.search(r'"key"\s*:\s*"([a-zA-Z0-9_-]+)"', raw)
                    if m:
                        candidate_key = m.group(1).lower()
                if candidate_key in KNOWN_KEYS:
                    key = candidate_key  # type: ignore[assignment]
                else:
                    raise ValueError("invalid llm selection JSON")
            except Exception:
                options = ", ".join(sorted(KNOWN_KEYS))
                chosen = _prompt_or_default(app, f"Select a blueprint key ({options})", "counter")
                key = chosen.strip().lower()
                if key not in KNOWN_KEYS:
                    return CommandResponse(messages=[("system", f"Invalid key '{key}'. Available: {options}")])

        # Wizard (load per-blueprint schema if available)
        defaults = app._default_template_metadata()
        wizard_qs = load_wizard_schema(key)
        answers: dict[str, any] = {}

        if wizard_qs:
            # seed defaults
            cfg_ctx = getattr(app, "config_context", None)
            network = None
            if cfg_ctx is not None and getattr(cfg_ctx, "config", None) is not None:
                network = getattr(cfg_ctx.config, "network", None)
            # Prefer the selected key for program_name default rather than the global default (counter)
            seed = {
                "program_name": program_name or key,
                "author_pubkey": author or defaults.get("author_pubkey", "CHANGEME"),
                "cluster": cluster or network or "devnet",
                "program_id": program_id or "replace-with-program-id",
            }
            if key == "token":
                seed.setdefault("token_mode", "quick")
                seed.setdefault("decimals", 9)
                seed.setdefault("initial_supply", "0")
            answers = prompt_wizard(app, wizard_qs, seed)
            if key == "token":
                token_mode = (answers.get("token_mode") or seed.get("token_mode", "program")).strip().lower()
                if token_mode == "quick":
                    cluster_hint = answers.get("cluster") or seed.get("cluster")
                    decimals_value = answers.get("decimals", seed.get("decimals"))
                    supply_value = answers.get("initial_supply", seed.get("initial_supply"))
                    return _spl_token_quick_flow(
                        app,
                        decimals_input=decimals_value,
                        supply_input=supply_value,
                        cluster_hint=cluster_hint,
                    )
            program_name = answers.get("program_name") or seed["program_name"]
            author = answers.get("author_pubkey") or seed["author_pubkey"]
            cluster = answers.get("cluster") or seed["cluster"]
            program_id = answers.get("program_id") or seed["program_id"]
        else:
            if program_name is None:
                # Default to the blueprint key for program name rather than the global default (counter)
                program_name = _prompt_or_default(app, "Program name", key)
            if author is None:
                author = defaults.get("author_pubkey", "CHANGEME")
            if cluster is None:
                cfg = getattr(app, "config_context", None)
                cluster = getattr(getattr(cfg, "config", None), "network", "devnet")
            if program_id is None:
                program_id = "replace-with-program-id"

        # Destination base (used both for scaffold and for workspace detection)
        base_dir = dest or Path.cwd()

        # Detect existing Anchor workspace to insert program under programs/
        def _find_anchor_root(start: Path) -> Path | None:
            try:
                cur = start.resolve()
            except Exception:
                cur = start.expanduser()
            for parent in [cur, *cur.parents]:
                if (parent / "Anchor.toml").exists():
                    return parent
            return None

        workspace_root = _find_anchor_root(base_dir)
        if workspace_root is None:
            # Fallback to active project if it looks like an Anchor workspace
            try:
                active = getattr(app.session_context.metadata, "active_project", None)
                if active:
                    ap = Path(active).expanduser()
                    if (ap / "Anchor.toml").exists():
                        workspace_root = ap
            except Exception:
                pass

        # Resolve template path from registry if present; otherwise fallback to templates/
        template_path = None
        try:
            entry = next((e for e in registry if e.key == key), None)
            if entry is not None and entry.template_path:
                template_path = resolve_registry_template_path(entry.template_path)
        except Exception:
            template_path = None
        if template_path is None and key not in templates:
            msg = (
                f"Blueprint '{key}' is not available locally. Available templates: {', '.join(sorted(templates)) or '(none)'}"
            )
            return CommandResponse(messages=[("system", msg)])

        if workspace_root is not None:
            # Hand off insertion to agent/CLI via /blueprint scaffold
            try:
                answers_json = json.dumps(answers or {
                    "program_name": program_name,
                    "author_pubkey": author,
                    "cluster": cluster or "devnet",
                    "program_id": program_id,
                }, separators=(",", ":"))
            except Exception:
                answers_json = "{}"
            import shlex as _shlex
            cmd_parts = [
                "/blueprint",
                "scaffold",
                "--key",
                key,
                "--target",
                str(workspace_root),
                "--workspace",
                str(workspace_root),
                "--answers-json",
                answers_json,
            ]
            if force:
                cmd_parts.append("--force")
            dispatch = " ".join(_shlex.quote(p) for p in cmd_parts)
            # Execute immediately for synchronous behavior in CLI/tests
            routed = app.command_router.dispatch(app, dispatch[1:] if dispatch.startswith("/") else dispatch)
            return routed

        # Otherwise scaffold a fresh workspace at dest
        dest = base_dir if dest is not None else (Path.cwd() / f"{program_name}-workspace")
        options = RenderOptions(
            template=key,
            destination=dest,
            program_name=program_name,
            author_pubkey=author,
            program_id=program_id,
            cluster=cluster or "devnet",
            overwrite=force,
            template_path=template_path,
        )
        # Hand off fresh scaffold to agent/CLI via /blueprint scaffold
        try:
            answers_json = json.dumps(answers or {
                "program_name": program_name,
                "author_pubkey": author,
                "cluster": cluster or "devnet",
                "program_id": program_id,
            }, separators=(",", ":"))
        except Exception:
            answers_json = "{}"
        target_dir = dest
        import shlex as _shlex
        cmd_parts = [
            "/blueprint",
            "scaffold",
            "--key",
            key,
            "--target",
            str(target_dir),
            "--answers-json",
            answers_json,
        ]
        if force:
            cmd_parts.append("--force")
        dispatch = " ".join(_shlex.quote(p) for p in cmd_parts)
        routed = app.command_router.dispatch(app, dispatch[1:] if dispatch.startswith("/") else dispatch)
        return routed

    router.register(
        SlashCommand(
            "new",
            handle,
            "Create a new blueprint: /new <key> [--dir <path>] [--program <name>] [--author <pubkey>] [--cluster <cluster>] [--program-id <id>] [--force]",
        )
    )


__all__ = ["register"]
def _decimal_to_cli_string(amount: Decimal) -> str:
    text = format(amount, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _parse_decimal(value: str | int | float | Decimal, *, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f"'{field}' must be numeric.")


def _determine_rpc_and_cluster(app: "CLIApp") -> tuple[str, str]:
    cfg_ctx = getattr(app, "config_context", None)
    cfg = getattr(cfg_ctx, "config", None)
    rpc_url = getattr(cfg, "rpc_url", "https://api.devnet.solana.com")
    cluster = getattr(cfg, "network", "devnet")
    return rpc_url, cluster


def _spl_token_quick_flow(
    app: "CLIApp",
    *,
    decimals_input: str | int | float | None,
    supply_input: str | int | float | None,
    cluster_hint: str | None,
) -> CommandResponse:
    if shutil.which("spl-token") is None:
        return CommandResponse(messages=[("system", "spl-token CLI not found in PATH. Install it or run `/env install spl-token`.")])

    status = app.wallet_manager.status()
    if not status.exists or not status.public_key:
        return CommandResponse(messages=[("system", "No SolCoder wallet found. Run `/wallet create` or `/wallet restore` first.")])

    # Parse decimals and supply
    decimals_raw = decimals_input if decimals_input is not None else 9
    try:
        decimals = int(str(decimals_raw))
    except ValueError:
        return CommandResponse(messages=[("system", "'decimals' must be an integer between 0 and 9.")])
    if decimals < 0 or decimals > 9:
        return CommandResponse(messages=[("system", "'decimals' must be between 0 and 9.")])

    supply_raw = supply_input if supply_input is not None else "0"
    try:
        supply = _parse_decimal(supply_raw, field="initial_supply")
    except ValueError as exc:
        return CommandResponse(messages=[("system", str(exc))])
    if supply < 0:
        return CommandResponse(messages=[("system", "Initial supply cannot be negative.")])

    scale = Decimal(10) ** decimals
    base_units = supply * scale
    if base_units != base_units.to_integral_value():
        return CommandResponse(messages=[("system", f"Initial supply exceeds the precision allowed by {decimals} decimals.")])

    supply_cli_str = _decimal_to_cli_string(supply)

    rpc_url, config_cluster = _determine_rpc_and_cluster(app)
    cluster = cluster_hint or config_cluster

    summary_lines = [
        "Quick SPL token mint:",
        f"  Wallet: {status.masked_address}",
        f"  Decimals: {decimals}",
        f"  Initial supply: {supply_cli_str}",
        f"  Cluster: {cluster}",
        "Type 'mint' to confirm or anything else to cancel.",
    ]
    app.console.print("\n".join(summary_lines))
    passphrase = app._prompt_secret("Wallet passphrase", allow_master=False)
    ack = app._prompt_text("Confirm").strip().lower()
    if ack != "mint":
        return CommandResponse(messages=[("system", "Cancelled.")])

    try:
        secret = app.wallet_manager.export_wallet(passphrase)
    except Exception as exc:  # noqa: BLE001
        return CommandResponse(messages=[("system", f"Failed to export wallet: {exc}")])

    key_path: Path | None = None
    try:
        handle = tempfile.NamedTemporaryFile("w", delete=False, suffix=".json")
        with handle:
            handle.write(secret)
            handle.flush()
            key_path = Path(handle.name)
        try:
            os.chmod(key_path, 0o600)
        except PermissionError:
            pass

        # Basic base58 validation helpers
        _B58 = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")

        def _looks_like_pubkey(value: str) -> bool:
            v = value.strip()
            return 32 <= len(v) <= 64 and all(c in _B58 for c in v)

        def _extract_pubkey_from_text(text: str) -> str | None:
            for token in text.replace(",", " ").split():
                if _looks_like_pubkey(token):
                    return token
            return None

        def _run_cmd(args: list[str]) -> subprocess.CompletedProcess[str]:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                check=False,
            )
            return result

        def _extract_from_json(stdout: str) -> dict[str, str]:
            out: dict[str, str] = {}
            try:
                data = json.loads(stdout)
            except Exception:
                return out

            def _walk(node: object) -> None:
                if isinstance(node, dict):
                    for k, v in node.items():
                        if isinstance(v, (str, int, float)):
                            sval = str(v)
                            kl = str(k).lower()
                            if kl in {"signature", "tx", "transaction", "sig"}:
                                out.setdefault("signature", sval)
                            if kl in {"address", "mint", "token", "account", "ata", "associatedtokenaddress"}:
                                out.setdefault(kl, sval)
                        else:
                            _walk(v)
                elif isinstance(node, list):
                    for it in node:
                        _walk(it)

            _walk(data)
            return out

        def _parse_created_address(stdout: str, keyword: str) -> str | None:
            # Prefer JSON when available
            meta = _extract_from_json(stdout)
            for key in ("mint", "token", "address"):
                if meta.get(key):
                    return meta[key]
            # Fallback to text parsing
            lower_kw = keyword.lower()
            for line in stdout.splitlines():
                text = line.strip()
                if text.lower().startswith(f"creating {lower_kw}"):
                    # Try to extract a plausible base58 public key
                    candidate = _extract_pubkey_from_text(text)
                    if candidate:
                        return candidate
            return None

        def _parse_signature(stdout: str) -> str | None:
            meta = _extract_from_json(stdout)
            if meta.get("signature"):
                return meta["signature"]
            for line in stdout.splitlines():
                if "Signature" in line:
                    return line.split(":", 1)[-1].strip()
            return None

        # 1) Create mint
        create_token_cmd = [
            "spl-token",
            "create-token",
            "--decimals",
            str(decimals),
            "--fee-payer",
            str(key_path),
            "--mint-authority",
            status.public_key,
            "--program-2022",
            "--output",
            "json",
            "--url",
            rpc_url,
        ]
        create_result = _run_cmd(create_token_cmd)
        if create_result.returncode != 0:
            err = create_result.stderr.strip() or create_result.stdout.strip() or "spl-token create-token failed."
            return CommandResponse(messages=[("system", err)])
        mint_address = _parse_created_address(create_result.stdout, "token")
        mint_signature = _parse_signature(create_result.stdout)

        if not mint_address:
            return CommandResponse(messages=[("system", "Unable to determine mint address from spl-token output.")])

        # 2) Create associated token account for wallet
        create_account_cmd = [
            "spl-token",
            "create-account",
            mint_address,
            "--owner",
            status.public_key,
            "--fee-payer",
            str(key_path),
            "--program-2022",
            "--output",
            "json",
            "--url",
            rpc_url,
        ]
        account_result = _run_cmd(create_account_cmd)
        if account_result.returncode != 0:
            err = account_result.stderr.strip() or account_result.stdout.strip() or "spl-token create-account failed."
            return CommandResponse(messages=[("system", err)])
        account_address = _parse_created_address(account_result.stdout, "account")
        account_signature = _parse_signature(account_result.stdout)
        if not account_address:
            # Fallback: compute ATA deterministically via spl-token address
            addr_cmd = [
                "spl-token",
                "address",
                "--verbose",
                "--token",
                mint_address,
                "--owner",
                status.public_key,
                "--program-2022",
                "--url",
                rpc_url,
            ]
            addr_result = _run_cmd(addr_cmd)
            if addr_result.returncode == 0:
                meta = _extract_from_json(addr_result.stdout)
                account_address = meta.get("address") or meta.get("ata") or meta.get("account")
                if not account_address:
                    # treat stdout as a bare address
                    lines = [ln.strip() for ln in addr_result.stdout.splitlines() if ln.strip()]
                    # Prefer explicit "Associated token address:" line when present
                    for ln in lines:
                        if "associated token address" in ln.lower():
                            cand = _extract_pubkey_from_text(ln)
                            if cand:
                                account_address = cand
                                break
                    # Otherwise pick the last base58-looking token in the output
                    if not account_address:
                        candidates: list[str] = []
                        for ln in lines:
                            cand = _extract_pubkey_from_text(ln)
                            if cand:
                                candidates.append(cand)
                        if candidates:
                            # avoid picking the wallet address if that's included first
                            for cand in reversed(candidates):
                                if cand != (status.public_key or ""):
                                    account_address = cand
                                    break
        if not account_address:
            # Surface the mint address so the user can proceed manually if needed
            explorer = f"https://explorer.solana.com/address/{mint_address}"
            if cluster and cluster not in {"mainnet", "mainnet-beta"}:
                explorer = f"{explorer}?cluster={cluster}"
            hint_lines = [
                "Unable to determine associated token account address from spl-token output.",
                f"Mint (created): {mint_address}",
                f"Explorer: {explorer}",
                "You can fetch the ATA and retry mint manually:",
                f"  spl-token address --verbose --token {mint_address} --owner {status.public_key} --program-2022 -u {rpc_url}",
            ]
            return CommandResponse(messages=[("system", "\n".join(hint_lines))])

        mint_tx_signature: str | None = None
        minted_amount_display: str | None = None
        if supply > 0:
            minted_amount_display = supply_cli_str
            mint_cmd = [
                "spl-token",
                "mint",
                mint_address,
                supply_cli_str,
                "--mint-authority",
                str(key_path),
                "--fee-payer",
                str(key_path),
                "--program-2022",
                "--output",
                "json",
                "--url",
                rpc_url,
            ]
            mint_cmd.append(account_address)
            mint_result = _run_cmd(mint_cmd)
            if mint_result.returncode != 0:
                err = mint_result.stderr.strip() or mint_result.stdout.strip() or "spl-token mint failed."
                return CommandResponse(messages=[("system", err)])
            mint_tx_signature = _parse_signature(mint_result.stdout)

    finally:
        try:
            if key_path:
                key_path.unlink(missing_ok=True)
        except Exception:
            pass

    explorer = f"https://explorer.solana.com/address/{mint_address}"
    if cluster and cluster not in {"mainnet", "mainnet-beta"}:
        explorer = f"{explorer}?cluster={cluster}"

    lines = [
        "✅ Quick SPL token created.",
        f"Mint: {mint_address}",
    ]
    if mint_signature:
        lines.append(f"Mint signature: {mint_signature}")
    if account_address:
        detail = f"Wallet ATA: {account_address}"
        if account_signature:
            detail += f" (signature: {account_signature})"
        lines.append(detail)
    if mint_tx_signature and minted_amount_display:
        lines.append(f"Minted {minted_amount_display} tokens (signature: {mint_tx_signature})")
    lines.append(f"Explorer: {explorer}")

    app.log_event("token", f"Quick SPL token created: {mint_address}")
    return CommandResponse(messages=[("system", "\n".join(lines))])
