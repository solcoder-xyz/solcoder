"""Unified metadata workflow (/metadata) for tokens and NFTs.

Implements a minimal local-first pipeline:
- upload: copies files into .solcoder/uploads and returns file:// URIs
- wizard: collects fields and optionally invokes set
- set: writes a local metadata JSON under .solcoder/metadata/<mint>.json and
       prepares future on-chain write (Metaplex integration TBD)
"""

from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from solcoder.cli.types import CommandResponse, CommandRouter, SlashCommand

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
                return CommandResponse(messages=[("system", "Usage: /metadata upload --file <path>|--dir <path>")])
            key = args[1]
            src = Path(args[2]).expanduser()
            if not src.exists():
                return CommandResponse(messages=[("system", f"Path not found: {src}")])
            target_base = _uploads_dir(app) / time.strftime("%Y%m%d_%H%M%S")
            if key == "--file":
                target_base.mkdir(parents=True, exist_ok=True)
                target = target_base / src.name
                shutil.copy2(src, target)
                uri = f"file://{target}"
                return CommandResponse(messages=[("system", f"Uploaded: {uri}")])
            else:
                if not src.is_dir():
                    return CommandResponse(messages=[("system", f"Not a directory: {src}")])
                shutil.copytree(src, target_base)
                # List URIs
                uris = [f"file://{p}" for p in sorted(target_base.rglob("*")) if p.is_file()]
                content = "\n".join(["Uploaded URIs:", *uris])
                return CommandResponse(messages=[("system", content)])

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
            uri = app._prompt_text("Metadata URI").strip() or ""
            royalty_bps = app._prompt_text("Seller fee bps (optional)").strip()
            creators = app._prompt_text("Creators 'PK:BPS,...' (optional)").strip()
            collection = app._prompt_text("Collection address (optional)").strip()
            do_run = app._prompt_text("Install deps and write on-chain now? (y/N)").strip().lower() in {"y","yes"}
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
                # Prepare a Node runner to write metadata on-chain via Umi (optional)
                runner_dir = _write_runner(app)
                lines.append("Runner prepared: Node Umi script scaffolded.")
                lines.append(f"Runner dir: {runner_dir}")
                rpc = getattr(getattr(app.config_context, "config", None), "rpc_url", "https://api.devnet.solana.com")
                if run_now:
                    # Attempt to run the script immediately if deps are present
                    import os
                    import subprocess
                    import tempfile
                    manager = app.wallet_manager
                    status = manager.status()
                    if not status.exists:
                        lines.append("(error) No wallet available; cannot run on-chain write.")
                    else:
                        key_json: Path | None = None
                        try:
                            # Ensure dependencies
                            if not (runner_dir / "node_modules").exists():
                                # Try to install automatically
                                try:
                                    result = subprocess.run(["npm", "install"], cwd=str(runner_dir), capture_output=True, text=True, check=False)
                                    if result.returncode != 0:
                                        lines.append("(warning) npm install failed; run manually and retry --run.")
                                except FileNotFoundError:
                                    lines.append("(warning) 'npm' not found; install Node.js and run 'npm install' in the runner dir.")
                            if (runner_dir / "node_modules").exists():
                                # Export wallet key (prompt for passphrase)
                                passphrase = app._prompt_secret("Wallet passphrase", allow_master=False)
                                secret = manager.export_wallet(passphrase)
                                with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as f:
                                    f.write(secret)
                                    f.flush()
                                    key_json = Path(f.name)
                                try:
                                    os.chmod(key_json, 0o600)
                                except Exception:
                                    pass
                                env = os.environ.copy()
                                env["SOLANA_KEYPAIR"] = str(key_json)
                                cmd = [
                                    "npx",
                                    "ts-node",
                                    "src/metadata_set.ts",
                                    "--file",
                                    str(out_path),
                                    "--rpc",
                                    str(rpc),
                                ]
                                try:
                                    result = subprocess.run(cmd, cwd=str(runner_dir), capture_output=True, text=True, check=False)
                                    if result.returncode == 0:
                                        lines.append("On-chain write completed via Umi runner.")
                                    else:
                                        err = result.stderr.strip() or result.stdout.strip() or "runner failed"
                                        lines.append(f"(warning) Runner error: {err}")
                                except FileNotFoundError:
                                    lines.append("(warning) 'npx' not found; install Node.js and run manually.")
                        finally:
                            try:
                                if key_json:
                                    key_json.unlink(missing_ok=True)
                            except Exception:
                                pass
                else:
                    lines.append("To write on-chain now:")
                    lines.append("  cd " + str(runner_dir))
                    lines.append("  npm install")
                    lines.append(f"  SOLANA_KEYPAIR=/path/to/your/key.json npm run set -- --file ../metadata/{args_obj.mint}.json --rpc {rpc}")
            except Exception as exc:  # noqa: BLE001
                lines.append(f"(warning) Failed to persist local metadata: {exc}")
            lines.append("Note: On-chain write via Metaplex is planned in 2.3b.")
            return CommandResponse(messages=[("system", "\n".join(lines))])

        return CommandResponse(messages=[("system", "Unknown subcommand. Try '/metadata help'.")])

    router.register(
        SlashCommand(
            "metadata",
            handle,
            "Unified metadata flow: wizard | upload | set",
        )
    )


__all__ = ["register"]
