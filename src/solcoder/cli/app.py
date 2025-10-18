
"""Interactive CLI shell for SolCoder."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.history import FileHistory
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from solcoder.core.context import ContextManager
from solcoder.cli.branding import SOLCODER_THEME, render_banner, themed_console
from solcoder.cli.commands import register_builtin_commands
from solcoder.cli.stub_llm import StubLLM
from solcoder.cli.status_bar import StatusBar
from solcoder.cli.types import CommandResponse, CommandRouter, LLMBackend
from solcoder.cli.wallet_prompts import prompt_secret, prompt_text
from solcoder.core import ConfigContext, ConfigManager
from solcoder.core.agent_loop import (
    DEFAULT_AGENT_MAX_ITERATIONS,
    AgentLoopContext,
    run_agent_loop,
)
from solcoder.core.todo import TodoManager
from solcoder.core.llm import LLMError
from solcoder.core.logs import LogBuffer, LogEntry
from solcoder.core.tool_registry import (
    ToolRegistry,
    ToolkitAlreadyRegisteredError,
    build_default_registry,
)
from solcoder.core.tools.todo import todo_toolkit
from solcoder.core.wallet_state import fetch_balance, update_wallet_metadata
from solcoder.session import SessionContext, SessionManager
from solcoder.solana import SolanaRPCClient, WalletError, WalletManager, WalletStatus

logger = logging.getLogger(__name__)


DEFAULT_HISTORY_PATH = Path(os.environ.get("SOLCODER_HOME", Path.home() / ".solcoder")) / "history"
DEFAULT_AGENT_MODE = os.environ.get("SOLCODER_AGENT_MODE", "assistive")


class _StatusContext:
    def __init__(self, app: "CLIApp", initial: Any) -> None:
        self._app = app
        self._last: Any = None
        if initial:
            self.update(initial)

    def __enter__(self) -> "_StatusContext":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - nothing to clean up
        return None

    def update(self, message: Any) -> None:
        if not message or message == self._last:
            return
        self._last = message
        self._app._print_rich(message)


class _ConsoleProxy:
    """Proxy that routes print() through CLIApp-aware renderer while delegating everything else."""

    def __init__(self, app: "CLIApp", console: Console) -> None:
        self._app = app
        self._console = console

    def print(self, *objects: Any, **kwargs: Any) -> None:
        self._app._print_rich(*objects, **kwargs)

    def status(self, status: Any, *args: Any, **kwargs: Any) -> _StatusContext:
        return _StatusContext(self._app, status)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._console, name)

class CLIApp:
    """Interactive shell orchestrating slash commands and chat flow."""

    def __init__(
        self,
        console: Console | None = None,
        history_path: Path | None = None,
        llm: LLMBackend | None = None,
        config_context: ConfigContext | None = None,
        config_manager: ConfigManager | None = None,
        session_context: SessionContext | None = None,
        session_manager: SessionManager | None = None,
        wallet_manager: WalletManager | None = None,
        rpc_client: SolanaRPCClient | None = None,
        tool_registry: ToolRegistry | None = None,
    ) -> None:
        base_console = console or CLIApp._default_console()
        if console is not None and not getattr(base_console, "_solcoder_theme_applied", False):
            base_console.push_theme(SOLCODER_THEME)
            setattr(base_console, "_solcoder_theme_applied", True)
        self._console = base_console
        self._pt_console = themed_console(force_terminal=True, color_system="standard")
        setattr(self._pt_console, "_solcoder_theme_applied", True)
        self.console = _ConsoleProxy(self, base_console)
        self._color_enabled = bool(self._console.is_terminal and not getattr(self._console, "no_color", False))
        self.config_context = config_context
        self.config_manager = config_manager
        self.session_manager = session_manager or SessionManager()
        self.session_context = session_context or self.session_manager.start()
        self.wallet_manager = wallet_manager or WalletManager()
        self.rpc_client = rpc_client
        self._master_passphrase = getattr(config_context, "passphrase", None)
        history_path = history_path or (
            self.session_manager.root / self.session_context.metadata.session_id / "history"
        )
        history_path.parent.mkdir(parents=True, exist_ok=True)
        self.command_router = CommandRouter()
        self.todo_manager = TodoManager()
        self._llm: LLMBackend = llm or StubLLM()
        self.context_manager = ContextManager(
            self.session_context,
            llm=self._llm,
            config_context=self.config_context,
        )
        self.log_buffer = LogBuffer()
        self._agent_mode = DEFAULT_AGENT_MODE
        self.status_bar = StatusBar(
            console=self._console,
            context_manager=self.context_manager,
            log_buffer=self.log_buffer,
            workspace_resolver=self._resolve_workspace_path,
            agent_mode_resolver=self._resolve_agent_mode,
        )
        bottom_toolbar = self.status_bar.toolbar if self.status_bar.supports_toolbar else None
        self.session = PromptSession(
            history=FileHistory(str(history_path)),
            bottom_toolbar=bottom_toolbar,
        )
        self.log_buffer.subscribe(lambda _entry: self._refresh_status_bar())
        register_builtin_commands(self, self.command_router)
        self._load_todo_state()
        self.tool_registry = tool_registry or build_default_registry()
        try:
            self.tool_registry.add_toolkit(todo_toolkit(self.todo_manager))
        except ToolkitAlreadyRegisteredError:
            logger.debug("Todo toolkit already registered; skipping duplicate add.")
        initial_status = self.wallet_manager.status()
        initial_balance = fetch_balance(self.rpc_client, initial_status.public_key)
        update_wallet_metadata(self.session_context.metadata, initial_status, balance=initial_balance)
        network_name = (
            self.config_context.config.network
            if self.config_context is not None and hasattr(self.config_context, "config")
            else "unknown"
        )
        self.log_event(
            "system",
            f"Session {self.session_context.metadata.session_id} initialised (network={network_name})",
        )
        if initial_status.exists:
            self.log_event("wallet", f"Wallet detected {initial_status.masked_address}")
        else:
            self.log_event("wallet", "No wallet configured", severity="warning")
        logger.debug(
            "CLIApp initialized with history file %s for session %s",
            history_path,
            self.session_context.metadata.session_id,
        )

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(self) -> None:
        """Start the interactive REPL."""
        self._render_banner()
        session_id = self.session_context.metadata.session_id
        metadata = self.session_context.metadata
        lines = [
            "[#14F195]🚀  Build Solana dApps at Light Speed[/]",
            "[#94A3B8]Ask for builds, audits, or deploys — every request becomes a transparent plan with on-chain actions.[/]",
            "",
            f"[#38BDF8]Session[/]: {session_id}",
        ]
        wallet_status = metadata.wallet_status or ""
        if wallet_status:
            if "Unlocked" in wallet_status:
                lines.append("[#14F195]🔓 Wallet unlocked with your SolCoder passphrase.[/]")
            elif "Locked" in wallet_status:
                lines.append("[#F472B6]🔒 Wallet locked. Use `/wallet unlock` to access.[/]")
        balance = metadata.wallet_balance
        if balance is not None:
            lines.append(f"[#14F195]💰 Balance[/]: [#E6FFFA]{balance:.3f} SOL")
        welcome_text = Text.from_markup("\n".join(lines))
        self.console.print(
            Panel(
                welcome_text,
                title="[bold #8264FF]SolCoder • The Solana AI Coding Agent[/]",
                border_style="#14F195",
                padding=(1, 2),
                style="on #0E0E0E",
            )
        )
        self.console.print()
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
                    if response.rendered_roles and role in response.rendered_roles:
                        continue
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

        self.context_manager.record("user", raw_line)
        self._render_message("user", raw_line)
        self.console.print()

        if raw_line.startswith("/"):
            logger.debug("Processing slash command: %s", raw_line)
            response = self.command_router.dispatch(self, raw_line[1:])
        else:
            logger.debug("Routing chat message to LLM backend")
            response = self._chat_with_llm(raw_line)

        for idx, (role, message) in enumerate(response.messages):
            tool_calls = response.tool_calls if idx == 0 else None
            self.context_manager.record(role, message, tool_calls=tool_calls)
        self.context_manager.compact_history_if_needed()
        self._persist()
        self._refresh_status_bar()
        return response

    def log_event(self, category: str, message: str, *, severity: str = "info") -> LogEntry:
        """Record an operational event in the shared log buffer."""
        return self.log_buffer.record(category, message, severity=severity)

    def _max_agent_iterations(self) -> int:
        return DEFAULT_AGENT_MAX_ITERATIONS

    def force_compact_history(self) -> str:
        """Force transcript compaction using the active history strategy."""
        return self.context_manager.force_compact_history()

    def _chat_with_llm(self, prompt: str) -> CommandResponse:
        context = AgentLoopContext(
            prompt=prompt,
            history=self.context_manager.conversation_history(),
            llm=self._llm,
            tool_registry=self.tool_registry,
            console=self.console,
            config_context=self.config_context,
            session_metadata=self.session_context.metadata,
            render_message=self._render_message,
            todo_manager=self.todo_manager,
            initial_todo_message=self._todo_history_snapshot(),
            max_iterations=self._max_agent_iterations(),
        )
        try:
            return run_agent_loop(context)
        except LLMError as exc:
            logger.error("LLM error: %s", exc)
            return CommandResponse(messages=[("system", f"LLM error: {exc}")])

    def _update_llm_settings(self, *, model: str | None = None, reasoning: str | None = None) -> None:
        if self.config_context is None:
            return
        if model:
            self.config_context.config.llm_model = model
        if reasoning:
            self.config_context.config.llm_reasoning_effort = reasoning
        update_kwargs: dict[str, str] = {}
        if model:
            update_kwargs["model"] = model
        if reasoning:
            update_kwargs["reasoning_effort"] = reasoning
        if update_kwargs and hasattr(self._llm, "update_settings"):
            try:
                self._llm.update_settings(**update_kwargs)  # type: ignore[misc]
            except Exception:  # noqa: BLE001
                logger.warning("LLM backend does not support runtime setting updates.")
        if self.config_manager is not None:
            try:
                self.config_manager.update_llm_preferences(
                    llm_model=model if model else None,
                    llm_reasoning_effort=reasoning if reasoning else None,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to persist LLM settings: %s", exc)

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------
    def _render_message(self, role: str, message: str) -> None:
        if role == "user":
            panel_title = "[#A855F7]You[/]"
            border_style = "solcoder.user.border"
            text_style = "solcoder.user.text"
        elif role == "agent":
            panel_title = "[#14F195]SolCoder[/]"
            border_style = "solcoder.agent.border"
            text_style = "solcoder.agent.text"
        else:
            panel_title = f"[#F472B6]{role.title()}[/]"
            border_style = "solcoder.system.border"
            text_style = "solcoder.system.text"
        text = Text(message, style=text_style)
        panel = Panel(
            text,
            title=panel_title,
            border_style=border_style,
            expand=False,
            padding=(1, 2),
            style="on #0E0E0E",
        )
        self.console.print(panel)

    def _render_status(self) -> None:
        if self.status_bar.supports_toolbar:
            self.console.print()
            self._refresh_status_bar()
            return
        self.console.print()
        self.console.print(self.status_bar.render_text())
        self.console.print()

    def _refresh_status_bar(self) -> None:
        if not self.status_bar.supports_toolbar:
            return
        try:
            application = self.session.app
        except Exception:  # pragma: no cover - defensive guard for teardown races
            return
        if getattr(application, "is_running", False):
            application.invalidate()

    def _render_banner(self) -> None:
        render_banner(self.console, animate=self._color_enabled)

    def _prompt_message(self) -> str:
        if not self._color_enabled:
            return "➤ "
        return ANSI("\x1b[38;2;168;85;247m➤\x1b[0m ")

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
        return prompt_secret(
            self.session,
            self.console,
            message,
            master_passphrase=self._master_passphrase,
            confirmation=confirmation,
            allow_master=allow_master,
        )

    def _prompt_text(self, message: str) -> str:
        return prompt_text(self.session, message)

    def _update_wallet_metadata(self, status: WalletStatus, *, balance: float | None) -> None:
        update_wallet_metadata(self.session_context.metadata, status, balance=balance)
        self._refresh_status_bar()

    def _fetch_balance(self, public_key: str | None) -> float | None:
        return fetch_balance(self.rpc_client, public_key)

    def _todo_history_snapshot(self) -> str | None:
        if not self.todo_manager or not self.todo_manager.tasks():
            return None
        todo_render = self.todo_manager.render()
        guidance = (
            "Update the TODO list with todo_* tools or the /todo command as work progresses. "
            "Only add new steps that are not already present."
        )
        return f"{todo_render}\n{guidance}"

    def _resolve_workspace_path(self) -> str:
        metadata = self.session_context.metadata
        if metadata.active_project:
            candidate = Path(metadata.active_project).expanduser()
        else:
            candidate = Path.cwd()
        try:
            candidate = candidate.resolve()
        except Exception:
            candidate = candidate.expanduser()
        try:
            home = Path.home()
            return f"~/{candidate.relative_to(home)}" if candidate.is_relative_to(home) else str(candidate)
        except ValueError:
            return str(candidate)

    def _resolve_agent_mode(self) -> str:
        return self._agent_mode

    def set_agent_mode(self, mode: str) -> None:
        self._agent_mode = mode
        self._refresh_status_bar()

    def _print_rich(self, *objects: Any, **kwargs: Any) -> None:
        app = getattr(self.session, "app", None)
        is_running = bool(getattr(app, "is_running", False)) if app is not None else False
        if is_running:
            with self._pt_console.capture() as capture:
                self._pt_console.print(*objects, **kwargs)
            rendered = capture.get()
            if rendered:
                app.print_text(ANSI(rendered), refresh=True)
        else:
            self._console.print(*objects, **kwargs)

    def _load_todo_state(self) -> None:
        if self.session_manager is None:
            return
        state = self.session_manager.load_todo(self.session_context.metadata.session_id)
        if not state:
            return
        tasks = state.get("tasks") or []
        unfinished = [task for task in tasks if isinstance(task, dict) and task.get("status") != "done"]
        if unfinished and not self._should_import_todo(len(unfinished)):
            logger.debug("Skipping import of %s unfinished TODO items", len(unfinished))
            return
        try:
            self.todo_manager.load_state(state)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load TODO state: %s", exc)

    def _should_import_todo(self, count: int) -> bool:
        if count <= 0:
            return True
        try:
            is_tty = sys.stdin.isatty()
        except Exception:  # noqa: BLE001
            is_tty = False
        if not is_tty:
            return True
        try:
            response = self.console.input(
                f"Import {count} open task{'s' if count != 1 else ''}? (y/N) "
            )
        except (EOFError, KeyboardInterrupt):
            return False
        return response.strip().lower() in {"y", "yes"}

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
            try:
                state = self.todo_manager.dump_state()
            except Exception:  # noqa: BLE001
                state = {"tasks": [], "revision": 0, "acknowledged": True}
            self.session_manager.save_todo(self.session_context.metadata.session_id, state)

    @staticmethod
    def _default_console() -> Console:
        force_style = os.environ.get("SOLCODER_FORCE_COLOR")
        no_color = os.environ.get("SOLCODER_NO_COLOR") is not None or os.environ.get("NO_COLOR") is not None
        if force_style:
            console = themed_console(force_terminal=True)
            setattr(console, "_solcoder_theme_applied", True)
            return console
        if no_color or not sys.stdout.isatty():
            console = themed_console(no_color=True, force_terminal=False, color_system=None)
            setattr(console, "_solcoder_theme_applied", True)
            return console
        console = themed_console()
        setattr(console, "_solcoder_theme_applied", True)
        return console
