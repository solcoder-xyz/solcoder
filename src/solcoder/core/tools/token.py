"""Tools for token operations exposed to the agent."""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Any

from solcoder.core.tools.base import Tool, Toolkit, ToolResult, ToolInvocationError


def _create_quick_token_handler(payload: dict[str, Any]) -> ToolResult:
    # Validate inputs
    decimals = payload.get("decimals")
    supply = payload.get("supply")
    cluster = payload.get("cluster")
    if decimals is None or supply is None:
        raise ToolInvocationError("'decimals' and 'supply' are required.")
    try:
        dval = int(decimals)
    except Exception:
        raise ToolInvocationError("'decimals' must be an integer between 0 and 9.")
    if dval < 0 or dval > 9:
        raise ToolInvocationError("'decimals' must be between 0 and 9.")

    # Prepare CLI dispatch. The CLI will prompt the user for passphrase and a final confirmation.
    parts = [
        "/new",
        "token",
        "--quick",
        "--decimals",
        str(dval),
        "--supply",
        str(supply),
    ]
    if isinstance(cluster, str) and cluster.strip():
        parts.extend(["--cluster", cluster.strip()])
    # Optional metadata fields to streamline post-mint metadata
    meta_name = payload.get("name")
    meta_symbol = payload.get("symbol")
    meta_uri = payload.get("uri")
    meta_royalty_bps = payload.get("royalty_bps")
    meta_creators = payload.get("creators")
    meta_collection = payload.get("collection")
    meta_run = payload.get("run")
    # Provide sensible defaults for agent flows when not provided
    def _derive_symbol(name: str) -> str:
        alnum = "".join(ch for ch in name if ch.isalnum())
        up = alnum.upper() or "TKN"
        return up[:6]

    if not (isinstance(meta_name, str) and meta_name.strip()):
        # Try program_name hint; otherwise default
        prog_name = payload.get("program_name") or "SolCoder Token"
        meta_name = str(prog_name).strip() or "SolCoder Token"
    if not (isinstance(meta_symbol, str) and meta_symbol.strip()):
        meta_symbol = _derive_symbol(str(meta_name))

    parts += ["--meta-name", str(meta_name).strip()]
    parts += ["--meta-symbol", str(meta_symbol).strip()]
    # Derive metadata URI from a local asset if provided and uri is missing
    if not (isinstance(meta_uri, str) and meta_uri.strip()):
        asset_file = payload.get("asset_file")
        asset_dir = payload.get("asset_dir")
        if bool(asset_file) ^ bool(asset_dir):
            try:
                uploads_root = Path.cwd() / ".solcoder" / "uploads" / time.strftime("%Y%m%d_%H%M%S")
                uploads_root.mkdir(parents=True, exist_ok=True)
                if asset_file:
                    src = Path(str(asset_file)).expanduser()
                    if src.exists() and src.is_file():
                        target = uploads_root / src.name
                        shutil.copy2(src, target)
                        meta_uri = f"file://{target}"
                else:
                    srcd = Path(str(asset_dir)).expanduser()
                    if srcd.exists() and srcd.is_dir():
                        shutil.copytree(srcd, uploads_root)
                        candidate = uploads_root / "metadata.json"
                        if candidate.exists():
                            meta_uri = f"file://{candidate}"
                        else:
                            json_files = sorted(p for p in uploads_root.rglob("*.json") if p.is_file())
                            if json_files:
                                meta_uri = f"file://{json_files[0]}"
            except Exception:
                meta_uri = None

    if isinstance(meta_uri, str) and meta_uri.strip():
        parts += ["--meta-uri", meta_uri.strip()]
    if meta_royalty_bps is not None:
        parts += ["--meta-royalty-bps", str(meta_royalty_bps)]
    if isinstance(meta_creators, str) and meta_creators.strip():
        parts += ["--meta-creators", meta_creators.strip()]
    if isinstance(meta_collection, str) and meta_collection.strip():
        parts += ["--meta-collection", meta_collection.strip()]
    if isinstance(meta_run, bool) and meta_run:
        parts += ["--meta-run"]
    import shlex as _shlex
    dispatch = " ".join(_shlex.quote(p) for p in parts)

    summary = (
        "Prepare quick SPL token mint (Token-2022):\n"
        f"  Decimals: {dval}\n"
        f"  Initial supply: {supply}\n"
        "The CLI will show a summary and request your passphrase and a final 'mint' confirmation."
    )
    applied_defaults: dict[str, str] = {}
    if not payload.get("name"):
        applied_defaults["name"] = str(meta_name)
    if not payload.get("symbol"):
        applied_defaults["symbol"] = str(meta_symbol)
    content_lines = [summary]
    if applied_defaults:
        pretty = ", ".join(f"{k}={v}" for k, v in applied_defaults.items())
        content_lines.append(f"Applied metadata defaults: {pretty}")
        if not meta_uri:
            content_lines.append("Note: No metadata URI provided; wizard will prompt after mint.")
    return ToolResult(
        content="\n".join(content_lines),
        summary="Quick token mint prepared; awaiting confirmation.",
        data={"dispatch_command": dispatch},
    )


def token_toolkit() -> Toolkit:
    create_quick_token = Tool(
        name="create_quick_token",
        description=(
            "Prepare a quick SPL Token-2022 mint without the full wizard. "
            "Prompts the user only for confirmation and passphrase. "
            "If name/symbol are not provided, sensible defaults are applied (e.g., 'SolCoder Token'/'SCT'). "
            "You may also pass 'asset_file' or 'asset_dir' to derive a file:// metadata URI automatically."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "decimals": {"type": "integer", "minimum": 0, "maximum": 9},
                "supply": {"type": ["number", "string"], "description": "Initial supply as UI amount."},
                "cluster": {"type": "string", "description": "Optional cluster hint (devnet/testnet/mainnet-beta)."},
                "name": {"type": "string"},
                "symbol": {"type": "string"},
                "uri": {"type": "string"},
                "royalty_bps": {"type": ["integer", "null"]},
                "creators": {"type": ["string", "null"]},
                "collection": {"type": ["string", "null"]},
                "run": {"type": "boolean"},
                "asset_file": {"type": "string", "description": "Path to metadata JSON file to upload and use as URI."},
                "asset_dir": {"type": "string", "description": "Directory containing metadata.json to use as URI."},
            },
            "required": ["decimals", "supply"],
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        handler=_create_quick_token_handler,
    )
    return Toolkit(
        name="solcoder.token",
        version="1.0.0",
        description="Token helpers for agent-initiated quick mints.",
        tools=[create_quick_token],
    )


__all__ = ["token_toolkit"]
