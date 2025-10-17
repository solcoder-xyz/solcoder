
"""Interactive CLI shell for SolCoder."""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from datetime import UTC, datetime
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from solcoder.core import (
    ConfigContext,
    DiagnosticResult,
    RenderOptions,
    available_templates,
    collect_environment_diagnostics,
    render_template,
    TemplateError,
)
from solcoder.session import TRANSCRIPT_LIMIT, SessionContext, SessionManager, SessionLoadError
from solcoder.session.manager import MAX_SESSIONS
from solcoder.solana import SolanaRPCClient, WalletError, WalletManager, WalletStatus

logger = logging.getLogger(__name__)


DEFAULT_HISTORY_PATH = Path(os.environ.get("SOLCODER_HOME", Path.home() / ".solcoder")) / "history"


@dataclass
class CommandResponse:
    """Represents the outcome of handling a CLI input."""

    messages: list[tuple[str, str]]
    continue_loop: bool = True
    tool_calls: list[dict[str, Any]] | None = None


def _parse_template_tokens(
    template_name: str,
    tokens: list[str],
    defaults: dict[str, str],
) -> tuple[RenderOptions | None, str | None]:
    destination: Path | None = None
    program_name = defaults["program_name"]
    author = defaults["author_pubkey"]
    program_id = "replace-with-program-id"
    cluster = "devnet"
    overwrite = False

    idx = 0
    while idx < len(tokens):
        token = tokens[idx]
        if token == "--force":
            overwrite = True
            idx += 1
            continue
        if token == "--program" and idx + 1 < len(tokens):
            program_name = tokens[idx + 1]
            idx += 2
            continue
        if token.startswith("--program="):
            program_name = token.split("=", 1)[1]
            idx += 1
            continue
        if token == "--author" and idx + 1 < len(tokens):
            author = tokens[idx + 1]
            idx += 2
            continue
        if token.startswith("--author="):
            author = token.split("=", 1)[1]
            idx += 1
            continue
        if token == "--program-id" and idx + 1 < len(tokens):
            program_id = tokens[idx + 1]
            idx += 2
            continue
        if token.startswith("--program-id="):
            program_id = token.split("=", 1)[1]
            idx += 1
            continue
        if token == "--cluster" and idx + 1 < len(tokens):
            cluster = tokens[idx + 1]
            idx += 2
            continue
        if token.startswith("--cluster="):
            cluster = token.split("=", 1)[1]
            idx += 1
            continue
        if token.startswith("-"):
            return None, f"Unknown option '{token}'."
        if destination is None:
            destination = Path(token)
            idx += 1
            continue
        return None, "Unexpected extra argument."

    if destination is None:
        return None, "Destination path is required."

    options = RenderOptions(
        template=template_name,
        destination=destination,
        program_name=program_name,
        author_pubkey=author,
        program_id=program_id,
        cluster=cluster,
        overwrite=overwrite,
    )
    return options, None


class SlashCommand:
    """Container for slash command metadata."""

    def __init__(self, name: str, handler: Callable[[CLIApp, list[str]], CommandResponse], help_text: str) -> None:
        self.name = name
        self.handler = handler
        self.help_text = help_text


class CommandRouter:
    """Parses and dispatches slash commands."""

    def __init__(self) -> None:
        self._commands: dict[str, SlashCommand] = {}

    def register(self, command: SlashCommand) -> None:
        logger.debug("Registering command: %s", command.name)
        self._commands[command.name] = command

    def available_commands(self) -> Iterable[SlashCommand]:
        return self._commands.values()

    def dispatch(self, app: CLIApp, raw_line: str) -> CommandResponse:
        parts = raw_line.strip().split()
        if not parts:
            return CommandResponse(messages=[])
        command_name, *args = parts
        command = self._commands.get(command_name)
        if not command:
            logger.info("Unknown command: /%s", command_name)
            return CommandResponse(messages=[("system", f"Unknown command '/{command_name}'. Type /help for a list of commands.")])
        logger.debug("Dispatching command '/%s' with args %s", command_name, args)
        return command.handler(app, args)


