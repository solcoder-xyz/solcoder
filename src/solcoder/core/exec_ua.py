"""Exec-UA header generation for SolCoder."""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Mapping, Sequence
from urllib.parse import quote

_SPEC_VERSION = "v1"
_DEFAULT_TIMEOUT_SECONDS = 15.0
_VERSION_PATTERN = re.compile(r"(\d+\.\d+)")
_EXEC_UA_CACHE: dict[str, str] = {}

_PM_CANDIDATES: Mapping[str, str] = {
    "apt": "apt",
    "brew": "brew",
    "choco": "choco",
    "pip": "pip",
    "npm": "npm",
    "yarn": "yarn",
    "pnpm": "pnpm",
}

_TOOL_PROBES: tuple[tuple[str, Sequence[str]], ...] = (
    ("node", ("node", "--version")),
    ("python", (sys.executable, "--version")),
    ("git", ("git", "--version")),
)


def _run_command(args: Sequence[str], *, timeout: float = 2.0) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(  # noqa: S603,S607
            args,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except Exception as exc:  # noqa: BLE001
        return subprocess.CompletedProcess(args, returncode=1, stdout="", stderr=str(exc))


def _normalize_version(raw: str | None) -> str:
    if not raw:
        return "unknown"
    match = _VERSION_PATTERN.search(raw)
    if not match:
        return "unknown"
    return match.group(1)


def _detect_os() -> tuple[str, str]:
    system = platform.system().lower()
    if system == "darwin":
        os_name = "macos"
        version = platform.mac_ver()[0]
    elif system == "windows":
        os_name = "windows"
        version = platform.win32_ver()[0]
    elif system == "linux":
        os_name = "linux"
        version = ""
        if hasattr(platform, "freedesktop_os_release"):
            try:
                release_info = platform.freedesktop_os_release()
            except Exception:  # noqa: BLE001
                release_info = {}
            version = (release_info or {}).get("VERSION_ID") or ""
        if not version:
            version = platform.release()
    else:
        os_name = system or "unknown"
        version = platform.release()
    version = version or "unknown"
    parts = version.split(".")
    if len(parts) > 2:
        version = ".".join(parts[:2])
    return os_name, version


def _detect_arch() -> str:
    machine = platform.machine().lower()
    if "arm" in machine or "aarch64" in machine:
        return "arm64"
    if machine in {"x86_64", "amd64"}:
        return "x86_64"
    return machine or "unknown"


def _detect_shell() -> str:
    shell_path = os.environ.get("SHELL") or os.environ.get("COMSPEC")
    if not shell_path:
        return "unknown/unknown"
    shell_name = Path(shell_path).name
    version_output = _run_command([shell_path, "--version"])
    version = _normalize_version(version_output.stdout or version_output.stderr)
    if version == "unknown" and shell_name.lower() in {"pwsh", "powershell"}:
        alt = _run_command([shell_path, "-NoLogo", "-Command", "$PSVersionTable.PSVersion.ToString()"])
        version = _normalize_version(alt.stdout or alt.stderr)
    return f"{shell_name}/{version}"


def _detect_package_managers() -> str:
    detected: list[str] = []
    for key, exe in _PM_CANDIDATES.items():
        if shutil.which(exe):
            detected.append(key)
    return ",".join(detected) if detected else "none"


def _detect_sudo_mode(os_name: str) -> str:
    if os_name == "windows":
        return "forbidden"
    sudo_path = shutil.which("sudo")
    if not sudo_path:
        return "forbidden"
    result = _run_command([sudo_path, "-n", "true"])
    if result.returncode == 0:
        return "passwordless"
    stderr = (result.stderr or "").lower()
    if "password" in stderr or "a terminal is required" in stderr or result.returncode == 1:
        return "prompt"
    return "prompt"


def _detect_cwd() -> str:
    cwd = str(Path.cwd())
    return quote(cwd, safe="/:\\")


def _detect_git_state() -> str:
    git_path = shutil.which("git")
    if not git_path:
        return "0"
    inside = _run_command([git_path, "rev-parse", "--is-inside-work-tree"])
    if inside.returncode != 0 or (inside.stdout or "").strip().lower() != "true":
        return "0"
    branch = _run_command([git_path, "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip() or "unknown"
    status = _run_command([git_path, "status", "--porcelain"]).stdout.strip()
    dirty = "*" if status else ""
    branch_clean = branch.replace(" ", "_")
    return f"1:{branch_clean}{dirty}"


def _detect_tools() -> str:
    tools: list[str] = []
    for name, command in _TOOL_PROBES:
        if name == "python":
            version = f"{sys.version_info.major}.{sys.version_info.minor}"
        else:
            if not shutil.which(command[0]):
                continue
            result = _run_command(command)
            version = _normalize_version(result.stdout or result.stderr)
        if version == "unknown":
            continue
        tools.append(f"{name}/{version}")
    return ",".join(tools)


def _normalize_timeout(timeout: float | int | None) -> str:
    value = _DEFAULT_TIMEOUT_SECONDS if timeout is None else float(timeout)
    if value.is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def build_exec_ua_header(*, timeout: float | int | None = None, refresh: bool = False) -> str:
    """Return the Exec-UA header string describing the current environment."""
    cache_key = str(timeout) if timeout is not None else "default"
    if not refresh and cache_key in _EXEC_UA_CACHE:
        return _EXEC_UA_CACHE[cache_key]

    os_name, os_version = _detect_os()
    arch = _detect_arch()
    shell = _detect_shell()
    package_managers = _detect_package_managers()
    sudo_mode = _detect_sudo_mode(os_name)
    cwd = _detect_cwd()
    git_state = _detect_git_state()
    tools = _detect_tools()
    timeout_value = _normalize_timeout(timeout)

    tokens = [
        f"spec={_SPEC_VERSION}",
        f"os={os_name}",
        f"ver={os_version}",
        f"arch={arch}",
        f"shell={shell}",
        f"pm={package_managers}",
        f"sudo={sudo_mode}",
        f"cwd={cwd}",
        f"git={git_state}",
        f"tools={tools}" if tools else "tools=unknown",
        f"timeout={timeout_value}",
    ]
    header = "Exec-UA: " + "; ".join(tokens) + ";"
    _EXEC_UA_CACHE[cache_key] = header
    return header


def clear_exec_ua_cache() -> None:
    _EXEC_UA_CACHE.clear()


__all__ = ["build_exec_ua_header", "clear_exec_ua_cache"]
