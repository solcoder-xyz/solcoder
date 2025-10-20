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
from rich import box
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from solcoder.cli.branding import (
    SOLCODER_THEME,
    create_chat_panel,
    create_todo_panel,
    render_banner,
    themed_console,
)
from solcoder.cli.commands import register_builtin_commands
from solcoder.cli.status_bar import StatusBar
from solcoder.cli.stub_llm import StubLLM
from solcoder.cli.types import CommandResponse, CommandRouter, LLMBackend
from solcoder.cli.wallet_prompts import prompt_secret, prompt_text
from solcoder.core import (
    ConfigContext,
    ConfigManager,
    DiagnosticResult,
    collect_environment_diagnostics,
)
from solcoder.core.agent_loop import (
    DEFAULT_AGENT_MAX_ITERATIONS,
    AgentLoopContext,
    run_agent_loop,
)
from solcoder.core.context import ContextManager
from solcoder.core.installers import (
    InstallerError,
    detect_missing_tools,
    install_tool,
    installer_display_name,
    installer_key_for_diagnostic,
    required_tools,
)
from solcoder.core.llm import LLMError
from solcoder.core.logs import LogBuffer, LogEntry
from solcoder.core.todo import TodoManager
from solcoder.core.tool_registry import (
    ToolkitAlreadyRegisteredError,
    ToolRegistry,
    build_default_registry,
)
from solcoder.core.tools.todo import todo_toolkit
from solcoder.core.wallet_state import fetch_balance, update_wallet_metadata
from solcoder.session import SessionContext, SessionManager
from solcoder.solana import SolanaRPCClient, WalletError, WalletManager, WalletStatus

logger = logging.getLogger(__name__)


DEFAULT_HISTORY_PATH = (
    Path(os.environ.get("SOLCODER_HOME", Path.home() / ".solcoder")) / "history"
)
DEFAULT_AGENT_MODE = os.environ.get("SOLCODER_AGENT_MODE", "assistive")


class _StatusContext:
    def __init__(self, app: CLIApp, initial: Any, spinner: str = "dots") -> None:
        self._app = app
        self._spinner_name = spinner
        self._last: Any = None
        self._live: Live | None = None
        self._current_message: Any = initial

        if initial:
            self._start_spinner(initial)

    def __enter__(self) -> _StatusContext:
        return self

    def __exit__(
        self, exc_type, exc, tb
    ) -> None:
        if self._live:
            self._live.stop()
            self._live = None

    def update(self, message: Any) -> None:
        if not message or message == self._last:
            return
        self._last = message
        self._current_message = message

        if self._live:
            # Update the spinner with new message
            spinner_text = Text()
            spinner_text.append("⚡ ", style="bold #14F195")
            if isinstance(message, Text):
                spinner_text.append_text(message)
            else:
                spinner_text.append(str(message), style="solcoder.status.text")

            spinner = Spinner(self._spinner_name, text=spinner_text, style="solcoder.status.spinner")
            self._live.update(spinner)
        else:
            self._start_spinner(message)

    def _start_spinner(self, message: Any) -> None:
        """Start the live spinner display."""
        spinner_text = Text()
        spinner_text.append("⚡ ", style="bold #14F195")
        if isinstance(message, Text):
            spinner_text.append_text(message)
        else:
            spinner_text.append(str(message), style="solcoder.status.text")

        spinner = Spinner(self._spinner_name, text=spinner_text, style="solcoder.status.spinner")

        # Use the app's console to create the Live display
        app = getattr(self._app.session, "app", None)
        is_running = (
            bool(getattr(app, "is_running", False)) if app is not None else False
        )

        if is_running:
            # When inside patch_stdout(), render to sys.__stdout__
            from io import StringIO

            # We can't use Live with StringIO easily, so just print a simple status
            output = f"⚡ {str(message)}\n"
            sys.__stdout__.write(output)
            sys.__stdout__.flush()
        else:
            # Outside patch_stdout(), use normal Rich Live spinner
            self._live = Live(spinner, console=self._app._console, refresh_per_second=10)
            self._live.start()


