"""Environment installer helpers for SolCoder."""

from __future__ import annotations

import platform
import subprocess
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

from typing_extensions import TypeAlias

from solcoder.core.env_diag import DiagnosticResult, collect_environment_diagnostics

Runner: TypeAlias = Callable[[list[str]], subprocess.CompletedProcess[str]]


class InstallerError(RuntimeError):
    """Raised when an installer cannot complete successfully."""


@dataclass(slots=True)
class InstallerSpec:
    """Definition describing how to install and verify a tool."""

    key: str
    display_name: str
    command_map: Mapping[str, Sequence[str]]
    verification_targets: Sequence[str]
    required: bool = True
    environment: Mapping[str, str] | None = None


@dataclass(slots=True)
class InstallerResult:
    """Result returned after running an installer."""

    tool: str
    display_name: str
    success: bool
    verification_passed: bool
    commands: Sequence[str]
    logs: Sequence[str]
    error: str | None = None
    dry_run: bool = False

    @property
    def status(self) -> str:
        if self.dry_run:
            return "dry-run"
        if self.success and self.verification_passed:
            return "success"
        if self.success and not self.verification_passed:
            return "verify-failed"
        return "error"


def _platform_key() -> str:
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    if system == "linux":
        return "linux"
    if system == "windows":
        return "windows"
    return system


def _bash_command(cmd: str) -> list[str]:
    return ["bash", "-lc", cmd]


INSTALLER_SPECS: dict[str, InstallerSpec] = {
    "solana": InstallerSpec(
        key="solana",
        display_name="Solana CLI",
        command_map={
            "macos": (
                "curl -sSfL https://release.solana.com/stable/install | bash -s -- -y",
            ),
            "linux": (
                "curl -sSfL https://release.solana.com/stable/install | bash -s -- -y",
            ),
        },
        verification_targets=("Solana CLI",),
        environment={
            "SOLANA_INSTALL_NONINTERACTIVE": "1",
        },
    ),
    "anchor": InstallerSpec(
        key="anchor",
        display_name="Anchor CLI",
        command_map={
            "macos": (
                "cargo install --git https://github.com/coral-xyz/anchor anchor-cli --locked",
            ),
            "linux": (
                "cargo install --git https://github.com/coral-xyz/anchor anchor-cli --locked",
            ),
        },
        verification_targets=("Anchor",),
    ),
    "rust": InstallerSpec(
        key="rust",
        display_name="Rust toolchain",
        command_map={
            "macos": (
                "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | bash -s -- -y",
                "source $HOME/.cargo/env",
            ),
            "linux": (
                "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | bash -s -- -y",
                "source $HOME/.cargo/env",
            ),
        },
        verification_targets=("Rust Compiler", "Cargo"),
    ),
    "node": InstallerSpec(
        key="node",
        display_name="Node.js + npm",
        command_map={
            "macos": (
                "curl -fsSL https://fnm.vercel.app/install | bash",
                "export PATH=\"$HOME/.local/share/fnm:$PATH\" && eval \"$(fnm env)\" && fnm install --lts",
            ),
            "linux": (
                "curl -fsSL https://fnm.vercel.app/install | bash",
                "export PATH=\"$HOME/.local/share/fnm:$PATH\" && eval \"$(fnm env)\" && fnm install --lts",
            ),
        },
        verification_targets=("Node.js", "npm"),
    ),
    "yarn": InstallerSpec(
        key="yarn",
        display_name="Yarn",
        command_map={
            "macos": ("npm install -g corepack", "corepack enable", "corepack prepare yarn@stable --activate"),
            "linux": ("npm install -g corepack", "corepack enable", "corepack prepare yarn@stable --activate"),
        },
        verification_targets=("Yarn",),
        required=False,
    ),
}


def list_installable_tools() -> list[str]:
    """Return the list of supported installer keys."""
    return list(INSTALLER_SPECS.keys())


def required_tools() -> list[str]:
    """Return the subset of installer keys required for bootstrap."""
    return [spec.key for spec in INSTALLER_SPECS.values() if spec.required]


def installer_display_name(tool: str) -> str:
    spec = INSTALLER_SPECS.get(tool)
    if spec is None:
        raise InstallerError(f"Unknown installer '{tool}'.")
    return spec.display_name


