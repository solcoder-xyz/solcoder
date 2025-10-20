from __future__ import annotations

import subprocess
from urllib.parse import quote

import solcoder.core.exec_ua as exec_ua


def _completed(args, returncode=0, stdout="", stderr="") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args, returncode=returncode, stdout=stdout, stderr=stderr)


def test_build_exec_ua_header_compiles_expected_tokens(monkeypatch, tmp_path):
    exec_ua.clear_exec_ua_cache()

    project_dir = tmp_path / "My Project"
    project_dir.mkdir()
    monkeypatch.chdir(project_dir)
    monkeypatch.setenv("SHELL", "/bin/zsh")
    monkeypatch.delenv("COMSPEC", raising=False)

    monkeypatch.setattr(exec_ua.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(exec_ua.platform, "mac_ver", lambda: ("14.6.1", ("", "", ""), ""))
    monkeypatch.setattr(exec_ua.platform, "machine", lambda: "arm64")

    available = {
        "brew": "/opt/homebrew/bin/brew",
        "pip": "/usr/bin/pip3",
        "npm": "/usr/local/bin/npm",
        "sudo": "/usr/bin/sudo",
        "git": "/usr/bin/git",
        "node": "/usr/local/bin/node",
    }

    def fake_which(executable: str) -> str | None:
        return available.get(executable)

    monkeypatch.setattr(exec_ua.shutil, "which", fake_which)

    python_cmd = exec_ua.sys.executable

    def fake_run(args, *, timeout=2.0):
        if list(args) == ["/bin/zsh", "--version"]:
            return _completed(args, stdout="zsh 5.9 (arm64-apple-darwin)")
        if list(args[:3]) == ["/usr/bin/sudo", "-n", "true"]:
            return _completed(args, returncode=1, stderr="sudo: a password is required")
        if list(args[:3]) == ["/usr/bin/git", "rev-parse", "--is-inside-work-tree"]:
            return _completed(args, stdout="true\n")
        if list(args[:4]) == ["/usr/bin/git", "rev-parse", "--abbrev-ref", "HEAD"]:
            return _completed(args, stdout="feature-x\n")
        if list(args[:3]) == ["/usr/bin/git", "status", "--porcelain"]:
            return _completed(args, stdout=" M README.md\n")
        if list(args) in ([ "/usr/local/bin/node", "--version"], ["node", "--version"]):
            return _completed(args, stdout="v20.11.0\n")
        if list(args) == [python_cmd, "--version"]:
            return _completed(args, stdout=f"Python {exec_ua.sys.version_info.major}.{exec_ua.sys.version_info.minor}.0")
        if list(args[:2]) in ([ "/usr/bin/git", "--version"], ["git", "--version"]):
            return _completed(args, stdout="git version 2.44.1")
        return _completed(args)

    monkeypatch.setattr(exec_ua, "_run_command", fake_run)

    encoded_cwd = quote(str(project_dir), safe="/:\\")
    python_version = f"{exec_ua.sys.version_info.major}.{exec_ua.sys.version_info.minor}"

    header = exec_ua.build_exec_ua_header(timeout=42, refresh=True)
    expected = (
        "Exec-UA: spec=v1; os=macos; ver=14.6; arch=arm64; shell=zsh/5.9; "
        f"pm=brew,pip,npm; sudo=prompt; cwd={encoded_cwd}; git=1:feature-x*; "
        f"tools=node/20.11,python/{python_version},git/2.44; timeout=42;"
    )
    assert header == expected

    cached = exec_ua.build_exec_ua_header(timeout=42)
    assert cached is header
