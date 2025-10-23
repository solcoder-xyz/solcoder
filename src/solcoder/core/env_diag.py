"""Environment diagnostics for SolCoder."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List
import shutil
import subprocess


@dataclass(frozen=True)
class ToolRequirement:
    name: str
    executable: str
    version_args: list[str]
    remediation: str
    fallback_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class DiagnosticResult:
    name: str
    status: str
    found: bool
    version: str | None
    remediation: str | None
    details: str | None = None


ToolRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]
WhichResolver = Callable[[str], str | None]


REQUIRED_TOOLS: tuple[ToolRequirement, ...] = (
    ToolRequirement(
        name="Solana CLI",
        executable="solana",
        version_args=["--help"],
        remediation="Install the Solana CLI: https://docs.solana.com/cli/install-solana-cli",
        fallback_paths=(
            "~/.local/share/solana/install/active_release/bin/solana",
        ),
    ),
    ToolRequirement(
        name="Anchor",
        executable="anchor",
        version_args=["--version"],
        remediation="Install Anchor with `cargo install --git https://github.com/coral-xyz/anchor anchor-cli --locked`.",
        fallback_paths=(
            "~/.cargo/bin/anchor",
        ),
    ),
    ToolRequirement(
        name="Rust Compiler",
        executable="rustc",
        version_args=["--version"],
        remediation="Install Rust using rustup: https://rustup.rs/",
        fallback_paths=(
            "~/.cargo/bin/rustc",
        ),
    ),
    ToolRequirement(
        name="Cargo",
        executable="cargo",
        version_args=["--version"],
        remediation="Install Rust toolchain with rustup if Cargo is missing: https://rustup.rs/",
        fallback_paths=(
            "~/.cargo/bin/cargo",
        ),
    ),
    ToolRequirement(
        name="Cargo build-sbf",
        executable="cargo-build-sbf",
        version_args=["--help"],
        remediation=(
            "Install the Solana SBF toolchain plugin: "
            "`cargo install --git https://github.com/solana-labs/cargo-build-sbf cargo-build-sbf --locked "
            "--config net.git-fetch-with-cli=true` and ensure $HOME/.cargo/bin is on your PATH."
        ),
        fallback_paths=(
            "~/.cargo/bin/cargo-build-sbf",
        ),
    ),
    ToolRequirement(
        name="Node.js",
        executable="node",
        version_args=["--version"],
        remediation="Install Node.js via nvm or the official installer: https://nodejs.org/en/download",
    ),
    ToolRequirement(
        name="npm",
        executable="npm",
        version_args=["--version"],
        remediation="Install npm by installing Node.js: https://nodejs.org/en/download",
    ),
    ToolRequirement(
        name="Yarn",
        executable="yarn",
        version_args=["--version"],
        remediation="Enable Yarn via Corepack: `npm install -g corepack && corepack enable`.",
        fallback_paths=(
            "~/.yarn/bin/yarn",
            "~/.local/bin/yarn",
            "~/.volta/bin/yarn",
            "~/.fnm/bin/yarn",
            "~/.local/share/fnm/aliases/default/bin/yarn",
        ),
    ),
    ToolRequirement(
        name="Python 3",
        executable="python3",
        version_args=["--version"],
        remediation="Install Python 3 using your OS package manager or https://www.python.org/downloads/.",
    ),
    ToolRequirement(
        name="pip",
        executable="pip3",
        version_args=["--version"],
        remediation="Install pip with `python3 -m ensurepip --upgrade`.",
    ),
    ToolRequirement(
        name="SPL Token CLI",
        executable="spl-token",
        version_args=["--version"],
        remediation=(
            "Install with `cargo install spl-token-cli` and ensure `$HOME/.cargo/bin` is on your PATH."
        ),
        fallback_paths=(
            "~/.cargo/bin/spl-token",
        ),
    ),
    ToolRequirement(
        name="Umi Runtime",
        executable="node",
        version_args=["--version"],
        remediation="Install Node.js (nvm or official installer) to run Umi runners.",
    ),
)


def _default_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False, timeout=5)


def collect_environment_diagnostics(
    *,
    runner: ToolRunner | None = None,
    resolver: WhichResolver | None = None,
    tools: Iterable[ToolRequirement] = REQUIRED_TOOLS,
) -> List[DiagnosticResult]:
    which = resolver or shutil.which
    exec_runner = runner or _default_runner
    results: List[DiagnosticResult] = []
    for tool in tools:
        path = which(tool.executable)
        fallback_path: str | None = None
        if not path and tool.fallback_paths:
            for raw in tool.fallback_paths:
                candidate = Path(raw).expanduser()
                if candidate.exists():
                    fallback_path = str(candidate)
                    break

        if not path and fallback_path is None:
            results.append(
                DiagnosticResult(
                    name=tool.name,
                    status="missing",
                    found=False,
                    version=None,
                    remediation=tool.remediation,
                )
            )
            continue

        if not path and fallback_path:
            try:
                completed = exec_runner([fallback_path, *tool.version_args])
            except Exception as exc:  # noqa: BLE001
                results.append(
                    DiagnosticResult(
                        name=tool.name,
                        status="missing",
                        found=False,
                        version=None,
                        remediation=tool.remediation,
                        details=f"Found at {fallback_path} but failed to execute: {exc}",
                    )
                )
                continue

            output = (completed.stdout or completed.stderr or "").strip()
            version = output.splitlines()[0].strip() if output else "unknown"
            parent_dir = Path(fallback_path).expanduser().parent
            remediation = (
                f"{tool.remediation} Add {parent_dir} to your PATH."
                if tool.remediation
                else f"Add {parent_dir} to your PATH."
            )
            results.append(
                DiagnosticResult(
                    name=tool.name,
                    status="missing",
                    found=False,
                    version=version,
                    remediation=remediation,
                    details=f"Detected at {fallback_path}, but it is not on PATH.",
                )
            )
            continue

        assert path is not None  # for type checkers
        try:
            completed = exec_runner([path, *tool.version_args])
        except Exception as exc:  # noqa: BLE001
            results.append(
                DiagnosticResult(
                    name=tool.name,
                    status="error",
                    found=True,
                    version=None,
                    remediation=tool.remediation,
                    details=str(exc),
                )
            )
            continue

        output = (completed.stdout or completed.stderr or "").strip()
        version = output.splitlines()[0].strip() if output else "unknown"
        status = "ok" if completed.returncode == 0 and output else "warn"
        details = None
        if completed.returncode != 0 and not details:
            details = f"Non-zero exit code: {completed.returncode}"
        results.append(
            DiagnosticResult(
                name=tool.name,
                status=status,
                found=True,
                version=version,
                remediation=None if status == "ok" else tool.remediation,
                details=details,
            )
        )
    return results


__all__ = ["DiagnosticResult", "ToolRequirement", "collect_environment_diagnostics", "REQUIRED_TOOLS"]
