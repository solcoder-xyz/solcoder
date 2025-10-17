"""Environment diagnostics command."""

from __future__ import annotations

from typing import TYPE_CHECKING

from solcoder.cli.types import CommandResponse, CommandRouter, SlashCommand
from solcoder.core import DiagnosticResult, collect_environment_diagnostics

if TYPE_CHECKING:  # pragma: no cover
    from solcoder.cli.app import CLIApp


def register(_app: CLIApp, router: CommandRouter) -> None:
    """Register the /env command."""

    def handle(app: CLIApp, args: list[str]) -> CommandResponse:
        if not args or args[0].lower() not in {"diag", "diagnostics"}:
            return CommandResponse(messages=[("system", "Usage: /env diag")])

        results = collect_environment_diagnostics()
        content = _format_env_diag(results)
        total = len(results)
        missing = sum(not item.found for item in results)
        degraded = sum(item.status in {"warn", "error"} for item in results)
        if missing:
            tool_status = "missing"
        elif degraded:
            tool_status = "warn"
        else:
            tool_status = "ok"
        summary = f"{total - missing} of {total} tools detected"
        if missing or degraded:
            summary += f"; {missing} missing, {degraded} warnings"
        tool_calls = [
            {
                "type": "command",
                "name": "/env diag",
                "status": tool_status,
                "summary": summary,
            }
        ]
        return CommandResponse(messages=[("system", content)], tool_calls=tool_calls)

    router.register(SlashCommand("env", handle, "Environment diagnostics"))


def _format_env_diag(results: list[DiagnosticResult]) -> str:
    lines = ["Environment Diagnostics", "======================"]
    header = f"{'Tool':<22} {'Status':<8} Details"
    lines.append(header)
    lines.append("-" * len(header))
    for item in results:
        status_label = {
            "ok": "OK",
            "warn": "WARN",
            "missing": "MISSING",
            "error": "ERROR",
        }.get(item.status, item.status.upper())
        if item.found and item.version:
            detail = item.version
        elif item.found:
            detail = "Detected (version unavailable)"
        else:
            detail = "Not found in PATH"
        if item.details:
            detail = f"{detail} ({item.details})"
        lines.append(f"{item.name:<22} {status_label:<8} {detail}")
        if item.remediation and status_label != "OK":
            lines.append(f"    ↳ {item.remediation}")
    return "\n".join(lines)


__all__ = ["register"]
