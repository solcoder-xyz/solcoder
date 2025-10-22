"""Environment diagnostics command."""

from __future__ import annotations

from typing import TYPE_CHECKING

from solcoder.cli.types import CommandResponse, CommandRouter, SlashCommand
from solcoder.core import DiagnosticResult, collect_environment_diagnostics
from solcoder.core.installers import (
    InstallerError,
    InstallerResult,
    install_tool,
    list_installable_tools,
    required_tools,
)

if TYPE_CHECKING:  # pragma: no cover
    from solcoder.cli.app import CLIApp


USAGE = "Usage: /env <diag|install> [options]"


def register(_app: CLIApp, router: CommandRouter) -> None:
    """Register the /env command."""

    def handle(app: CLIApp, args: list[str]) -> CommandResponse:
        if not args:
            return CommandResponse(messages=[("system", USAGE)])

        action = args[0].lower()
        if action in {"diag", "diagnostics"}:
            return _handle_diag(args[1:])
        if action == "install":
            return _handle_install(app, args[1:])

        return CommandResponse(messages=[("system", USAGE)])

    def _handle_diag(_args: list[str]) -> CommandResponse:
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

    def _handle_install(app: CLIApp, args: list[str]) -> CommandResponse:
        if not args:
            tools = ", ".join(list_installable_tools() + ["all"])
            return CommandResponse(
                messages=[("system", f"Usage: /env install <tool|all> [--dry-run]\nAvailable tools: {tools}")]
            )

        dry_run = False
        filtered: list[str] = []
        for token in args:
            if token in {"--dry-run", "-n"}:
                dry_run = True
            else:
                filtered.append(token)

        if not filtered:
            return CommandResponse(messages=[("system", "Specify at least one tool to install.")])

        target = filtered[0].lower()
        available = list_installable_tools()
        install_list: list[str]
        if target == "all":
            install_list = [t for t in required_tools() if t in available]
            for extra in available:
                if extra not in install_list:
                    install_list.append(extra)
        else:
            if target not in available:
                return CommandResponse(
                    messages=[("system", f"Unknown installer '{target}'. Available: {', '.join(available + ['all'])}")]
                )
            install_list = [target]

        results: list[InstallerResult] = []
        errors: list[str] = []
        for tool_key in install_list:
            try:
                runner = None
                if tool_key == "metadata-runner":
                    # Prepare a runner that executes within the project metadata runner directory
                    from pathlib import Path as _Path
                    def _runner(cmd: list[str]):  # type: ignore[override]
                        # Find active workspace
                        active = getattr(app.session_context.metadata, "active_project", None)
                        root = _Path(active).expanduser() if active else _Path.cwd()
                        target = (root / ".solcoder" / "metadata_runner")
                        if not target.exists():
                            # No runner scaffold yet
                            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr=str(target) + " missing; run /metadata set first")
                        full = [cmd[0], cmd[1], f"cd {str(target)} && {cmd[2]}"] if cmd[:2] == ["bash", "-lc"] else cmd
                        return subprocess.run(full, capture_output=True, text=True, check=False)
                    runner = _runner
                result = install_tool(tool_key, console=app.console, dry_run=dry_run, runner=runner)
            except InstallerError as exc:
                errors.append(str(exc))
                continue
            results.append(result)

        summary_lines = _format_install_results(results, dry_run=dry_run)
        if errors:
            summary_lines.append("\nErrors:")
            for error in errors:
                summary_lines.append(f"  - {error}")

        status = "success"
        if errors or any(not item.success for item in results if not item.dry_run):
            status = "error"

        tool_calls = [
            {
                "type": "command",
                "name": f"/env install {'all' if target == 'all' else target}",
                "status": status,
                "summary": f"{len(results)} installer(s) executed",
            }
        ]

        message = "\n".join(summary_lines)
        return CommandResponse(messages=[("system", message)], tool_calls=tool_calls)

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


def _format_install_results(results: list[InstallerResult], *, dry_run: bool) -> list[str]:
    if not results:
        return ["No installers executed."]

    lines = ["Environment Install", "-------------------"]
    for result in results:
        state = result.status
        prefix = {
            "success": "✅",
            "verify-failed": "⚠️",
            "error": "❌",
            "dry-run": "ℹ️",
        }.get(state, "•")
        detail = result.error if result.error else ""
        lines.append(f"{prefix} {result.display_name} — {state}{f' ({detail})' if detail else ''}")
        if not dry_run and result.logs:
            snippet = list(result.logs[-10:])
            for log_line in snippet:
                trimmed = log_line.strip()
                if trimmed:
                    lines.append(f"    {trimmed}")
    if dry_run:
        lines.append("\nDry run only: no commands were executed.")
    return lines


__all__ = ["register"]
