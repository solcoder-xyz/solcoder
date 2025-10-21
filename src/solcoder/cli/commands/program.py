"""On-chain program interaction commands (Anchor-first)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any
import asyncio
import os

from rich.table import Table

from solcoder.cli.types import CommandResponse, CommandRouter, SlashCommand

if TYPE_CHECKING:  # pragma: no cover
    from solcoder.cli.app import CLIApp


SPL_CATALOG: dict[str, dict[str, Any]] = {
    # Memo program (write-only, no accounts required beyond signer)
    "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr": {
        "name": "spl-memo",
        "instructions": [
            {
                "name": "memo",
                "args": [{"name": "memo", "type": "string"}],
                "accounts": [],
                "description": "Attach a memo to a transaction (requires a transfer or memo-supporting CLI).",
            }
        ],
    },
    # SPL Token v1 program (common operations; schema-only for listing)
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA": {
        "name": "spl-token",
        "instructions": [
            {
                "name": "transfer",
                "args": [{"name": "amount", "type": "u64"}],
                "accounts": [
                    {"name": "source", "writable": True, "signer": False},
                    {"name": "mint", "writable": False, "signer": False},
                    {"name": "destination", "writable": True, "signer": False},
                    {"name": "authority", "writable": False, "signer": True},
                ],
                "description": "Transfer tokens using associated token accounts.",
            },
        ],
    },
}


def _anchor_idl_fetch(program_id: str, *, cluster: str | None = None, rpc_url: str | None = None) -> dict[str, Any] | None:
    if shutil.which("anchor") is None:
        return None
    command = ["anchor", "idl", "fetch", program_id]
    if cluster:
        command.extend(["--provider.cluster", cluster])
    if rpc_url:
        command.extend(["-u", rpc_url])
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except Exception:  # noqa: BLE001
        return None
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def _anchorpy_idl_fetch(program_id: str, *, rpc_url: str | None = None) -> dict[str, Any] | None:
    try:
        import anchorpy  # type: ignore
        from solana.rpc.async_api import AsyncClient  # type: ignore
        from anchorpy import Provider, Program  # type: ignore
    except Exception:  # noqa: BLE001
        return None

    async def _run() -> dict[str, Any] | None:
        endpoint = rpc_url or "https://api.devnet.solana.com"
        client = AsyncClient(endpoint)
        try:
            provider = await Provider.create(client)
            program = await Program.at(program_id, provider)
            idl = program.idl
            if idl:
                # anchorpy returns an IDL object; convert to dict
                return idl if isinstance(idl, dict) else getattr(idl, "dict", None) or getattr(idl, "_idl", None)
        except Exception:
            return None
        finally:
            try:
                await client.close()
            except Exception:
                pass
        return None

    try:
        return asyncio.run(_run())
    except Exception:  # noqa: BLE001
        return None


def _render_idl_table(app: CLIApp, idl: dict[str, Any], title: str) -> None:
    table = Table(title=title, header_style="bold #38BDF8")
    table.add_column("Instruction", style="#14F195")
    table.add_column("Args", style="#94A3B8")
    table.add_column("Accounts", style="#94A3B8")
    for ix in idl.get("instructions", []):
        name = ix.get("name", "?")
        args = ", ".join(f"{a.get('name')}: {a.get('type')}" for a in ix.get("args", [])) or "—"
        accounts = ", ".join(
            f"{acc.get('name')}({'S' if acc.get('signer') else ''}{'W' if acc.get('writable') else ''})".strip("()")
            or acc.get("name")
            for acc in ix.get("accounts", [])
        ) or "—"
        table.add_row(str(name), args, accounts)
    app.console.print(table)


def register(app: CLIApp, router: CommandRouter) -> None:
    """Register the /program command and its subcommands."""

    def handle(app: CLIApp, args: list[str]) -> CommandResponse:
        cfg = getattr(app, "config_context", None)
        network = getattr(getattr(cfg, "config", None), "network", None)
        rpc_url = getattr(getattr(cfg, "config", None), "rpc_url", None)

        if not args or args[0] in {"help", "--help", "-h"}:
            usage = "\n".join(
                [
                    "Usage: /program <subcommand>",
                    "",
                    "Subcommands:",
                    "  inspect <program_id>               Show instructions, args, and required accounts.",
                    "  call <program_id> [--method ...]   Prepare a call; shows summary and confirmation (Anchor path requires anchorpy).",
                    "  wizard <program_id>                 Guided flow to select instruction and fill values.",
                    "  idl import <path>                   Import an IDL JSON for future inspection.",
                ]
            )
            return CommandResponse(messages=[("system", usage)])

        sub, *rest = args
        sub = sub.lower()

        if sub == "inspect":
            if not rest:
                return CommandResponse(messages=[("system", "Usage: /program inspect <program_id>")])
            program_id = rest[0]
            # Prefer anchorpy (if installed); then fall back to anchor CLI; then SPL catalog
            idl = _anchorpy_idl_fetch(program_id, rpc_url=rpc_url)
            if not idl:
                idl = _anchor_idl_fetch(program_id, cluster=network, rpc_url=rpc_url)
            title = f"Program {program_id}"
            if idl:
                _render_idl_table(app, idl, f"Anchor IDL — {title}")
                return CommandResponse(messages=[("system", f"Found Anchor IDL for {program_id}")])

            # SPL fallback
            spl = SPL_CATALOG.get(program_id)
            if spl:
                _render_idl_table(app, spl, f"SPL Catalog — {title}")
                return CommandResponse(messages=[("system", f"Using SPL catalog for {program_id}")])

            return CommandResponse(messages=[("system", f"No on-chain IDL found for {program_id}. Use `/program idl import <path>` or operate in raw mode.")])

        if sub == "idl":
            if not rest or rest[0] != "import" or len(rest) < 2:
                return CommandResponse(messages=[("system", "Usage: /program idl import <path>")])
            path = Path(rest[1]).expanduser()
            if not path.exists():
                return CommandResponse(messages=[("system", f"IDL file not found: {path}")])
            try:
                data = json.loads(path.read_text())
                instructions = data.get("instructions")
                if not isinstance(instructions, list):  # naive validation
                    raise ValueError("Invalid IDL: missing 'instructions'")
            except Exception as exc:  # noqa: BLE001
                return CommandResponse(messages=[("system", f"Failed to import IDL: {exc}")])

            store_dir = Path(".solcoder/idl")
            store_dir.mkdir(parents=True, exist_ok=True)
            program_name = data.get("name") or path.stem
            target = store_dir / f"{program_name}.json"
            target.write_text(json.dumps(data, indent=2))
            return CommandResponse(messages=[("system", f"Imported IDL to {target}")])

        if sub in {"call", "wizard"}:
            # Minimal skeleton: show what would be called and collect basics
            if not rest:
                return CommandResponse(messages=[("system", f"Usage: /program {sub} <program_id> [--method <name>] [--args-json <json>] [--accounts-json <json>]")])
            program_id = rest[0]
            # crude flag parsing
            method = None
            args_json = None
            accounts_json = None
            i = 1
            while i < len(rest):
                tok = rest[i]
                if tok == "--method" and i + 1 < len(rest):
                    method = rest[i + 1]
                    i += 2
                    continue
                if tok == "--args-json" and i + 1 < len(rest):
                    args_json = rest[i + 1]
                    i += 2
                    continue
                if tok == "--accounts-json" and i + 1 < len(rest):
                    accounts_json = rest[i + 1]
                    i += 2
                    continue
                i += 1

            try:
                args_obj = json.loads(args_json) if args_json else None
            except json.JSONDecodeError:
                return CommandResponse(messages=[("system", "--args-json must be valid JSON")])
            try:
                accounts_obj = json.loads(accounts_json) if accounts_json else None
            except json.JSONDecodeError:
                return CommandResponse(messages=[("system", "--accounts-json must be valid JSON")])

            # Special-case executable SPL flows
            if program_id in SPL_CATALOG:
                entry = SPL_CATALOG[program_id]
                pname = entry.get("name", "spl")
                if pname == "spl-memo":
                    memo_text = None
                    if isinstance(args_obj, dict):
                        memo_text = args_obj.get("memo")
                    if not memo_text:
                        return CommandResponse(messages=[("system", "Memo requires args-json like {\"memo\": \"hello\"}")])
                    # Confirm and send memo via solana CLI transfer 0 --with-memo
                    manager = app.wallet_manager
                    status = manager.status()
                    if not status.exists or not status.public_key:
                        return CommandResponse(messages=[("system", "No wallet available. Create or restore one first.")])
                    rpc = rpc_url or "https://api.devnet.solana.com"
                    summary = "\n".join([
                        f"Program: {program_id} (spl-memo)",
                        f"Memo: {memo_text}",
                        "Type 'send' to confirm or anything else to cancel.",
                    ])
                    app.console.print(summary)
                    passphrase = app._prompt_secret("Wallet passphrase", allow_master=False)
                    ack = app._prompt_text("Confirm").strip().lower()
                    if ack != "send":
                        return CommandResponse(messages=[("system", "Cancelled.")])
                    # Ensure Solana CLI is available, then export key and run memo
                    import tempfile
                    import json as _json
                    if shutil.which("solana") is None:
                        return CommandResponse(messages=[("system", "Solana CLI not found in PATH.")])
                    try:
                        secret = manager.export_wallet(passphrase)
                    except Exception as exc:  # noqa: BLE001
                        return CommandResponse(messages=[("system", f"Failed to export key: {exc}")])
                    key_path = None
                    try:
                        handle = tempfile.NamedTemporaryFile("w", delete=False, suffix=".json")
                        with handle:
                            handle.write(secret)
                            handle.flush()
                            key_path = Path(handle.name)
                        try:
                            os.chmod(key_path, 0o600)
                        except PermissionError:
                            # Windows may not support POSIX perms; ignore
                            pass
                        # self transfer of 0 with memo
                        cmd = [
                            "solana",
                            "transfer",
                            status.public_key,
                            "0",
                            "--from",
                            str(key_path),
                            "--fee-payer",
                            str(key_path),
                            "--url",
                            rpc,
                            "--with-memo",
                            memo_text,
                            "--output",
                            "json",
                        ]
                        try:
                            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
                        except FileNotFoundError:
                            return CommandResponse(messages=[("system", "Solana CLI not found in PATH.")])
                    finally:
                        try:
                            if key_path:
                                Path(key_path).unlink(missing_ok=True)
                        except Exception:
                            pass
                    if result.returncode != 0:
                        err = result.stderr.strip() or result.stdout.strip() or "Memo transaction failed"
                        return CommandResponse(messages=[("system", err)])
                    try:
                        payload = _json.loads(result.stdout)
                        signature = payload.get("signature")
                    except Exception:
                        signature = None
                    msg = f"Memo submitted. Signature: {signature or '(unknown)'}"
                    return CommandResponse(messages=[("system", msg)])

                if pname == "spl-token":
                    if shutil.which("spl-token") is None:
                        return CommandResponse(messages=[("system", "spl-token CLI not found in PATH.")])
                    if not isinstance(args_obj, dict):
                        return CommandResponse(messages=[("system", "Provide args-json like {\"amount\": 1.23}")])
                    amount = args_obj.get("amount")
                    if amount is None:
                        return CommandResponse(messages=[("system", "'amount' is required in args-json for token transfer")])
                    try:
                        amount_val = float(amount)
                    except Exception:
                        return CommandResponse(messages=[("system", "'amount' must be numeric")])
                    if not isinstance(accounts_obj, dict) or not accounts_obj.get("mint") or not accounts_obj.get("destination"):
                        return CommandResponse(messages=[("system", "accounts-json must include 'mint' and 'destination' addresses")])
                    mint = accounts_obj["mint"]
                    destination = accounts_obj["destination"]
                    # Confirm
                    summary = "\n".join([
                        f"Program: {program_id} (spl-token)",
                        f"Transfer {amount_val:.6f} of mint {mint} to {destination}",
                        "Type 'send' to confirm or anything else to cancel.",
                    ])
                    app.console.print(summary)
                    passphrase = app._prompt_secret("Wallet passphrase", allow_master=False)
                    ack = app._prompt_text("Confirm").strip().lower()
                    if ack != "send":
                        return CommandResponse(messages=[("system", "Cancelled.")])
                    # Export key and run spl-token transfer
                    import tempfile
                    try:
                        secret = app.wallet_manager.export_wallet(passphrase)
                    except Exception as exc:  # noqa: BLE001
                        return CommandResponse(messages=[("system", f"Failed to export key: {exc}")])
                    key_path = None
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
                        cmd = [
                            "spl-token",
                            "transfer",
                            mint,
                            f"{amount_val}",
                            destination,
                            "--owner",
                            str(key_path),
                            "--url",
                            rpc_url or "https://api.devnet.solana.com",
                            "--fund-recipient",
                        ]
                        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
                    finally:
                        try:
                            if key_path:
                                Path(key_path).unlink(missing_ok=True)
                        except Exception:
                            pass
                    if result.returncode != 0:
                        err = result.stderr.strip() or result.stdout.strip() or "spl-token transfer failed"
                        return CommandResponse(messages=[("system", err)])
                    # spl-token prints signature line
                    out = result.stdout.strip()
                    sig = None
                    for line in out.splitlines():
                        if "Signature" in line:
                            sig = line.split(":", 1)[-1].strip()
                            break
                    return CommandResponse(messages=[("system", f"Token transfer submitted. Signature: {sig or '(unknown)'}")])

            # Default: prepare only
            message = (
                "Program call preparation:\n"
                f"  Program: {program_id}\n"
                f"  Method: {method or '(unspecified)'}\n"
                "  Note: Generic on-chain execution requires anchorpy/solana-py integration. "
                "For now, this flow collects inputs and shows a confirmation summary."
            )
            return CommandResponse(messages=[("system", message)])

        return CommandResponse(messages=[("system", "Unknown subcommand. Type `/program help` for usage.")])

    router.register(
        SlashCommand(
            "program",
            handle,
            "Program interaction: inspect | call | wizard | idl import",
        )
    )


__all__ = ["register"]