class _ConsoleProxy:
    """Proxy that routes print() through CLIApp-aware renderer while delegating everything else."""

    def __init__(self, app: CLIApp, console: Console) -> None:
        self._app = app
        self._console = console

    def print(self, *objects: Any, **kwargs: Any) -> None:
        self._app._print_rich(*objects, **kwargs)

    def status(self, status: Any, *args: Any, **kwargs: Any) -> _StatusContext:
        spinner = kwargs.get("spinner", "dots")
        return _StatusContext(self._app, status, spinner=spinner)

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
        print_raw_llm: bool | None = None,
    ) -> None:
        base_console = console or CLIApp._default_console()
        if console is not None and not getattr(
            base_console, "_solcoder_theme_applied", False
        ):
            base_console.push_theme(SOLCODER_THEME)
            base_console._solcoder_theme_applied = True
        self._console = base_console
        self.console = _ConsoleProxy(self, base_console)
        self._color_enabled = bool(
            self._console.is_terminal and not getattr(self._console, "no_color", False)
        )
        self.config_context = config_context
        self.config_manager = config_manager
        self.session_manager = session_manager or SessionManager()
        self.session_context = session_context or self.session_manager.start()
        self.wallet_manager = wallet_manager or WalletManager()
        self.rpc_client = rpc_client
        self._master_passphrase = getattr(config_context, "passphrase", None)
        history_path = history_path or (
            self.session_manager.root
            / self.session_context.metadata.session_id
            / "history"
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
        env_flag = os.environ.get("SOLCODER_PRINT_RAW_LLM")
        if print_raw_llm is None:
            print_raw_llm = (
                env_flag is not None
                and env_flag.strip().lower() not in {"", "0", "false", "no"}
            )
        self._print_raw_llm = bool(print_raw_llm)
        self._agent_mode = DEFAULT_AGENT_MODE
        self.status_bar = StatusBar(
            console=self._console,
            context_manager=self.context_manager,
            log_buffer=self.log_buffer,
            workspace_resolver=self._resolve_workspace_path,
            agent_mode_resolver=self._resolve_agent_mode,
        )
        bottom_toolbar = (
            self.status_bar.toolbar if self.status_bar.supports_toolbar else None
        )
        self.session = PromptSession(
            history=FileHistory(str(history_path)),
            bottom_toolbar=bottom_toolbar,
        )
        self.log_buffer.subscribe(lambda _entry: self._refresh_status_bar())
        register_builtin_commands(self, self.command_router)
        self._load_todo_state()
        self.tool_registry = tool_registry or build_default_registry()
        self.tool_registry.add_toolkit(
            todo_toolkit(self.todo_manager), overwrite=True
        )
        initial_status = self.wallet_manager.status()
        initial_balance = fetch_balance(self.rpc_client, initial_status.public_key)
        update_wallet_metadata(
            self.session_context.metadata, initial_status, balance=initial_balance
        )
        self._awaiting_ctrl_c_confirm = False
        network_name = (
            self.config_context.config.network
            if self.config_context is not None
            and hasattr(self.config_context, "config")
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
        should_clear = self._handle_environment_bootstrap()
        if should_clear:
            self.console.clear()
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
                lines.append(
                    "[#14F195]🔓 Wallet unlocked with your SolCoder passphrase.[/]"
                )
            elif "Locked" in wallet_status:
                lines.append(
                    "[#F472B6]🔒 Wallet locked. Use `/wallet unlock` to access.[/]"
                )
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
        with patch_stdout(raw=True):
            while True:
                try:
                    user_input = self.session.prompt(self._prompt_message())
                    self._awaiting_ctrl_c_confirm = False
                except KeyboardInterrupt:
                    if self._awaiting_ctrl_c_confirm:
                        self.console.print("Exiting SolCoder. Bye!")
                        break
                    self._awaiting_ctrl_c_confirm = True
                    logger.debug("KeyboardInterrupt detected; awaiting confirmation")
                    self.console.print("Press Ctrl-C again to exit SolCoder.")
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
        # Don't render user message - it's already visible in the prompt

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

    def _handle_environment_bootstrap(self) -> bool:
        try:
            hide_status = getattr(self.status_bar, "supports_toolbar", False)
            if hide_status and hasattr(self.status_bar, "set_toolbar_support"):
                self.status_bar.set_toolbar_support(False)

            with self.console.status("Running environment diagnostics...", spinner="dots"):
                diagnostics = collect_environment_diagnostics()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Environment diagnostics failed during bootstrap: %s", exc)
            return False
        finally:
            if hide_status and hasattr(self.status_bar, "set_toolbar_support"):
                self.status_bar.set_toolbar_support(True)

        required_set = set(required_tools())

        def render_diagnostics_table(results: list[DiagnosticResult]) -> None:
            table = Table(
                title=None,
                box=box.SIMPLE_HEAD,
                show_edge=False,
                pad_edge=False,
                header_style="bold #38BDF8",
            )
            table.add_column("Tool", style="#38BDF8", no_wrap=True)
            table.add_column("Status", style="#14F195", no_wrap=True)
            table.add_column("Detail", style="#94A3B8")

            status_styles = {
                "ok": "#14F195",
                "warn": "#FACC15",
                "missing": "#F97316",
                "error": "#FB7185",
            }

            for item in results:
                detail = ""
                if item.found and item.version:
                    detail = item.version
                elif item.found:
                    detail = "Detected (version unavailable)"
                elif item.remediation:
                    detail = item.remediation
                else:
                    detail = "Not found on PATH"

                status_label = item.status.lower()
                style = status_styles.get(status_label, "#38BDF8")
                display_status = status_label.upper()
                table.add_row(item.name, f"[{style}]{display_status}[/{style}]", detail)

            panel = Panel(
                table,
                title="[bold #38BDF8]Environment Diagnostics[/]",
                border_style="#38BDF8",
                padding=(1, 2),
            )
            self.console.print(panel)

        def manual_missing(results: list[DiagnosticResult]) -> set[str]:
            manual_names = {
                item.name
                for item in results
                if item.name in {"Python 3", "pip"} and not item.found
            }
            return manual_names

        def show_manual_notice(
            current: set[str], previous: set[str]
        ) -> set[str]:
            if not current or current == previous:
                return previous
            names = ", ".join(sorted(current))
            self.console.print(
                f"[#F97316]Manual setup required for: {names}. "
                "Follow the remediation guidance above to install them.[/]"
            )
            return current

        def parse_install_location(details: str | None) -> str | None:
            if not details or "Detected at" not in details:
                return None
            fragment = details.split("Detected at", 1)[1]
            fragment = fragment.split(" but", 1)[0]
            fragment = fragment.split(",", 1)[0]
            location = fragment.strip()
            return location or None

        def shell_hint_for(path_str: str) -> tuple[str, str]:
            lowered = path_str.lower()
            if ".cargo/bin" in lowered:
                return (
                    '. "$HOME/.cargo/env"',
                    "Add `source \"$HOME/.cargo/env\"` to your ~/.zshrc (or ~/.bashrc) "
                    "and restart the terminal.",
                )
            if "solana" in lowered:
                parent = Path(path_str).expanduser().parent
                export = f'export PATH="{parent}:$PATH"'
                return (
                    export,
                    f"Add `{export}` to your shell config (e.g., ~/.zshrc) and reload it.",
                )
            if ".fnm" in lowered or "corepack" in lowered:
                parent = Path(path_str).expanduser().parent
                export = f'export PATH="{parent}:$PATH"'
                return (
                    export,
                    f"Add `{export}` to ~/.zshrc and run `corepack enable` if not already.",
                )
            parent = Path(path_str).expanduser().parent
            export = f'export PATH="{parent}:$PATH"'
            return (
                export,
                f"Add `{export}` to your shell config file and restart the terminal.",
            )

        def run_installer(tool_key: str) -> bool:
            name = installer_display_name(tool_key)
            self.console.print(f"[#38BDF8]Installing {name}...[/]")
            try:
                result = install_tool(tool_key, console=self.console)
            except InstallerError as exc:  # pragma: no cover - interactive failure
                self.console.print(f"[#F97316]Failed to install {name}: {exc}[/]")
                self.log_event("install", f"{name} install error: {exc}", severity="error")
                return False

            if result.success and result.verification_passed:
                self.console.print(f"[#14F195]Installed {name} successfully.[/]")
                self.log_event("install", f"{name} installed", severity="info")
                return True

            error_detail = result.error or "verification failed"
            self.console.print(f"[#F97316]{name} installation incomplete: {error_detail}[/]")
            self.log_event(
                "install", f"{name} install incomplete: {error_detail}", severity="warning"
            )
            return False

        def prompt_for_tool(tool_key: str) -> str:
            name = installer_display_name(tool_key)
            is_anchor = tool_key == "anchor"
            required = tool_key in required_set
            default_yes = required or is_anchor
            options = "Y/n/skip" if default_yes else "y/N/skip"
            prompt_message = f"{name} is missing. Install now? ({options})"

            while True:
                answer = prompt_text(self.session, prompt_message).strip().lower()
                if not answer:
                    answer = "y" if default_yes else "n"
                if answer in {"y", "yes"}:
                    return "install"
                if answer in {"skip", "s"}:
                    if is_anchor:
                        confirm = prompt_text(
                            self.session,
                            (
                                "Anchor powers Solana deploy flows. "
                                "Type 'skip' again to continue without installing."
                            ),
                        ).strip().lower()
                        if confirm != "skip":
                            self.console.print(
                                "[#FACC15]Anchor skip not confirmed; will keep prompting.[/]"
                            )
                            continue
                    return "skip"
                if answer in {"n", "no"}:
                    if is_anchor:
                        self.console.print(
                            "[#FACC15]Anchor is required for deploy workflows. "
                            "Choose 'skip' if you must proceed without it.[/]"
                        )
                        continue
                    return "skip"
                self.console.print("[#94A3B8]Please respond with 'y', 'n', or 'skip'.[/]")

        render_diagnostics_table(diagnostics)
        manual_state = show_manual_notice(manual_missing(diagnostics), set())

        path_only: list[tuple[DiagnosticResult, str]] = []
        for item in diagnostics:
            location = parse_install_location(item.details)
            if location:
                path_only.append((item, location))

        skipped: set[str] = set()
        if path_only:
            self.console.print("[#FACC15]Tools detected but not yet on PATH:[/]")
            for diag_item, location in path_only:
                self.console.print(f"  - {diag_item.name}: {location}")

            grouped: dict[tuple[str, str], list[str]] = {}
            for diag_item, location in path_only:
                quick_cmd, persistent_msg = shell_hint_for(location)
                grouped.setdefault((quick_cmd, persistent_msg), []).append(
                    diag_item.name
                )
                key = installer_key_for_diagnostic(diag_item.name)
                if key:
                    skipped.add(key)

            for (quick_cmd, persistent_msg), tool_names in grouped.items():
                names = ", ".join(tool_names)
                self.console.print(
                    f"[#38BDF8]Temporary fix for {names}:[/] `{quick_cmd}`"
                )
                self.console.print(f"[#94A3B8]Persist it:[/] {persistent_msg}")

            answer = prompt_text(
                self.session,
                "Reload your shell to apply PATH changes now? (y/N)",
            ).strip().lower()
            if answer in {"y", "yes"}:
                self.console.print(
                    "[#38BDF8]Closing SolCoder. "
                    "Run each quick fix command above, append the persistent export to your shell profile "
                    "(e.g., `~/.zshrc`), then reload with `source ~/.zshrc` or `exec $SHELL -l` before restarting.[/]"
                )
                raise SystemExit(0)

        while True:
            missing_all = detect_missing_tools(diagnostics, only_required=False)
            pending = [tool for tool in missing_all if tool not in skipped]
            if not pending:
                break

            tool = "anchor" if "anchor" in pending else pending[0]
            decision = prompt_for_tool(tool)
            name = installer_display_name(tool)

            if decision == "skip":
                skipped.add(tool)
                severity = "warning" if tool in required_set else "info"
                if tool == "anchor":
                    self.console.print(
                        "[#F97316]Anchor install skipped. "
                        "Run `/env install anchor` before attempting deploys.[/]"
                    )
                else:
                    self.console.print(
                        f"[#94A3B8]{name} install skipped. "
                        f"Run `/env install {tool}` later as needed.[/]"
                    )
                self.log_event(
                    "install",
                    f"{name} skipped during bootstrap",
                    severity=severity,
                )
                continue

            installed = run_installer(tool)

            try:
                with self.console.status("Re-running diagnostics...", spinner="dots"):
                    diagnostics = collect_environment_diagnostics()
            except Exception as exc:  # noqa: BLE001
                logger.debug(
                    "Environment diagnostics failed after installing %s: %s", tool, exc
                )
                self.console.print(
                    "[#F97316]Unable to refresh environment diagnostics. "
                    "Run `/env diag` once ready.[/]"
                )
                return True

            render_diagnostics_table(diagnostics)
            manual_state = show_manual_notice(manual_missing(diagnostics), manual_state)

            if installed:
                continue

        remaining = detect_missing_tools(diagnostics, only_required=False)
        if remaining:
            remaining_names = ", ".join(installer_display_name(tool) for tool in remaining)
            self.console.print(
                f"[#FACC15]Setup note:[/] Still missing: {remaining_names}. "
                "Run `/env install <tool>` when ready."
            )

        manual_state = manual_missing(diagnostics)
        if manual_state:
            names = ", ".join(sorted(manual_state))
            self.console.print(
                f"[#F97316]Reminder:[/] {names} require manual installation steps."
            )

        prompt_text(
            self.session,
            "Diagnostics complete. Press Enter when you’re ready to open the SolCoder shell.",
        )
        return True

    def log_event(
        self, category: str, message: str, *, severity: str = "info"
    ) -> LogEntry:
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
            print_raw_llm=self._print_raw_llm,
            todo_manager=self.todo_manager,
            initial_todo_message=self._todo_history_snapshot(),
            max_iterations=self._max_agent_iterations(),
        )
        try:
            return run_agent_loop(context)
        except LLMError as exc:
            logger.error("LLM error: %s", exc)
            return CommandResponse(messages=[("system", f"LLM error: {exc}")])

    def _update_llm_settings(
        self, *, model: str | None = None, reasoning: str | None = None
    ) -> None:
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
        """Render a chat message using modern Rich panels."""
        # Check if this is a TODO panel render request
        if "[[RENDER_TODO_PANEL]]" in message:
            # Render the TODO list as a Rich panel
            tasks = self.todo_manager.as_dicts()
            todo_panel = create_todo_panel(tasks)
            self.console.print(todo_panel)

            # If there's other content in the message, render it too
            other_content = message.replace("[[RENDER_TODO_PANEL]]", "").strip()
            if other_content:
                panel = create_chat_panel(role, other_content, use_markdown=False)
                self.console.print(panel)
            return

        # Detect markdown for agent responses
        use_markdown = role == "agent" and (
            "```" in message or "**" in message or "`" in message
        )

        # Create and print the panel
        panel = create_chat_panel(role, message, use_markdown=use_markdown)
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

    def _prompt_message(self) -> ANSI | str:
        if not self._color_enabled:
            return "➤ "
        # Use ANSI wrapper for proper cursor positioning with color codes
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

    def _prompt_secret(
        self, message: str, *, confirmation: bool = False, allow_master: bool = True
    ) -> str:
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

    def _update_wallet_metadata(
        self, status: WalletStatus, *, balance: float | None
    ) -> None:
        update_wallet_metadata(self.session_context.metadata, status, balance=balance)
        self._refresh_status_bar()

    def _fetch_balance(self, public_key: str | None) -> float | None:
        return fetch_balance(self.rpc_client, public_key)

    def _todo_history_snapshot(self) -> str | None:
        if not self.todo_manager or not self.todo_manager.tasks():
            return None
        todo_render = self.todo_manager.render_plain()
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
            return (
                f"~/{candidate.relative_to(home)}"
                if candidate.is_relative_to(home)
                else str(candidate)
            )
        except ValueError:
            return str(candidate)

    def _resolve_agent_mode(self) -> str:
        return self._agent_mode

    def set_agent_mode(self, mode: str) -> None:
        self._agent_mode = mode
        self._refresh_status_bar()

    def _print_rich(self, *objects: Any, **kwargs: Any) -> None:
        """Print using Rich console, handling both REPL and non-REPL contexts."""
        app = getattr(self.session, "app", None)
        is_running = (
            bool(getattr(app, "is_running", False)) if app is not None else False
        )

        if is_running:
            # When inside patch_stdout(), use sys.__stdout__ (the true original)
            from io import StringIO

            buffer = StringIO()
            temp_console = Console(
                file=buffer,
                force_terminal=True,
                width=self._console.width or 120,
                legacy_windows=False,
                force_interactive=False,
            )
            temp_console.push_theme(SOLCODER_THEME)
            temp_console.print(*objects, **kwargs)
            output = buffer.getvalue()
            if output:
                # Write to sys.__stdout__ which is never patched by prompt_toolkit
                sys.__stdout__.write(output)
                sys.__stdout__.flush()
        else:
            self._console.print(*objects, **kwargs)

    def _load_todo_state(self) -> None:
        if self.session_manager is None:
            return
        state = self.session_manager.load_todo(self.session_context.metadata.session_id)
        if not state:
            return
        tasks = state.get("tasks") or []
        unfinished = [
            task
            for task in tasks
            if isinstance(task, dict) and task.get("status") != "done"
        ]
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
            self.session_manager.save_todo(
                self.session_context.metadata.session_id, state
            )

    @staticmethod
    def _default_console() -> Console:
        force_style = os.environ.get("SOLCODER_FORCE_COLOR")
        no_color = (
            os.environ.get("SOLCODER_NO_COLOR") is not None
            or os.environ.get("NO_COLOR") is not None
        )
        if force_style:
            console = themed_console(force_terminal=True)
            console._solcoder_theme_applied = True
            return console
        if no_color or not sys.stdout.isatty():
            console = themed_console(
                no_color=True, force_terminal=False, color_system=None
            )
            console._solcoder_theme_applied = True
            return console
        console = themed_console()
        console._solcoder_theme_applied = True
        return console
