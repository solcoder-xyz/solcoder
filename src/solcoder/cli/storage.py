"""Storage helpers for metadata uploads (Bundlr/Irys and IPFS)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

import httpx
import mimetypes


def ipfs_upload_nft_storage(file_path: Path, api_key: str) -> str:
    """Upload a single file to nft.storage and return an https:// URL.

    For directories, callers should pick a single JSON (e.g., metadata.json) to upload here.
    """
    url = "https://api.nft.storage/upload"
    headers = {"Authorization": f"Bearer {api_key}"}
    with file_path.open("rb") as f:
        resp = httpx.post(url, headers=headers, files={"file": (file_path.name, f)}, timeout=30.0)
    resp.raise_for_status()
    data = resp.json()
    cid = data.get("value", {}).get("cid")
    if not cid:
        raise RuntimeError(f"nft.storage response missing cid: {data}")
    return f"https://ipfs.io/ipfs/{cid}"


def ensure_bundlr_runner(root: Path) -> Path:
    runner = root / ".solcoder" / "uploader_runner"
    (runner / "src").mkdir(parents=True, exist_ok=True)
    pkg = {
        "name": "solcoder-uploader-runner",
        "private": True,
        "type": "module",
        "dependencies": {"@irys/sdk": "^0.1.15", "bignumber.js": "^9.1.2"},
        "devDependencies": {"ts-node": "^10.9.2", "typescript": "^5.4.0"},
        "scripts": {"upload": "ts-node src/bundlr_upload.ts"},
    }
    (runner / "package.json").write_text(json.dumps(pkg, indent=2))
    (runner / "tsconfig.json").write_text(
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
import path from 'node:path';
import Irys from '@irys/sdk';
import BigNumber from 'bignumber.js';

function parseArgs() {
  const args = process.argv.slice(2);
  const out = {} as Record<string, string>;
  for (let i = 0; i < args.length; i++) {
    const k = args[i];
    if (k.startsWith('--') && i + 1 < args.length) { out[k.substring(2)] = args[i+1]; i++; }
  }
  return out;
}

async function main() {
  const opts = parseArgs();
  const file = opts['file'];
  const rpc = opts['rpc'] || 'https://api.devnet.solana.com';
  const keyPath = process.env.SOLANA_KEYPAIR;
  const contentType = opts['contentType'] || 'application/octet-stream';
  if (!file) throw new Error('Missing --file <asset>');
  if (!keyPath) throw new Error('Set SOLANA_KEYPAIR to your keypair JSON path');
  const secret = Uint8Array.from(JSON.parse(fs.readFileSync(keyPath, 'utf8')));
  // Irys supports 'solana' network with devnet/testnet/mainnet
  const irys = await Irys.create({ url: 'https://devnet.irys.xyz', token: 'solana', key: secret, config: { providerUrl: rpc } });
  const data = fs.readFileSync(path.resolve(file));
  const price = await irys.getPrice(data.length);
  const balance = await irys.getLoadedBalance();
  const required = price.multipliedBy(1.1).integerValue(BigNumber.ROUND_CEIL); // 10% headroom
  if (balance.isLessThan(required)) {
    const toFund = required.minus(balance);
    console.log(`Funding Bundlr account with ${toFund.toString()} lamports (includes 10% buffer).`);
    await irys.fund(toFund);
  }
  const tags = [{ name: 'Content-Type', value: contentType }];
  const receipt = await irys.upload(data, { tags });
  console.log(receipt.id ? `https://arweave.net/${receipt.id}` : receipt);
}

main().catch((e) => { console.error(e); process.exit(1); });
"""
    (runner / "src" / "bundlr_upload.ts").write_text(ts_src)
    return runner


