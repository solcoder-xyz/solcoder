"""Anchor build/deploy helpers for SolCoder."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import tomli_w

try:  # Python 3.11+
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - fallback for older interpreters
    import tomli as tomllib  # type: ignore[no-redef]

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

# Base58 alphabet constant mirrors solana.wallet to avoid import cycles.
BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


class DeployError(RuntimeError):
    """Raised when build/deploy orchestration fails."""


@dataclass(slots=True)
class CommandResult:
    """Represents the outcome of an anchor CLI invocation."""

    command: list[str]
    cwd: Path
    duration_secs: float
    returncode: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        return self.returncode == 0


@dataclass(slots=True)
class AnchorDeployResult(CommandResult):
    """`anchor deploy` output bundled with parsed program id (if available)."""

    program_id: str | None = None


@dataclass(slots=True)
class DeployVerification:
    """Structured verification result prior to build/deploy."""

    errors: list[str]
    warnings: list[str]
    infos: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


def discover_anchor_root(start: Path) -> Path | None:
    """Return the nearest ancestor (inclusive) that contains Anchor.toml."""
    try:
        cur = start.resolve()
    except Exception:
        cur = start.expanduser()
    for candidate in [cur, *cur.parents]:
        if (candidate / "Anchor.toml").exists():
            return candidate
    return None


def load_anchor_config(anchor_path: Path) -> dict[str, Any]:
    """Load Anchor.toml and return as dictionary."""
    try:
        return tomllib.loads(anchor_path.read_text())
    except FileNotFoundError as exc:
        raise DeployError(f"Anchor config not found at {anchor_path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise DeployError(f"Failed to parse {anchor_path}: {exc}") from exc


def save_anchor_config(anchor_path: Path, data: dict[str, Any]) -> None:
    """Persist Anchor.toml with updated values."""
    content = tomli_w.dumps(data)
    anchor_path.write_text(content)


def infer_program_name(anchor_config: dict[str, Any], *, cluster: str | None = None) -> str | None:
    """Best-effort program name inference from Anchor config."""
    programs_section = anchor_config.get("programs")
    if not isinstance(programs_section, dict):
        return None
    cluster_key = cluster or _provider_cluster(anchor_config)
    candidates: dict[str, Any] | None = None
    if cluster_key and isinstance(programs_section.get(cluster_key), dict):
        candidates = programs_section[cluster_key]
    if not candidates:
        # Fall back to the first cluster entry
        for value in programs_section.values():
            if isinstance(value, dict) and value:
                candidates = value
                break
    if not candidates:
        return None
    # Return the first key deterministically sorted for stability
    return sorted(candidates.keys())[0] if candidates else None


def resolve_cluster(anchor_config: dict[str, Any], preferred: str | None = None) -> str:
    """Resolve the target cluster from configuration or sensible defaults."""
    if preferred and preferred.strip():
        return preferred.strip()
    detected = _provider_cluster(anchor_config)
    if detected:
        return detected
    programs_section = anchor_config.get("programs")
    if isinstance(programs_section, dict):
        for key, value in programs_section.items():
            if isinstance(value, dict):
                return str(key)
    return "devnet"


def _provider_cluster(anchor_config: dict[str, Any]) -> str | None:
    provider = anchor_config.get("provider")
    if isinstance(provider, dict):
        cluster = provider.get("cluster")
        if isinstance(cluster, str) and cluster.strip():
            return cluster.strip()
    return None


def ensure_program_keypair(project_root: Path, program_name: str) -> tuple[Path, str]:
    """Ensure a program keypair exists and return (path, public_key)."""
    key_dir = project_root / ".solcoder" / "keys" / "programs"
    key_dir.mkdir(parents=True, exist_ok=True)
    key_path = key_dir / f"{program_name}.json"

    if key_path.exists():
        try:
            raw = json.loads(key_path.read_text())
            if isinstance(raw, list):
                data = bytes(int(b) & 0xFF for b in raw)
            elif isinstance(raw, str):
                data = bytes(json.loads(raw))
            else:
                raise ValueError("Program key format not recognised.")
        except Exception as exc:  # noqa: BLE001
            raise DeployError(f"Failed to read program keypair: {exc}") from exc
        if len(data) not in {32, 64}:
            raise DeployError("Program keypair file is invalid.")
        private_bytes = data[:32]
        public_bytes = data[32:] if len(data) == 64 else ed25519.Ed25519PrivateKey.from_private_bytes(private_bytes).public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    else:
        private = ed25519.Ed25519PrivateKey.generate()
        private_bytes = private.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
        public_bytes = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        payload = list(private_bytes + public_bytes)
        key_path.write_text(json.dumps(payload))
        try:
            os.chmod(key_path, 0o600)
        except PermissionError:
            pass
    return key_path, _b58encode(public_bytes)


def update_declare_id(program_root: Path, program_id: str) -> None:
    """Patch declare_id! macro in the program's lib.rs."""
    lib_rs = program_root / "src" / "lib.rs"
    if not lib_rs.exists():
        raise DeployError(f"{lib_rs} not found.")
    text = lib_rs.read_text()
    pattern = re.compile(r'declare_id!\s*\(\s*"([^"]+)"\s*\)\s*;')
    replacement = f'declare_id!("{program_id}");'
    new_text, count = pattern.subn(replacement, text, count=1)
    if count == 0:
        raise DeployError(f"Unable to locate declare_id! macro in {lib_rs}")
    if new_text != text:
        lib_rs.write_text(new_text)


