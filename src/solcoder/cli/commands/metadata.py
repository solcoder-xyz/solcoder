"""Unified metadata workflow (/metadata) for tokens and NFTs.

Implements a minimal local-first pipeline:
- upload: copies files into .solcoder/uploads and returns file:// URIs
- wizard: collects fields and optionally invokes set
- set: writes a local metadata JSON under .solcoder/metadata/<mint>.json and
       prepares future on-chain write (Metaplex integration TBD)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from solcoder.cli.types import CommandResponse, CommandRouter, SlashCommand
from solcoder.cli.storage import bundlr_upload, ipfs_upload_nft_storage, ipfs_upload_dir_web3storage
from solcoder.solana.constants import TOKEN_2022_PROGRAM_ID

if TYPE_CHECKING:  # pragma: no cover
    from solcoder.cli.app import CLIApp


@dataclass
class MetadataSetArgs:
    mint: str
    name: str
    symbol: str
    uri: str
    royalty_bps: int | None = None
    creators: str | None = None
    collection: str | None = None


def _workspace_root(app: "CLIApp") -> Path:
    try:
        active = getattr(app.session_context.metadata, "active_project", None)
        if active:
            p = Path(active).expanduser()
            return p
    except Exception:
        pass
    return Path.cwd()


def _uploads_dir(app: "CLIApp") -> Path:
    root = _workspace_root(app)
    uploads = root / ".solcoder" / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    return uploads


def _metadata_dir(app: "CLIApp") -> Path:
    root = _workspace_root(app)
    out = root / ".solcoder" / "metadata"
    out.mkdir(parents=True, exist_ok=True)
    return out


TOKEN_2022_PROGRAM_ARGS = ["--program-id", TOKEN_2022_PROGRAM_ID]


def _write_runner(app: "CLIApp") -> Path:
    """Ensure the Node-based Umi runner is scaffolded; return its directory."""
    runner_dir = _workspace_root(app) / ".solcoder" / "metadata_runner"
    (runner_dir / "src").mkdir(parents=True, exist_ok=True)
    pkg = {
        "name": "solcoder-metadata-runner",
        "private": True,
        "type": "module",
        "dependencies": {
            "@metaplex-foundation/umi": "^0.9.1",
            "@metaplex-foundation/umi-bundle-defaults": "^0.9.1",
            "@metaplex-foundation/mpl-token-metadata": "^3.0.0",
        },
        "devDependencies": {"ts-node": "^10.9.2", "typescript": "^5.4.0"},
        "scripts": {"set": "ts-node src/metadata_set.ts"},
    }
    (runner_dir / "package.json").write_text(json.dumps(pkg, indent=2))
    (runner_dir / "tsconfig.json").write_text(
        json.dumps(
            {
                "compilerOptions": {
                    "target": "ES2020",
                    "module": "ESNext",
                    "moduleResolution": "Node",
                    "esModuleInterop": True,
                    "strict": False,
                    "skipLibCheck": True,
                    "outDir": "dist",
                },
                "include": ["src/**/*"],
            },
            indent=2,
        )
    )
    ts_src = """
import fs from 'node:fs';
import process from 'node:process';
import { createUmi } from '@metaplex-foundation/umi-bundle-defaults';
import { publicKey, createSignerFromKeypair, signerIdentity } from '@metaplex-foundation/umi';
import { createV1, updateV1 } from '@metaplex-foundation/mpl-token-metadata';

function parseArgs() {
  const args = process.argv.slice(2);
  const out = {} as Record<string, string>;
  for (let i = 0; i < args.length; i++) {
    const k = args[i];
    if (k.startsWith('--') && i + 1 < args.length) {
      out[k.substring(2)] = args[i+1]; i++;
    }
  }
  return out;
}