def bundlr_upload(
    file_path: Path,
    *,
    rpc_url: str,
    key_json: str,
    console=None,
    workspace_root: Path | None = None,
    content_type: str | None = None,
) -> str:
    file_path = Path(file_path).expanduser()
    if not file_path.exists():
        raise RuntimeError(f"File not found: {file_path}")
    root = Path(workspace_root).expanduser() if workspace_root else Path.cwd()
    runner = ensure_bundlr_runner(root)
    if shutil.which("npm") is None:
        raise RuntimeError("npm not found in PATH; install Node.js to use Bundlr uploads.")
    # Ensure deps
    if not (runner / "node_modules").exists():
        if console:
            console.print("[#94A3B8]Installing Bundlr (Irys) uploader deps…[/]")
        install = subprocess.run(
            ["npm", "install"],
            cwd=str(runner),
            capture_output=True,
            text=True,
            check=False,
        )
        if install.returncode != 0:
            err = install.stderr.strip() or install.stdout.strip() or "npm install failed"
            raise RuntimeError(err)
    if shutil.which("npx") is None:
        raise RuntimeError("npx not found in PATH; install Node.js (which provides npx) to use Bundlr uploads.")
    # Write key temp file
    tmp_key: Optional[Path] = None
    mime = content_type or mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    try:
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as f:
            f.write(key_json)
            f.flush()
            tmp_key = Path(f.name)
        try:
            os.chmod(tmp_key, 0o600)
        except Exception:
            pass
        env = os.environ.copy()
        env["SOLANA_KEYPAIR"] = str(tmp_key)
        cmd = [
            "npx",
            "ts-node",
            "src/bundlr_upload.ts",
            "--file",
            str(file_path),
            "--rpc",
            rpc_url,
            "--contentType",
            mime,
        ]
        result = subprocess.run(cmd, cwd=str(runner), env=env, capture_output=True, text=True, check=False, timeout=120)
        if result.returncode != 0:
            err = result.stderr.strip() or result.stdout.strip() or "bundlr upload failed"
            raise RuntimeError(err)
        url = (result.stdout or "").strip().splitlines()[-1].strip()
        if not url:
            raise RuntimeError("bundlr returned empty URL")
        return url
    finally:
        try:
            if tmp_key:
                tmp_key.unlink(missing_ok=True)
        except Exception:
            pass


def ensure_ipfs_runner(root: Path) -> Path:
    runner = root / ".solcoder" / "uploader_runner"
    (runner / "src").mkdir(parents=True, exist_ok=True)
    # Reuse the same runner dir; add web3.storage dependency if missing
    pkg_path = runner / "package.json"
    if pkg_path.exists():
        pkg = json.loads(pkg_path.read_text())
    else:
        pkg = {
            "name": "solcoder-uploader-runner",
            "private": True,
            "type": "module",
            "dependencies": {},
            "devDependencies": {"ts-node": "^10.9.2", "typescript": "^5.4.0"},
            "scripts": {"upload": "ts-node src/bundlr_upload.ts"},
        }
    deps = pkg.setdefault("dependencies", {})
    deps.setdefault("web3.storage", "^4.5.4")
    pkg["scripts"]["ipfs"] = "ts-node src/ipfs_upload.ts"
    pkg_path.write_text(json.dumps(pkg, indent=2))
    (runner / "tsconfig.json").write_text(
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
import path from 'node:path';
import process from 'node:process';
import { Web3Storage, File } from 'web3.storage';

function parseArgs() {
  const args = process.argv.slice(2);
  const out = {} as Record<string, string>;
  for (let i = 0; i < args.length; i++) {
    const k = args[i];
    if (k.startsWith('--') && i + 1 < args.length) { out[k.substring(2)] = args[i+1]; i++; }
  }
  return out;
}

async function main() {
  const opts = parseArgs();
  const dir = opts['dir'];
  const token = process.env.WEB3_STORAGE_TOKEN || opts['token'];
  if (!dir) throw new Error('Missing --dir <path>');
  if (!token) throw new Error('Missing web3.storage token');
  const client = new Web3Storage({ token });
  // Pack directory into File[]
  const root = path.resolve(dir);
  const walk = (p: string): File[] => {
    const entries = fs.readdirSync(p, { withFileTypes: true });
    const out: File[] = [];
    for (const e of entries) {
      const full = path.join(p, e.name);
      if (e.isDirectory()) out.push(...walk(full));
      else out.push(new File([fs.readFileSync(full)], path.relative(root, full)));
    }
    return out;
  };
  const files = walk(root);
  const cid = await client.put(files, { wrapWithDirectory: true });
  console.log(`https://ipfs.io/ipfs/${cid}`);
}

main().catch((e) => { console.error(e); process.exit(1); });
"""
    (runner / "src" / "ipfs_upload.ts").write_text(ts_src)
    return runner


def ipfs_upload_dir_web3storage(dir_path: Path, api_key: str, console=None) -> str:
    root = Path.cwd()
    runner = ensure_ipfs_runner(root)
    if not (runner / "node_modules").exists():
        if console:
            console.print("[#94A3B8]Installing IPFS (web3.storage) uploader deps…[/]")
        subprocess.run(["npm", "install"], cwd=str(runner), check=False)
    env = os.environ.copy()
    env["WEB3_STORAGE_TOKEN"] = api_key
    cmd = [
        "npx",
        "ts-node",
        "src/ipfs_upload.ts",
        "--dir",
        str(dir_path),
    ]
    result = subprocess.run(cmd, cwd=str(runner), env=env, capture_output=True, text=True, check=False, timeout=180)
    if result.returncode != 0:
        err = result.stderr.strip() or result.stdout.strip() or "ipfs upload failed"
        raise RuntimeError(err)
    url = (result.stdout or "").strip().splitlines()[-1].strip()
    if not url:
        raise RuntimeError("ipfs upload returned empty URL")
    return url