class StubLLM:
    """Placeholder LLM adapter used until the real integration is wired in."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def respond(self, prompt: str) -> str:
        self.calls.append(prompt)
        return f"[stub] I heard: {prompt}"


class CLIApp:
    """Interactive shell orchestrating slash commands and chat flow."""

    def __init__(
        self,
        console: Console | None = None,
        history_path: Path | None = None,
        llm: StubLLM | None = None,
        config_context: ConfigContext | None = None,
        session_context: SessionContext | None = None,
        session_manager: SessionManager | None = None,
        wallet_manager: WalletManager | None = None,
        rpc_client: SolanaRPCClient | None = None,
    ) -> None:
        self.console = console or CLIApp._default_console()
        self.config_context = config_context
        self.session_manager = session_manager or SessionManager()
        self.session_context = session_context or self.session_manager.start()
        self.wallet_manager = wallet_manager or WalletManager()
        self.rpc_client = rpc_client
        self._master_passphrase = getattr(config_context, "passphrase", None)
        history_path = history_path or (
            self.session_manager.root / self.session_context.metadata.session_id / "history"
        )
        history_path.parent.mkdir(parents=True, exist_ok=True)
        self.session = PromptSession(history=FileHistory(str(history_path)))
        self.command_router = CommandRouter()
        self._register_builtin_commands()
        self._llm = llm or StubLLM()
        self._transcript = self.session_context.transcript
        initial_status = self.wallet_manager.status()
        initial_balance = self._fetch_balance(initial_status.public_key)
        self._update_wallet_metadata(initial_status, balance=initial_balance)
        logger.debug(
            "CLIApp initialized with history file %s for session %s",
            history_path,
            self.session_context.metadata.session_id,
        )

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    def _register_builtin_commands(self) -> None:
        self.command_router.register(
            SlashCommand("help", CLIApp._handle_help, "Show available commands"),
        )
        self.command_router.register(
            SlashCommand("quit", CLIApp._handle_quit, "Exit SolCoder"),
        )
        self.command_router.register(
            SlashCommand("settings", CLIApp._handle_settings, "View or update session settings"),
        )
        self.command_router.register(
            SlashCommand("wallet", CLIApp._handle_wallet, "Wallet management commands"),
        )
        self.command_router.register(
            SlashCommand("session", CLIApp._handle_session, "Session utilities"),
        )
        self.command_router.register(
            SlashCommand("env", CLIApp._handle_env, "Environment diagnostics"),
        )
        self.command_router.register(
            SlashCommand("template", CLIApp._handle_template, "Template scaffolding commands"),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(self) -> None:
        """Start the interactive REPL."""
        welcome = (
            "Welcome to SolCoder! Type plain text to chat or `/help` for commands."
            f"\n\nSession ID: {self.session_context.metadata.session_id}"
        )
        self.console.print(Panel(welcome, title="SolCoder"))
        with patch_stdout():
            while True:
                try:
                    user_input = self.session.prompt(self._prompt_message())
                except KeyboardInterrupt:
                    # User pressed Ctrl-C; ignore and prompt again.
                    logger.debug("KeyboardInterrupt detected; ignoring")
                    continue
                except EOFError:
                    self.console.print("Exiting SolCoder. Bye!")
                    break

                response = self.handle_line(user_input)
                for role, message in response.messages:
                    self._render_message(role, message)

                if not response.continue_loop:
                    break
                self._render_status()

        self._persist()

    def handle_line(self, raw_line: str) -> CommandResponse:
        """Handle a single line of user input (used by tests and run loop)."""
        raw_line = raw_line.rstrip()
        if not raw_line:
            return CommandResponse(messages=[])

        self._record("user", raw_line)
        self._render_message("user", raw_line)

        if raw_line.startswith("/"):
            logger.debug("Processing slash command: %s", raw_line)
            response = self.command_router.dispatch(self, raw_line[1:])
        else:
            logger.debug("Routing chat message to LLM stub")
            reply = self._llm.respond(raw_line)
            response = CommandResponse(messages=[("agent", reply)])

        for idx, (role, message) in enumerate(response.messages):
            tool_calls = response.tool_calls if idx == 0 else None
            self._record(role, message, tool_calls=tool_calls)
        self._persist()
        return response

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------
    @staticmethod
    def _handle_help(app: CLIApp, _args: list[str]) -> CommandResponse:
        lines = [f"/{cmd.name}	{cmd.help_text}" for cmd in app.command_router.available_commands()]
        content = "\n".join(sorted(lines))
        return CommandResponse(messages=[("system", content)])

    @staticmethod
    def _handle_quit(_app: CLIApp, _args: list[str]) -> CommandResponse:
        return CommandResponse(messages=[("system", "Exiting SolCoder. Bye!")], continue_loop=False)

    @staticmethod
    def _handle_settings(app: CLIApp, args: list[str]) -> CommandResponse:
        metadata = app.session_context.metadata
        if not args:
            project_display = metadata.active_project or "unknown"
            wallet_display = metadata.wallet_status or "---"
            spend_display = f"{metadata.spend_amount:.2f} SOL"
            lines = [
                f"Active project:\t{project_display}",
                f"Wallet:\t\t{wallet_display}",
                f"Session spend:\t{spend_display}",
            ]
            return CommandResponse(messages=[("system", "\n".join(lines))])

        subcommand, *values = args
        if subcommand.lower() == "wallet":
            if not values:
                return CommandResponse(
                    messages=[("system", "Usage: /settings wallet <label-or-address>")],
                )
            metadata.wallet_status = " ".join(values)
            return CommandResponse(messages=[("system", f"Wallet updated to '{metadata.wallet_status}'.")])

        if subcommand.lower() == "spend":
            if not values:
                return CommandResponse(messages=[("system", "Usage: /settings spend <amount-sol>")])
            try:
                amount = float(values[0])
            except ValueError:
                return CommandResponse(messages=[("system", "Spend amount must be a number (SOL).")])
            if amount < 0:
                return CommandResponse(messages=[("system", "Spend amount cannot be negative.")])
            metadata.spend_amount = amount
            return CommandResponse(messages=[("system", f"Session spend set to {metadata.spend_amount:.2f} SOL.")])

        return CommandResponse(
            messages=[
                (
                    "system",
                    "Unknown settings option. Use `/settings`, `/settings wallet <value>`, or `/settings spend <amount>`.",
                )
            ]
        )

    @staticmethod
    def _handle_session(app: CLIApp, args: list[str]) -> CommandResponse:
        if not args:
            return CommandResponse(messages=[("system", "Usage: /session export <id>")])

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

            content = CLIApp._format_export_text(export_data)
            return CommandResponse(messages=[("system", content)], tool_calls=tool_summary)

        return CommandResponse(messages=[("system", "Unknown session command. Try `/session export <id>`.")])

    @staticmethod
    def _handle_env(_app: CLIApp, args: list[str]) -> CommandResponse:
        if not args or args[0].lower() not in {"diag", "diagnostics"}:
            return CommandResponse(messages=[("system", "Usage: /env diag")])

        results = collect_environment_diagnostics()
        content = CLIApp._format_env_diag(results)
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

    @staticmethod
    def _handle_template(app: CLIApp, args: list[str]) -> CommandResponse:
        if not args:
            templates = ", ".join(available_templates()) or "(none)"
            return CommandResponse(
                messages=[
                    (
                        "system",
                        "Usage: /template <name> <destination> [--program <name>] [--author <pubkey>] [--program-id <id>] [--cluster <cluster>] [--force]\n"
                        f"Available templates: {templates}",
                    )
                ]
            )

        template_name = args[0].lower()
        if template_name not in available_templates():
            return CommandResponse(
                messages=[(
                    "system",
                    f"Unknown template '{template_name}'. Available: {', '.join(available_templates()) or '(none)'}"
                )]
            )

        defaults = app._default_template_metadata()
        options, error = _parse_template_tokens(template_name, args[1:], defaults)
        if error:
            return CommandResponse(messages=[("system", error)])
        assert options is not None
        try:
            output = render_template(options)
        except TemplateError as exc:
            return CommandResponse(messages=[("system", f"Template error: {exc}")])

        message = f"Template '{template_name}' rendered to {output}"
        tool_calls = [
            {
                "type": "command",
                "name": "/template",
                "status": "success",
                "summary": f"{template_name} → {output}",
            }
        ]
        return CommandResponse(messages=[("system", message)], tool_calls=tool_calls)

    @staticmethod
    def _handle_wallet(app: CLIApp, args: list[str]) -> CommandResponse:
        manager = app.wallet_manager
        if manager is None:
            return CommandResponse(messages=[("system", "Wallet manager unavailable in this session.")])

        if not args or args[0].lower() == "status":
            status = manager.status()
            balance = app._fetch_balance(status.public_key)
            app._update_wallet_metadata(status, balance=balance)
            if not status.exists:
                return CommandResponse(messages=[("system", "No wallet found. Run `/wallet create` to set one up.")])
            lock_state = "Unlocked" if status.is_unlocked else "Locked"
            balance_line = f"Balance: {balance:.3f} SOL" if balance is not None else "Balance: unavailable"
            message = "\n".join(
                [
                    f"Wallet {lock_state}",
                    f"Address: {status.public_key} ({status.masked_address})",
                    balance_line,
                ]
            )
            return CommandResponse(messages=[("system", message)])

        command, *rest = args
        command = command.lower()

        if command == "create":
            if manager.wallet_exists():
                return CommandResponse(
                    messages=[("system", "Wallet already exists. Delete the file manually or use `/wallet restore` with overwrite.")],
                )
            passphrase = app._prompt_secret("Create wallet passphrase", confirmation=True)
            status, mnemonic = manager.create_wallet(passphrase, force=True)
            balance = app._fetch_balance(status.public_key)
            app._update_wallet_metadata(status, balance=balance)
            balance_line = f" Balance {balance:.3f} SOL." if balance is not None else "."
            message = "\n".join(
                [
                    f"Created wallet {status.public_key} and unlocked it.{balance_line}",
                    "Recovery phrase (store securely):",
                    mnemonic,
                ]
            )
            return CommandResponse(messages=[("system", message)])

        if command == "restore":
            if not rest:
                secret = app._prompt_text("Paste secret key (JSON array, base58, or recovery phrase)")
            else:
                # allow `/wallet restore path/to/file`
                candidate = Path(rest[0]).expanduser()
                secret = candidate.read_text().strip() if candidate.exists() else " ".join(rest)
            passphrase = app._prompt_secret("Wallet passphrase", confirmation=True)
            try:
                status, mnemonic = manager.restore_wallet(secret, passphrase, overwrite=True)
            except WalletError as exc:
                app.console.print(f"[red]{exc}")
                return CommandResponse(messages=[("system", str(exc))])
            try:
                status = manager.unlock_wallet(passphrase)
            except WalletError:
                status = manager.status()
            balance = app._fetch_balance(status.public_key)
            app._update_wallet_metadata(status, balance=balance)
            restored_lines = [f"Wallet restored for {status.public_key}."]
            if status.is_unlocked:
                restored_lines.append("Wallet unlocked.")
            else:
                restored_lines.append("Use `/wallet unlock` to access.")
            if mnemonic:
                restored_lines.append("Recovery phrase saved from the provided words.")
            return CommandResponse(messages=[("system", " ".join(restored_lines))])

        if command == "unlock":
            initial_pass = app._prompt_secret("Wallet passphrase")
            try:
                status = manager.unlock_wallet(initial_pass)
            except WalletError:
                app.console.print("[yellow]Stored passphrase failed; please re-enter.[/yellow]")
                retry_pass = app._prompt_secret("Wallet passphrase", allow_master=False)
                try:
                    status = manager.unlock_wallet(retry_pass)
                except WalletError as exc:
                    return CommandResponse(messages=[("system", str(exc))])
            balance = app._fetch_balance(status.public_key)
            app._update_wallet_metadata(status, balance=balance)
            balance_line = f" Current balance {balance:.3f} SOL." if balance is not None else "."
            return CommandResponse(messages=[("system", f"Wallet unlocked for {status.public_key}.{balance_line}")])

        if command == "lock":
            status = manager.lock_wallet()
            app._update_wallet_metadata(status, balance=None)
            return CommandResponse(messages=[("system", "Wallet locked.")])

        if command == "export":
            passphrase = app._prompt_secret("Wallet passphrase")
            try:
                secret = manager.export_wallet(passphrase)
            except WalletError as exc:
                return CommandResponse(messages=[("system", str(exc))])
            if rest:
                target_path = Path(rest[0]).expanduser()
                app._write_secret_file(target_path, secret)
                return CommandResponse(messages=[("system", f"Exported secret to {target_path}")])
            return CommandResponse(messages=[("system", f"Exported secret: {secret}")])

        if command in {"phrase", "mnemonic"}:
            passphrase = app._prompt_secret("Wallet passphrase", allow_master=False)
            try:
                mnemonic = manager.get_mnemonic(passphrase)
            except WalletError as exc:
                return CommandResponse(messages=[("system", str(exc))])
            return CommandResponse(messages=[("system", f"Recovery phrase:\n{mnemonic}")])

        return CommandResponse(
            messages=[
                (
                    "system",
                    "Unknown wallet command. Available: `/wallet status`, `/wallet create`, `/wallet restore`, `/wallet unlock`, `/wallet lock`, `/wallet export`, `/wallet phrase`.",
                )
            ]
        )

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------
    def _render_message(self, role: str, message: str) -> None:
        if role == "user":
            panel_title = "You"
            style = "bold cyan"
        elif role == "agent":
            panel_title = "SolCoder"
            style = "green"
        else:
            panel_title = role.title()
            style = "magenta"
        text = Text(message, style=style)
        self.console.print(Panel(text, title=panel_title, expand=False))

    def _render_status(self) -> None:
        session_id = self.session_context.metadata.session_id
        metadata = self.session_context.metadata
        project_display = metadata.active_project or "unknown"
        wallet_display = metadata.wallet_status or "---"
        balance_display = (
            f"{metadata.wallet_balance:.3f} SOL" if metadata.wallet_balance is not None else "--"
        )
        spend_display = f"{metadata.spend_amount:.2f} SOL"
        status = Text(
            f"Session: {session_id} • Project: {project_display} • Wallet: {wallet_display} • Balance: {balance_display} • Spend: {spend_display}",
            style="dim",
        )
        self.console.print(status)

    def _prompt_message(self) -> str:
        return "❯ "

    def _record(self, role: str, message: str, *, tool_calls: list[dict[str, Any]] | None = None) -> None:
        entry: dict[str, Any] = {
            "role": role,
            "message": message,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        if tool_calls:
            entry["tool_calls"] = tool_calls
        self.session_context.transcript.append(entry)
        if len(self.session_context.transcript) > TRANSCRIPT_LIMIT:
            del self.session_context.transcript[:-TRANSCRIPT_LIMIT]

    def _default_template_metadata(self) -> dict[str, str]:
        program_name = "counter"
        author_pubkey = "CHANGEME"
        if self.wallet_manager is not None:
            try:
                status = self.wallet_manager.status()
                if status.public_key:
                    author_pubkey = status.public_key
            except WalletError:
                pass
        return {"program_name": program_name, "author_pubkey": author_pubkey}

    def _prompt_secret(self, message: str, *, confirmation: bool = False, allow_master: bool = True) -> str:
        if allow_master and self._master_passphrase is not None:
            return self._master_passphrase
        while True:
            value = self.session.prompt(f"{message}: ", is_password=True)
            if not confirmation:
                return value
            confirm = self.session.prompt("Confirm passphrase: ", is_password=True)
            if value == confirm:
                return value
            self.console.print("[red]Passphrases do not match. Try again.[/red]")

    def _prompt_text(self, message: str) -> str:
        return self.session.prompt(f"{message}: ")

    def _update_wallet_metadata(self, status: WalletStatus, *, balance: float | None) -> None:
        metadata = self.session_context.metadata
        if not status.exists:
            metadata.wallet_status = "missing"
            metadata.wallet_balance = None
            return
        lock_state = "Unlocked" if status.is_unlocked else "Locked"
        address = status.masked_address if status.public_key else "---"
        metadata.wallet_status = f"{lock_state} ({address})"
        metadata.wallet_balance = balance

    def _fetch_balance(self, public_key: str | None) -> float | None:
        if not public_key or self.rpc_client is None:
            return None
        try:
            return self.rpc_client.get_balance(public_key)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Unable to fetch balance for %s: %s", public_key, exc)
            return None

    @staticmethod
    def _format_export_text(export_data: dict[str, object]) -> str:
        metadata = export_data.get("metadata", {})
        transcript = export_data.get("transcript", [])
        lines = ["Session Export", "=============="]
        if isinstance(metadata, dict):
            for key in (
                "session_id",
                "created_at",
                "updated_at",
                "active_project",
                "wallet_status",
                "wallet_balance",
                "spend_amount",
            ):
                if key in metadata and metadata[key] is not None:
                    lines.append(f"{key.replace('_', ' ').title()}: {metadata[key]}")
        lines.append("")
        lines.append("Transcript (most recent first):")
        if isinstance(transcript, list) and transcript:
            for entry in transcript:
                if isinstance(entry, dict):
                    role = entry.get("role", "?")
                    message = entry.get("message", "")
                    timestamp = entry.get("timestamp")
                    prefix = f"{timestamp} " if timestamp else ""
                    lines.append(f"{prefix}[{role}] {message}")
                    tool_calls = entry.get("tool_calls")
                    if isinstance(tool_calls, list):
                        for tool_call in tool_calls:
                            if not isinstance(tool_call, dict):
                                continue
                            call_type = tool_call.get("type", "tool")
                            name = tool_call.get("name") or ""
                            status = tool_call.get("status") or ""
                            summary = tool_call.get("summary") or ""
                            details = " • ".join(
                                part for part in (name, status, summary) if part
                            )
                            lines.append(f"    ↳ {call_type}: {details}")
                else:
                    lines.append(str(entry))
        else:
            lines.append("(no transcript available)")
        return "\n".join(lines)

    @staticmethod
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

    def _write_secret_file(self, target: Path, secret: str) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(secret)
        try:
            os.chmod(target, 0o600)
        except PermissionError:
            pass

    def _persist(self) -> None:
        if self.session_manager is not None:
            self.session_manager.save(self.session_context)

    @staticmethod
    def _default_console() -> Console:
        force_style = os.environ.get("SOLCODER_FORCE_COLOR")
        no_color = os.environ.get("SOLCODER_NO_COLOR") is not None or os.environ.get("NO_COLOR") is not None
        if force_style:
            return Console(force_terminal=True)
        if no_color or not sys.stdout.isatty():
            return Console(no_color=True, force_terminal=False, color_system=None)
        return Console()