async function main() {
  const opts = parseArgs();
  const file = opts['file'];
  const rpc = opts['rpc'] || 'https://api.devnet.solana.com';
  const keyPath = process.env.SOLANA_KEYPAIR;
  if (!file) throw new Error('Missing --file <metadata.json>');
  if (!keyPath) throw new Error('Set SOLANA_KEYPAIR to your keypair JSON path');
  const payload = JSON.parse(fs.readFileSync(file, 'utf8'));
  const secret = Uint8Array.from(JSON.parse(fs.readFileSync(keyPath, 'utf8')));
  const umi = createUmi(rpc);
  const kp = umi.eddsa.createKeypairFromSecretKey(secret);
  const signer = createSignerFromKeypair(umi, kp);
  umi.use(signerIdentity(signer));
  const mint = publicKey(payload.mint);
  // Build optional creators array from CSV "PK:BPS,..." (BPS -> ~share%)
  let creators = null as null | Array<{ address: ReturnType<typeof publicKey>; verified: boolean; share: number }>;
  if (payload.creators && typeof payload.creators === 'string') {
    try {
      const items = String(payload.creators)
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean)
        .map((entry) => {
          const [addr, bpsStr] = entry.split(':');
          const bps = Number(bpsStr || '0');
          const share = Math.max(0, Math.min(100, Math.round(bps / 100)));
          return { address: publicKey(addr.trim()), verified: false, share };
        });
      if (items.length > 0) creators = items;
    } catch {}
  }
  // Optional collection key
  let collection = null as null | { key: ReturnType<typeof publicKey>; verified: boolean };
  if (payload.collection && typeof payload.collection === 'string') {
    try {
      collection = { key: publicKey(String(payload.collection).trim()), verified: false };
    } catch {}
  }
  const data = {
    name: payload.name,
    symbol: payload.symbol,
    uri: payload.uri,
    sellerFeeBasisPoints: payload.royalty_bps ?? 0,
    creators,
    collection,
    uses: null
  };
  try {
    await createV1(umi, { mint, data }).sendAndConfirm(umi);
    console.log('Metadata created');
  } catch (e) {
    console.warn('createV1 failed, attempting updateV1:', (e as Error).message);
    await updateV1(umi, { mint, data }).sendAndConfirm(umi);
    console.log('Metadata updated');
  }
}

