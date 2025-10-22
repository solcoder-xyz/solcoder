"""Session-related commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

from solcoder.cli.export_utils import format_export_text
from solcoder.cli.types import CommandResponse, CommandRouter, SlashCommand
from solcoder.session import SessionLoadError
from solcoder.session.manager import MAX_SESSIONS

if TYPE_CHECKING:  # pragma: no cover
    from solcoder.cli.app import CLIApp


def register(app: CLIApp, router: CommandRouter) -> None:
    """Register the /session command."""

    def handle(app: CLIApp, args: list[str]) -> CommandResponse:
        if not args:
            return CommandResponse(messages=[("system", "Usage: /session export <id> | /session set project <path>")])

        command, *rest = args
        if command.lower() == "export":
            if not rest:
                return CommandResponse(messages=[("system", "Usage: /session export <id>")])

            session_id = rest[0]
            tool_summary = [
                {
                    "type": "command",
                    "name": "/session export",
                    "status": "success",
                    "summary": f"Exported session {session_id}",
                }
            ]
            try:
                export_data = app.session_manager.export_session(session_id, redact=True)
            except FileNotFoundError:
                message = (
                    f"Session '{session_id}' not found. Only the most recent {MAX_SESSIONS} sessions are retained."
                )
                tool_summary[0]["status"] = "not_found"
                tool_summary[0]["summary"] = f"Session {session_id} missing"
                return CommandResponse(messages=[("system", message)], tool_calls=tool_summary)
            except SessionLoadError as exc:
                tool_summary[0]["status"] = "error"
                tool_summary[0]["summary"] = str(exc)
                return CommandResponse(messages=[("system", f"Failed to load session: {exc}")], tool_calls=tool_summary)

            content = format_export_text(export_data)
            return CommandResponse(messages=[("system", content)], tool_calls=tool_summary)

        if command.lower() == "set":
            if len(rest) < 2:
                return CommandResponse(messages=[("system", "Usage: /session set project <path>")])
            target_key = rest[0].lower()
            if target_key != "project":
                return CommandResponse(messages=[("system", "Unknown setting. Try: /session set project <path>")])
            target_path = rest[1]
            from pathlib import Path

            p = Path(target_path).expanduser()
            try:
                p = p.resolve()
            except Exception:
                p = p.expanduser()

            if not (p / "Anchor.toml").exists():
                return CommandResponse(
                    messages=[
                        (
                            "system",
                            f"Path '{p}' does not look like an Anchor workspace (missing Anchor.toml).",
                        )
                    ]
                )

            # Update active project in the current session
            app.session_context.metadata.active_project = str(p)
            app.session_manager.save(app.session_context)

            # Persist as project-level default for future sessions
            try:
                project_home = Path.cwd() / ".solcoder"
                project_home.mkdir(parents=True, exist_ok=True)
                (project_home / "active_workspace").write_text(str(p))
            except Exception:
                # Best-effort; ignore persistence errors
                pass

            tool_summary = [
                {
                    "type": "command",
                    "name": "/session set project",
                    "status": "success",
                    "summary": f"Active workspace set to {p}",
                }
            ]
            return CommandResponse(
                messages=[("system", f"Active workspace set to {p}.")], tool_calls=tool_summary
            )

        if command.lower() == "compact":
            summary = app.force_compact_history()
            return CommandResponse(messages=[("system", summary)])

        return CommandResponse(messages=[("system", "Unknown session command. Try `/session export <id>` or `/session set project <path>`.")])

    router.register(SlashCommand("session", handle, "Session utilities"))


__all__ = ["register"]
