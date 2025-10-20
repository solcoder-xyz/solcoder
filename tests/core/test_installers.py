from __future__ import annotations

from solcoder.core.env_diag import DiagnosticResult
from solcoder.core.installers import (
    InstallerError,
    detect_missing_tools,
    install_tool,
    installer_display_name,
    list_installable_tools,
    required_tools,
)


def test_detect_missing_tools_flags_required() -> None:
    diagnostics = [
        DiagnosticResult(
            name="Solana CLI",
            status="missing",
            found=False,
            version=None,
            remediation="Install",
        ),
        DiagnosticResult(
            name="Anchor",
            status="ok",
            found=True,
            version="anchor-cli 0.29.0",
            remediation=None,
        ),
        DiagnosticResult(
            name="Rust Compiler",
            status="ok",
            found=True,
            version="rustc 1.73",
            remediation=None,
        ),
        DiagnosticResult(
            name="Cargo",
            status="ok",
            found=True,
            version="cargo 1.73",
            remediation=None,
        ),
        DiagnosticResult(
            name="Node.js",
            status="ok",
            found=True,
            version="v20.8.0",
            remediation=None,
        ),
        DiagnosticResult(
            name="npm",
            status="ok",
            found=True,
            version="10.1.0",
            remediation=None,
        ),
        DiagnosticResult(
            name="Yarn",
            status="missing",
            found=False,
            version=None,
            remediation="Enable corepack",
        ),
        DiagnosticResult(
            name="Python 3",
            status="ok",
            found=True,
            version="Python 3.11.6",
            remediation=None,
        ),
        DiagnosticResult(
            name="pip",
            status="ok",
            found=True,
            version="pip 23.2",
            remediation=None,
        ),
    ]

    missing_required = detect_missing_tools(diagnostics, only_required=True)
    assert "solana" in missing_required
    assert "anchor" not in missing_required


def test_install_tool_dry_run_returns_result() -> None:
    tools = list_installable_tools()
    assert tools
    for tool in required_tools():
        result = install_tool(tool, dry_run=True)
        assert result.dry_run is True
        assert result.tool == tool
        assert result.commands


def test_installer_display_name_unknown() -> None:
    try:
        installer_display_name("unknown-tool")
    except InstallerError:
        pass
    else:  # pragma: no cover - should never happen
        raise AssertionError("Expected InstallerError for unknown tool")