main().catch((e) => { console.error(e); process.exit(1); });
"""
    (runner_dir / "src" / "metadata_set.ts").write_text(ts_src)
    return runner_dir


def _is_token2022_mint(mint: str, rpc_url: str) -> bool:
    if shutil.which("spl-token") is None:
        return False
    cmd = [
        "spl-token",
        "display",
        mint,
        "--output",
        "json",
    ]
    cmd.extend(TOKEN_2022_PROGRAM_ARGS)
    cmd.extend(["--url", rpc_url])
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return False
    try:
        payload = json.loads(result.stdout or "{}")
    except Exception:
        return True
    program_id = (
        payload.get("programId")
        or payload.get("program_id")
        or payload.get("mint", {}).get("programId")
    )
    if program_id:
        return str(program_id) == TOKEN_2022_PROGRAM_ID
    return True


def _write_metadata_via_spl_token(
    app: "CLIApp",
    mint: str,
    *,
    name: str,
    symbol: str,
    uri: str,
    rpc_url: str,
    metadata_path: Path | None = None,
) -> tuple[bool, list[str], str]:
    if shutil.which("spl-token") is None:
        return False, ["(warning) spl-token CLI not found; install Solana CLI and rerun '/metadata set --run'."], uri

    manager = app.wallet_manager
    try:
        status = manager.status()
    except Exception as exc:  # noqa: BLE001
        return False, [f"(error) Unable to read wallet status: {exc}"], uri

    if not getattr(status, "exists", False) or not getattr(status, "public_key", None):
        return False, ["(error) No wallet available; cannot write metadata on-chain."], uri

    try:
        passphrase = app._prompt_secret("Wallet passphrase", allow_master=False)
        secret = manager.export_wallet(passphrase)
    except Exception as exc:  # noqa: BLE001
        return False, [f"(error) Wallet export failed: {exc}"], uri

    key_json: Path | None = None
    messages: list[str] = []
    resolved_uri = uri
    try:
        if uri.startswith("file://"):
            local_path = Path(uri[7:])
            try:
                remote_uri = bundlr_upload(
                    local_path,
                    rpc_url=rpc_url,
                    key_json=secret,
                    console=getattr(app, "console", None),
                    workspace_root=_workspace_root(app),
                    content_type="application/json",
                )
                resolved_uri = remote_uri
                messages.append(f"Metadata uploaded via Bundlr: {remote_uri}")
                if metadata_path and metadata_path.exists():
                    try:
                        data = json.loads(metadata_path.read_text())
                        data["uri"] = remote_uri
                        metadata_path.write_text(json.dumps(data, indent=2))
                    except Exception as exc:  # noqa: BLE001
                        messages.append(f"(warning) Unable to rewrite metadata file with remote URI: {exc}")
            except Exception as exc:  # noqa: BLE001
                messages.append(f"(warning) Bundlr upload failed: {exc}")

        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as handle:
            handle.write(secret)
            handle.flush()
            key_json = Path(handle.name)
        try:
            os.chmod(key_json, 0o600)
        except PermissionError:
            pass

        init_cmd = [
            "spl-token",
            "initialize-metadata",
            mint,
            name,
            symbol,
            resolved_uri,
            "--mint-authority",
            str(key_json),
            "--fee-payer",
            str(key_json),
        ]
        if status.public_key:
            init_cmd.extend(["--update-authority", str(status.public_key)])
        init_cmd.extend(TOKEN_2022_PROGRAM_ARGS)
        init_cmd.extend(["--url", rpc_url])
        init_res = subprocess.run(init_cmd, capture_output=True, text=True, check=False)
        if init_res.returncode == 0:
            messages.append("Token-2022 metadata initialized on-chain via spl-token.")
            return True, messages, resolved_uri

        err = init_res.stderr.strip() or init_res.stdout.strip()
        err_lower = err.lower()
        already_exists = any(token in err_lower for token in ["already", "0x0a", "custom program error: 0xa"])
        if not already_exists:
            messages.append(f"(warning) spl-token initialize-metadata failed: {err or 'unknown error'}")
            return False, messages, resolved_uri

        update_fields = [("name", name), ("symbol", symbol), ("uri", resolved_uri)]
        for field, value in update_fields:
            upd_cmd = [
                "spl-token",
                "update-metadata",
                mint,
                field,
                value,
                "--authority",
                str(key_json),
                "--fee-payer",
                str(key_json),
            ]
            upd_cmd.extend(TOKEN_2022_PROGRAM_ARGS)
            upd_cmd.extend(["--url", rpc_url])
            upd_res = subprocess.run(upd_cmd, capture_output=True, text=True, check=False)
            if upd_res.returncode != 0:
                upd_err = upd_res.stderr.strip() or upd_res.stdout.strip() or "unknown error"
                messages.append(f"(warning) Failed to update metadata field '{field}': {upd_err}")
                return False, messages, resolved_uri
        messages.append("Token-2022 metadata updated on-chain via spl-token.")
        return True, messages, resolved_uri
    finally:
        try:
            if key_json:
                key_json.unlink(missing_ok=True)
        except Exception:
            pass


def _run_metadata_via_node(app: "CLIApp", runner_dir: Path, metadata_path: Path, rpc_url: str) -> tuple[bool, list[str]]:
    """Install runner deps if needed and execute the Umi script to write metadata."""

    messages: list[str] = []
    manager = app.wallet_manager
    try:
        status = manager.status()
    except Exception as exc:  # noqa: BLE001
        return False, [f"(error) Unable to read wallet status: {exc}"]

    if not getattr(status, "exists", False):
        return False, ["(error) No wallet available; cannot write metadata on-chain."]

    try:
        passphrase = app._prompt_secret("Wallet passphrase", allow_master=False)
        secret = manager.export_wallet(passphrase)
    except Exception as exc:  # noqa: BLE001
        return False, [f"(error) Wallet export failed: {exc}"]

    key_json: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as handle:
            handle.write(secret)
            handle.flush()
            key_json = Path(handle.name)
        try:
            os.chmod(key_json, 0o600)
        except PermissionError:
            pass

        npm_path = shutil.which("npm")
        if not npm_path:
            return False, ["(warning) 'npm' not found; install Node.js and rerun '/metadata set --run'."]

        env = os.environ.copy()
        env["SOLANA_KEYPAIR"] = str(key_json)

        node_modules = runner_dir / "node_modules"
        if not node_modules.exists():
            install_cmd = [npm_path, "install"]
            try:
                install_res = subprocess.run(
                    install_cmd,
                    cwd=str(runner_dir),
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except FileNotFoundError:
                return False, ["(warning) 'npm' not found; install Node.js and rerun '/metadata set --run'."]

            if install_res.returncode != 0:
                err = install_res.stderr.strip() or install_res.stdout.strip() or "npm install failed"
                return False, [f"(warning) npm install failed: {err}"]

        npx_path = shutil.which("npx")
        if npx_path:
            runner_cmd = [
                npx_path,
                "ts-node",
                "src/metadata_set.ts",
                "--file",
                str(metadata_path),
                "--rpc",
                str(rpc_url),
            ]
        else:
            runner_cmd = [
                npm_path,
                "exec",
                "ts-node",
                "src/metadata_set.ts",
                "--file",
                str(metadata_path),
                "--rpc",
                str(rpc_url),
            ]

        try:
            runner_res = subprocess.run(
                runner_cmd,
                cwd=str(runner_dir),
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
        except FileNotFoundError:
            return False, ["(warning) 'npx' not found; install Node.js 18+ and rerun '/metadata set --run'."]

        if runner_res.returncode != 0:
            err = runner_res.stderr.strip() or runner_res.stdout.strip() or "metadata runner failed"
            return False, [f"(warning) Metadata runner failed: {err}"]

        output = runner_res.stdout.strip()
        if output:
            messages.append(f"On-chain metadata write completed via Umi runner. Output: {output}")
        else:
            messages.append("On-chain metadata write completed via Umi runner.")
        return True, messages
    finally:
        try:
            if key_json:
                key_json.unlink(missing_ok=True)
        except Exception:
            pass


def register(app: CLIApp, router: CommandRouter) -> None:
    def handle(app: CLIApp, args: list[str]) -> CommandResponse:
        if not args or args[0] in {"help", "-h", "--help"}:
            usage = (
                "Usage: /metadata <wizard|upload|set> [options]\n\n"
                "  wizard --mint <MINT> [--type token|nft]\n"
                "    Guides through name, symbol, uri, royalty, creators.\n\n"
                "  upload --file <path> | --dir <path>\n"
                "    Copies assets under .solcoder/uploads and returns file:// URIs.\n\n"
                "  set --mint <MINT> --name <N> --symbol <S> --uri <URI> [--royalty-bps <n>] [--creators <PK:BPS,...>] [--collection <PK>]\n"
                "    Writes local metadata file .solcoder/metadata/<mint>.json and prepares on-chain write.\n"
            )
            return CommandResponse(messages=[("system", usage)])

        sub = args[0].lower()

        if sub == "upload":
            if len(args) < 3 or args[1] not in {"--file", "--dir"}:
                return CommandResponse(messages=[("system", "Usage: /metadata upload --file <path>|--dir <path> [--storage auto|bundlr|ipfs]")])
            key = args[1]
            src = Path(args[2]).expanduser()
            storage = "auto"
            i = 3
            while i < len(args):
                tok = args[i]
                if tok == "--storage" and i + 1 < len(args):
                    storage = args[i + 1].strip().lower()
                    i += 2
                    continue
                i += 1
            if not src.exists():
                return CommandResponse(messages=[("system", f"Path not found: {src}")])
            # Choose provider
            cfg = getattr(app, "config_context", None)
            rpc = getattr(getattr(cfg, "config", None), "rpc_url", "https://api.devnet.solana.com")
            workspace_root = _workspace_root(app)
            ipfs_key = getattr(getattr(cfg, "config", None), "nft_storage_api_key", None) or getattr(getattr(cfg, "config", None), "web3_storage_api_key", None)
            use_ipfs = storage == "ipfs" or (storage == "auto" and ipfs_key and not shutil.which("npm"))
            if storage == "ipfs" and not ipfs_key:
                return CommandResponse(messages=[("system", "IPFS provider requested but no API key configured in .solcoder/config.toml (nft_storage_api_key or web3_storage_api_key).")])
            # File selection
            if key == "--dir" and not src.is_dir():
                return CommandResponse(messages=[("system", f"Not a directory: {src}")])
            if key == "--file" and not src.is_file():
                return CommandResponse(messages=[("system", f"Not a file: {src}")])

            # Uploader execution
            if use_ipfs:
                try:
                    with app.console.status("Uploading to IPFS…", spinner="dots"):
                        if src.is_file():
                            url = ipfs_upload_nft_storage(src, str(ipfs_key))
                        else:
                            url = ipfs_upload_dir_web3storage(src, str(ipfs_key), console=app.console)
                except Exception as exc:  # noqa: BLE001
                    return CommandResponse(messages=[("system", f"IPFS upload failed: {exc}")])
                return CommandResponse(messages=[("system", f"Uploaded: {url}")])
            else:
                # Prefer Bundlr/Irys via Node runner
                file_to_upload = src if src.is_file() else (src / "metadata.json")
                if not file_to_upload.exists():
                    # fallback to local copy if directory without metadata.json
                    target_base = _uploads_dir(app) / time.strftime("%Y%m%d_%H%M%S")
                    shutil.copytree(src, target_base)
                    uris = [f"file://{p}" for p in sorted(target_base.rglob("*")) if p.is_file()]
                    content = "\n".join(["(local fallback) Uploaded URIs:", *uris])
                    return CommandResponse(messages=[("system", content)])
                try:
                    status = app.wallet_manager.status()
                    if not status.exists:
                        return CommandResponse(messages=[("system", "No wallet available for Bundlr payment. Create or restore a wallet first.")])
                    passphrase = app._prompt_secret("Wallet passphrase", allow_master=False)
                    secret = app.wallet_manager.export_wallet(passphrase)
                except Exception as exc:  # noqa: BLE001
                    return CommandResponse(messages=[("system", f"Wallet export failed: {exc}")])
                try:
                    with app.console.status("Uploading to Bundlr…", spinner="dots"):
                        url = bundlr_upload(
                            file_to_upload,
                            rpc_url=str(rpc),
                            key_json=secret,
                            console=app.console,
                            workspace_root=workspace_root,
                        )
                except Exception as exc:  # noqa: BLE001
                    return CommandResponse(messages=[("system", f"Bundlr upload failed: {exc}")])
                return CommandResponse(messages=[("system", f"Uploaded: {url}")])

        if sub == "wizard":
            mint: str | None = None
            asset_type: str = "token"
            i = 1
            while i < len(args):
                tok = args[i]
                if tok == "--mint" and i + 1 < len(args):
                    mint = args[i + 1]
                    i += 2
                    continue
                if tok == "--type" and i + 1 < len(args):
                    asset_type = args[i + 1]
                    i += 2
                    continue
                i += 1
            if not mint:
                return CommandResponse(messages=[("system", "Usage: /metadata wizard --mint <MINT> [--type token|nft]")])
            # Ask minimal fields
            name = app._prompt_text("Name").strip() or "Untitled"
            symbol = app._prompt_text("Symbol").strip() or "TKN"
            # Storage preference and asset selection
            storage_pref = app._prompt_text("Storage (auto/bundlr/ipfs) [auto]").strip().lower() or "auto"
            asset_path = app._prompt_text("Asset (file or directory; leave blank to auto-generate)").strip()
            uri = ""
            if asset_path:
                # Reuse internal upload logic
                cmd = "/metadata upload --file " + asset_path if Path(asset_path).is_file() else "/metadata upload --dir " + asset_path
                if storage_pref in {"bundlr", "ipfs"}:
                    cmd += f" --storage {storage_pref}"
                routed = app.command_router.dispatch(app, cmd[1:])
                # Extract returned URL from message
                for _, msg in routed.messages:
                    for line in msg.splitlines():
                        if line.startswith("Uploaded:"):
                            uri = line.split(":", 1)[1].strip()
                            break
                if not uri:
                    app.console.print("[#F97316]Upload did not return a URI; falling back to manual URI entry.[/]")
            if not uri:
                uri = app._prompt_text("Metadata URI (leave blank to auto-generate)").strip()
            royalty_bps = app._prompt_text("Seller fee bps (optional)").strip()
            creators = app._prompt_text("Creators 'PK:BPS,...' (optional)").strip()
            collection = app._prompt_text("Collection address (optional)").strip()
            do_run_answer = app._prompt_text("Write metadata on-chain now? (Y/n)").strip().lower()
            do_run = do_run_answer not in {"n", "no"}
            # Dispatch to set
            import shlex as _shlex
            cmd_parts = [
                "/metadata",
                "set",
                "--mint",
                mint,
                "--name",
                name,
                "--symbol",
                symbol,
                "--uri",
                uri,
            ]
            if royalty_bps:
                cmd_parts += ["--royalty-bps", royalty_bps]
            if creators:
                cmd_parts += ["--creators", creators]
            if collection:
                cmd_parts += ["--collection", collection]
            if do_run:
                cmd_parts += ["--run"]
            dispatch = " ".join(_shlex.quote(p) for p in cmd_parts)
            routed = app.command_router.dispatch(app, dispatch[1:])
            return routed

        if sub == "set":
            # Parse flags
            mint: str | None = None
            name: str | None = None
            symbol: str | None = None
            uri: str | None = None
            royalty_bps: int | None = None
            creators: str | None = None
            collection: str | None = None
            run_now: bool = False
            i = 1
            while i < len(args):
                tok = args[i]
                if tok == "--mint" and i + 1 < len(args):
                    mint = args[i + 1]
                    i += 2
                    continue
                if tok == "--name" and i + 1 < len(args):
                    name = args[i + 1]
                    i += 2
                    continue
                if tok == "--symbol" and i + 1 < len(args):
                    symbol = args[i + 1]
                    i += 2
                    continue
                if tok == "--uri" and i + 1 < len(args):
                    uri = args[i + 1]
                    i += 2
                    continue
                if tok == "--royalty-bps" and i + 1 < len(args):
                    try:
                        royalty_bps = int(args[i + 1])
                    except Exception:
                        return CommandResponse(messages=[("system", "--royalty-bps must be an integer")])
                    i += 2
                    continue
                if tok == "--creators" and i + 1 < len(args):
                    creators = args[i + 1]
                    i += 2
                    continue
                if tok == "--collection" and i + 1 < len(args):
                    collection = args[i + 1]
                    i += 2
                    continue
                if tok == "--run":
                    run_now = True
                    i += 1
                    continue
                i += 1
            if not (mint and name and symbol and uri):
                return CommandResponse(messages=[("system", "Usage: /metadata set --mint <MINT> --name <N> --symbol <S> --uri <URI> [--royalty-bps <n>] [--creators <PK:BPS,...>] [--collection <PK>] [--run]")])

            args_obj = MetadataSetArgs(
                mint=mint,
                name=name,
                symbol=symbol,
                uri=uri,
                royalty_bps=royalty_bps,
                creators=creators,
                collection=collection,
            )
            # Present summary and persist local metadata JSON (future on-chain write)
            run_success = False
            lines = [
                "Metadata set (staged):",
                f"  Mint      : {args_obj.mint}",
                f"  Name      : {args_obj.name}",
                f"  Symbol    : {args_obj.symbol}",
                f"  URI       : {args_obj.uri}",
            ]
            if args_obj.royalty_bps is not None:
                lines.append(f"  Royalty bps: {args_obj.royalty_bps}")
            if args_obj.creators:
                # Validate shares sum to 100 if provided as share (%)
                try:
                    parts = [p.strip() for p in str(args_obj.creators).split(',') if p.strip()]
                    shares = []
                    for part in parts:
                        segs = part.split(':')
                        if len(segs) >= 2:
                            shares.append(int(segs[1]))
                    if shares and sum(shares) != 100:
                        lines.append(f"  (warning) creators shares sum to {sum(shares)}; runner will normalize to 100%")
                except Exception:
                    pass
                lines.append(f"  Creators  : {args_obj.creators}")
            if args_obj.collection:
                lines.append(f"  Collection: {args_obj.collection}")
            # Persist to .solcoder/metadata
            out_dir = _metadata_dir(app)
            out_path = out_dir / f"{args_obj.mint}.json"
            try:
                payload = {
                    "mint": args_obj.mint,
                    "name": args_obj.name,
                    "symbol": args_obj.symbol,
                    "uri": args_obj.uri,
                    "royalty_bps": args_obj.royalty_bps,
                    "creators": args_obj.creators,
                    "collection": args_obj.collection,
                }
                out_path.write_text(json.dumps(payload, indent=2))
                lines.append(f"Saved: {out_path}")
                rpc = getattr(getattr(app.config_context, "config", None), "rpc_url", "https://api.devnet.solana.com")
                rpc_str = str(rpc)
                run_success = False
                runner_dir: Path | None = None
                run_messages: list[str] = []

                if run_now:
                    if _is_token2022_mint(args_obj.mint, rpc_str):
                        run_success, run_messages, resolved_uri = _write_metadata_via_spl_token(
                            app,
                            args_obj.mint,
                            name=args_obj.name,
                            symbol=args_obj.symbol,
                            uri=args_obj.uri,
                            rpc_url=rpc_str,
                            metadata_path=out_path,
                        )
                        lines.extend(run_messages)
                        if run_success and resolved_uri != args_obj.uri:
                            args_obj.uri = resolved_uri
                    if not run_success:
                        try:
                            runner_dir = _write_runner(app)
                            lines.append("Runner prepared: Node Umi script scaffolded.")
                            lines.append(f"Runner dir: {runner_dir}")
                        except Exception as runner_exc:  # noqa: BLE001
                            lines.append(f"(warning) Failed to scaffold metadata runner: {runner_exc}")
                            runner_dir = None
                        if runner_dir is not None:
                            success, node_messages = _run_metadata_via_node(app, runner_dir, out_path, rpc_str)
                            lines.extend(node_messages)
                            run_success = success
                else:
                    try:
                        runner_dir = _write_runner(app)
                        lines.append("Runner prepared: Node Umi script scaffolded.")
                        lines.append(f"Runner dir: {runner_dir}")
                    except Exception as runner_exc:  # noqa: BLE001
                        lines.append(f"(warning) Failed to scaffold metadata runner: {runner_exc}")
                        runner_dir = None

                if not run_success:
                    if runner_dir is not None:
                        lines.append("To write on-chain now:")
                        lines.append("  cd " + str(runner_dir))
                        lines.append("  npm install")
                        lines.append(
                            "  SOLANA_KEYPAIR=/path/to/your/key.json npm run set -- --file "
                            f"../metadata/{args_obj.mint}.json --rpc {rpc_str}"
                        )
                    elif run_now:
                        lines.append("Runner setup failed; rerun '/metadata set --run' after resolving the issue.")
            except Exception as exc:  # noqa: BLE001
                lines.append(f"(warning) Failed to persist local metadata: {exc}")
            else:
                if run_success:
                    lines[0] = "Metadata set on-chain:"
                    for idx, line in enumerate(lines):
                        if line.startswith("  URI"):
                            lines[idx] = f"  URI       : {args_obj.uri}"
                            break
            return CommandResponse(messages=[("system", "\n".join(lines))])

        return CommandResponse(messages=[("system", "Unknown subcommand. Try '/metadata help'.")])

        if sub == "install":
            root = _workspace_root(app)
            lines: list[str] = []
            # Scaffold runners
            try:
                set_runner = _write_runner(app)
                lines.append(f"Prepared metadata runner: {set_runner}")
            except Exception as exc:  # noqa: BLE001
                lines.append(f"(warning) Failed to scaffold metadata runner: {exc}")
                set_runner = None
            try:
                from solcoder.cli.storage import ensure_bundlr_runner, ensure_ipfs_runner
                b_runner = ensure_bundlr_runner(root)
                i_runner = ensure_ipfs_runner(root)
                lines.append(f"Prepared upload runners: {b_runner}, {i_runner}")
            except Exception as exc:  # noqa: BLE001
                lines.append(f"(warning) Failed to scaffold upload runners: {exc}")
                b_runner = None
                i_runner = None
            # Install deps where applicable
            import shutil as _shutil
            import subprocess as _subprocess
            for runner in [p for p in [set_runner, b_runner, i_runner] if p is not None]:
                pkg = runner / "package.json"
                if not pkg.exists():
                    continue
                if (runner / "node_modules").exists():
                    lines.append(f"Deps already installed: {runner}")
                    continue
                if not _shutil.which("npm"):
                    lines.append("(warning) npm not found; install Node.js to proceed with runner setup.")
                    continue
                try:
                    with app.console.status(f"Installing dependencies in {runner}…", spinner="dots"):
                        res = _subprocess.run(["npm", "install"], cwd=str(runner), capture_output=True, text=True, check=False)
                    if res.returncode == 0:
                        lines.append(f"Installed deps: {runner}")
                    else:
                        err = res.stderr.strip() or res.stdout.strip() or "npm install failed"
                        lines.append(f"(warning) Failed to install deps in {runner}: {err}")
                except FileNotFoundError:
                    lines.append("(warning) npm not found; skipping install.")
            return CommandResponse(messages=[("system", "\n".join(lines))])

    router.register(
        SlashCommand(
            "metadata",
            handle,
            "Unified metadata flow: wizard | upload | set",
        )
    )


__all__ = ["register"]