def detect_missing_tools(
    diagnostics: Iterable[DiagnosticResult],
    *,
    only_required: bool = False,
) -> list[str]:
    """Return installer keys that are missing according to diagnostics."""
    diag_map = {item.name: item for item in diagnostics}
    missing: list[str] = []
    for key, spec in INSTALLER_SPECS.items():
        if only_required and not spec.required:
            continue
        if not _has_tool(spec, diag_map):
            missing.append(key)
    return missing


def install_tool(
    tool: str,
    *,
    console=None,
    dry_run: bool = False,
    runner: Runner | None = None,
) -> InstallerResult:
    """Install the specified tool."""
    spec = INSTALLER_SPECS.get(tool)
    if spec is None:
        raise InstallerError(f"Unknown installer '{tool}'.")
    platform_key = _platform_key()
    commands = spec.command_map.get(platform_key)
    if not commands:
        raise InstallerError(
            f"Installer '{tool}' is not supported on platform '{platform_key}'."
        )

    executed_commands: list[str] = []
    logs: list[str] = []
    env = dict(spec.environment or {})
    success = True
    error: str | None = None

    for command in commands:
        executed_commands.append(command)
        if dry_run:
            logs.append(f"[dry-run] {command}")
            continue
        if console:
            console.print(f"[bold #14F195]$ {command}[/]")
        if runner:
            completed = runner(_bash_command(command))
            output = (completed.stdout or "") + (completed.stderr or "")
            if output:
                for line in output.splitlines():
                    logs.append(line)
                    if console:
                        console.print(line)
            if completed.returncode != 0:
                success = False
                error = f"Command exited with {completed.returncode}"
                break
        else:
            return_code, output_lines = _run_command(command, env=env, console=console)
            logs.extend(output_lines)
            if return_code != 0:
                success = False
                error = f"Command exited with {return_code}"
                break

    verification_passed = False
    if success and not dry_run:
        _refresh_environment(spec)
        diagnostics = collect_environment_diagnostics()
        verification_passed = _has_tool(spec, {d.name: d for d in diagnostics})
        if not verification_passed and success:
            error = "Post-install verification failed."
            success = False

    return InstallerResult(
        tool=spec.key,
        display_name=spec.display_name,
        success=success,
        verification_passed=verification_passed,
        commands=tuple(executed_commands),
        logs=tuple(logs),
        error=error,
        dry_run=dry_run,
    )


def _has_tool(spec: InstallerSpec, diag_map: Mapping[str, DiagnosticResult]) -> bool:
    for target in spec.verification_targets:
        diag = diag_map.get(target)
        if diag is None or not diag.found:
            return False
    return True


def _run_command(
    command: str,
    *,
    env: Mapping[str, str] | None = None,
    console=None,
) -> tuple[int, list[str]]:
    merged_env = None
    if env:
        merged_env = {**os.environ, **env}

    process = subprocess.Popen(  # noqa: S603,S607
        _bash_command(command),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=merged_env,
    )
    output_lines: list[str] = []
    try:
        if process.stdout is not None:
            for line in process.stdout:
                stripped = line.rstrip("\n")
                output_lines.append(stripped)
                if console:
                    console.print(stripped)
    finally:
        return_code = process.wait()
    return return_code, output_lines


def _refresh_environment(spec: InstallerSpec) -> None:
    home = Path.home()
    additions: list[str] = []

    if spec.key == "rust":
        additions.append(str(home / ".cargo" / "bin"))
    elif spec.key == "solana":
        active = home / ".local" / "share" / "solana" / "install" / "active_release" / "bin"
        if active.exists():
            additions.append(str(active))
    elif spec.key in {"node", "yarn"}:
        fnm_dir = home / ".local" / "share" / "fnm"
        additions.append(str(fnm_dir))
        alias = fnm_dir / "aliases" / "default"
        if alias.exists():
            additions.append(str(alias))
            bin_dir = alias / "bin"
            if bin_dir.exists():
                additions.append(str(bin_dir))

    if not additions:
        return

    current = os.environ.get("PATH", "")
    parts = [entry for entry in current.split(os.pathsep) if entry]
    updated = False
    for entry in additions:
        if entry and entry not in parts:
            parts.insert(0, entry)
            updated = True
    if updated:
        os.environ["PATH"] = os.pathsep.join(parts)


__all__ = [
    "InstallerError",
    "InstallerResult",
    "detect_missing_tools",
    "install_tool",
    "installer_display_name",
    "list_installable_tools",
    "required_tools",
]