def update_anchor_mapping(
    anchor_path: Path,
    anchor_config: dict[str, Any],
    *,
    program_name: str,
    program_id: str,
    cluster: str,
) -> None:
    """Ensure Anchor.toml has the correct program mapping for the chosen cluster."""
    programs = anchor_config.setdefault("programs", {})
    current_cluster = programs.setdefault(cluster, {})
    if not isinstance(current_cluster, dict):
        current_cluster = {}
        programs[cluster] = current_cluster
    if current_cluster.get(program_name) != program_id:
        current_cluster[program_name] = program_id
        save_anchor_config(anchor_path, anchor_config)


def run_anchor_command(
    command: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str] | None = None,
    timeout: int = 600,
) -> CommandResult:
    """Execute an anchor CLI command and capture its output."""
    start = time.perf_counter()
    try:
        completed = subprocess.run(  # noqa: S603,S607
            list(command),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            env=dict(env or os.environ),
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise DeployError(f"Command not found: {command[0]}") from exc
    except subprocess.TimeoutExpired as exc:  # type: ignore[attr-defined]
        raise DeployError(f"Command timed out after {timeout} seconds: {' '.join(command)}") from exc
    duration = time.perf_counter() - start
    return CommandResult(
        command=list(command),
        cwd=cwd,
        duration_secs=duration,
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )


def run_anchor_build(
    *,
    project_root: Path,
    env: Mapping[str, str] | None = None,
    timeout: int = 900,
) -> CommandResult:
    """Run `anchor build` in the given workspace."""
    return run_anchor_command(
        ["anchor", "build"],
        cwd=project_root,
        env=env,
        timeout=timeout,
    )


def run_anchor_deploy(
    *,
    project_root: Path,
    program_name: str,
    program_keypair: Path,
    env: Mapping[str, str] | None = None,
    timeout: int = 900,
) -> AnchorDeployResult:
    """Run `anchor deploy` and capture the deployed program id if present."""
    cmd = [
        "anchor",
        "deploy",
        "--program",
        program_name,
        "--program-keypair",
        str(program_keypair),
    ]
    result = run_anchor_command(cmd, cwd=project_root, env=env, timeout=timeout)
    program_id = extract_program_id(result.stdout) or extract_program_id(result.stderr)
    return AnchorDeployResult(
        command=result.command,
        cwd=result.cwd,
        duration_secs=result.duration_secs,
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
        program_id=program_id,
    )


def extract_program_id(output: str) -> str | None:
    """Return the first base58 program id found in anchor output."""
    match = re.search(r"Program Id: ([1-9A-HJ-NP-Za-km-z]{32,44})", output)
    if match:
        return match.group(1)
    # Anchor sometimes logs `Deploying <name> (<pubkey>)`
    match = re.search(r"\(([1-9A-HJ-NP-Za-km-z]{32,44})\)", output)
    if match:
        return match.group(1)
    return None


def verify_workspace(
    *,
    project_root: Path,
    program_name: str,
    cluster: str,
    wallet_exists: bool,
    wallet_unlocked: bool,
) -> DeployVerification:
    """Perform lightweight verification before running build/deploy."""
    errors: list[str] = []
    warnings: list[str] = []
    infos: list[str] = []

    anchor_path = project_root / "Anchor.toml"
    if not anchor_path.exists():
        errors.append(f"Anchor.toml not found at {anchor_path}.")
    else:
        try:
            cfg = load_anchor_config(anchor_path)
            current_id = (
                cfg.get("programs", {})
                .get(cluster, {})
                .get(program_name)
                if isinstance(cfg.get("programs"), dict)
                else None
            )
            if current_id and not _looks_like_base58(current_id):
                warnings.append(f"Program id mapping for {program_name} looks invalid: {current_id}")
        except DeployError as exc:
            errors.append(str(exc))

    program_root = project_root / "programs" / program_name
    if not program_root.exists():
        errors.append(f"Program directory not found: {program_root}")
    elif not (program_root / "src" / "lib.rs").exists():
        errors.append(f"{program_root}/src/lib.rs missing.")

    if shutil.which("anchor") is None:
        errors.append("anchor CLI not found in PATH. Run `/env install anchor`.")

    if shutil.which("solana") is None:
        warnings.append("solana CLI not found in PATH; deploy may fail.")

    if not wallet_exists:
        errors.append("No SolCoder wallet is available. Run `/wallet create` or `/wallet restore` first.")
    elif not wallet_unlocked:
        warnings.append("Wallet is locked. You will be prompted for a passphrase during deploy.")

    infos.append(f"Workspace root: {project_root}")
    infos.append(f"Program: {program_name}")
    infos.append(f"Cluster: {cluster}")
    return DeployVerification(errors=errors, warnings=warnings, infos=infos)


def _b58encode(data: bytes) -> str:
    """Minimal base58 encoder using the Solana alphabet."""
    num = int.from_bytes(data, "big")
    if num == 0:
        return "1" * len(data)
    encoded = ""
    while num > 0:
        num, remainder = divmod(num, 58)
        encoded = BASE58_ALPHABET[remainder] + encoded
    zeros = len(data) - len(data.lstrip(b"\x00"))
    return ("1" * zeros) + encoded


def _looks_like_base58(value: str) -> bool:
    return bool(re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,44}", value))


__all__ = [
    "AnchorDeployResult",
    "CommandResult",
    "DeployError",
    "DeployVerification",
    "discover_anchor_root",
    "ensure_program_keypair",
    "infer_program_name",
    "load_anchor_config",
    "resolve_cluster",
    "run_anchor_build",
    "run_anchor_deploy",
    "update_anchor_mapping",
    "update_declare_id",
    "verify_workspace",
    "extract_program_id",
]
