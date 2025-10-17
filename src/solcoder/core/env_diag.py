"""Environment diagnostics for SolCoder."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, List
import shutil
import subprocess


@dataclass(frozen=True)
class ToolRequirement:
    name: str
    executable: str
    version_args: list[str]
    remediation: str


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
        version_args=["--version"],
        remediation="Install the Solana CLI: https://docs.solana.com/cli/install-solana-cli",
    ),
    ToolRequirement(
        name="Anchor",
        executable="anchor",
        version_args=["--version"],
        remediation="Install Anchor with `cargo install --git https://github.com/coral-xyz/anchor anchor-cli --locked`.",
    ),
    ToolRequirement(
        name="Rust Compiler",
        executable="rustc",
        version_args=["--version"],
        remediation="Install Rust using rustup: https://rustup.rs/",
    ),
    ToolRequirement(
        name="Cargo",
        executable="cargo",
        version_args=["--version"],
        remediation="Install Rust toolchain with rustup if Cargo is missing: https://rustup.rs/",
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
        if not path:
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
