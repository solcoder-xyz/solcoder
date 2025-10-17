
"""Interactive CLI shell for SolCoder."""

from __future__ import annotations

import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from solcoder.cli.agent_loop import (
    DEFAULT_AGENT_MAX_ITERATIONS,
    AgentLoopContext,
    run_agent_loop,
)
from solcoder.cli.commands import register_builtin_commands
from solcoder.cli.stub_llm import StubLLM
from solcoder.cli.types import CommandResponse, CommandRouter, LLMBackend
from solcoder.core import ConfigContext, ConfigManager
from solcoder.core.llm import LLMError
from solcoder.core.tool_registry import ToolRegistry, build_default_registry
from solcoder.session import (
    TRANSCRIPT_LIMIT,
    SessionContext,
    SessionManager,
)
from solcoder.solana import SolanaRPCClient, WalletError, WalletManager, WalletStatus

logger = logging.getLogger(__name__)


DEFAULT_HISTORY_PATH = Path(os.environ.get("SOLCODER_HOME", Path.home() / ".solcoder")) / "history"
DEFAULT_HISTORY_LIMIT = 20
DEFAULT_SUMMARY_KEEP = 10
DEFAULT_SUMMARY_MAX_WORDS = 200
DEFAULT_AUTO_COMPACT_THRESHOLD = 0.95
DEFAULT_LLM_INPUT_LIMIT = 272_000
DEFAULT_LLM_OUTPUT_LIMIT = 128_000
DEFAULT_COMPACTION_COOLDOWN = 10
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
        self.console = console or CLIApp._default_console()
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
        self.session = PromptSession(history=FileHistory(str(history_path)))
        self.command_router = CommandRouter()
        register_builtin_commands(self, self.command_router)
        self._llm: LLMBackend = llm or StubLLM()
        self.tool_registry = tool_registry or build_default_registry()
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

        self._record("user", raw_line)
        self._render_message("user", raw_line)

        if raw_line.startswith("/"):
            logger.debug("Processing slash command: %s", raw_line)
            response = self.command_router.dispatch(self, raw_line[1:])
        else:
            logger.debug("Routing chat message to LLM backend")
            response = self._chat_with_llm(raw_line)

        for idx, (role, message) in enumerate(response.messages):
            tool_calls = response.tool_calls if idx == 0 else None
            self._record(role, message, tool_calls=tool_calls)
        self._compress_history_if_needed()
        self._persist()
        return response

    def _max_agent_iterations(self) -> int:
        return DEFAULT_AGENT_MAX_ITERATIONS

    def _chat_with_llm(self, prompt: str) -> CommandResponse:
        context = AgentLoopContext(
            prompt=prompt,
            history=self._conversation_history(),
            llm=self._llm,
            tool_registry=self.tool_registry,
            console=self.console,
            config_context=self.config_context,
            session_metadata=self.session_context.metadata,
            render_message=self._render_message,
            max_iterations=self._max_agent_iterations(),
        )
        try:
            return run_agent_loop(context)
        except LLMError as exc:
            logger.error("LLM error: %s", exc)
            return CommandResponse(messages=[("system", f"LLM error: {exc}")])

    def _conversation_history(self) -> list[dict[str, str]]:
        history: list[dict[str, str]] = []
        # Exclude the most recent entry (current user prompt) because it is passed separately.
        transcript = self._transcript[:-1]
        for entry in transcript:
            message = entry.get("message")
            if not isinstance(message, str) or not message:
                continue
            if entry.get("summary"):
                history.append({"role": "system", "content": message})
                continue
            role = entry.get("role")
            if role == "user":
                history.append({"role": "user", "content": message})
            elif role == "agent":
                history.append({"role": "assistant", "content": message})
            else:
                history.append({"role": "system", "content": message})
        return history

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

    def _compress_history_if_needed(self) -> None:
        transcript = self.session_context.transcript
        history_limit = self._config_int("history_max_messages", DEFAULT_HISTORY_LIMIT)
        cooldown = self.session_context.metadata.compression_cooldown
        if len(transcript) > history_limit and cooldown <= 0:
            self._summarize_older_history()
        metadata = self.session_context.metadata
        input_limit = self._config_int("llm_input_token_limit", DEFAULT_LLM_INPUT_LIMIT)
        threshold = self._config_float("history_auto_compact_threshold", DEFAULT_AUTO_COMPACT_THRESHOLD)
        if metadata.llm_last_input_tokens >= int(input_limit * threshold) and cooldown <= 0:
            self._compress_full_history()
        metadata.compression_cooldown = max(metadata.compression_cooldown - 1, 0)

    def _summarize_older_history(self) -> None:
        transcript = self.session_context.transcript
        history_limit = self._config_int("history_max_messages", DEFAULT_HISTORY_LIMIT)
        keep_count = self._config_int("history_summary_keep", DEFAULT_SUMMARY_KEEP)
        if keep_count >= history_limit:
            keep_count = max(history_limit - 2, 1)
        if len(transcript) <= keep_count:
            return
        older = transcript[:-keep_count]
        if not older:
            return
        summary_text = self._generate_summary(older)
        summary_entry = {
            "role": "system",
            "message": summary_text,
            "timestamp": datetime.now(UTC).isoformat(),
            "summary": True,
        }
        self.session_context.transcript = [summary_entry, *transcript[-keep_count:]]
        self._transcript = self.session_context.transcript
        input_limit = self._config_int("llm_input_token_limit", DEFAULT_LLM_INPUT_LIMIT)
        self.session_context.metadata.llm_last_input_tokens = min(
            self._estimate_context_tokens(),
            input_limit,
        )
        self.session_context.metadata.compression_cooldown = self._config_int(
            "history_compaction_cooldown",
            DEFAULT_COMPACTION_COOLDOWN,
        )

    def _compress_full_history(self) -> None:
        transcript = self.session_context.transcript
        keep_count = self._config_int("history_summary_keep", DEFAULT_SUMMARY_KEEP)
        keep_count = max(min(keep_count, len(transcript)), 1)
        if len(transcript) <= keep_count:
            return
        keep = transcript[-keep_count:]
        summary_text = self._generate_summary(transcript[:-keep_count])
        summary_entry = {
            "role": "system",
            "message": summary_text,
            "timestamp": datetime.now(UTC).isoformat(),
            "summary": True,
        }
        self.session_context.transcript = [summary_entry, *keep]
        self._transcript = self.session_context.transcript
        estimated = self._estimate_context_tokens()
        metadata = self.session_context.metadata
        input_limit = self._config_int("llm_input_token_limit", DEFAULT_LLM_INPUT_LIMIT)
        metadata.llm_last_input_tokens = min(estimated, input_limit)
        metadata.compression_cooldown = self._config_int(
            "history_compaction_cooldown",
            DEFAULT_COMPACTION_COOLDOWN,
        )

    def _generate_summary(self, entries: list[dict[str, Any]]) -> str:
        if not entries:
            return "(history empty)"
        conversation_lines: list[str] = []
        for entry in entries:
            role = entry.get("role", "unknown")
            message = entry.get("message", "")
            conversation_lines.append(f"{role}: {message}")
        transcript_text = "\n".join(conversation_lines)
        base_words = self._config_int("history_summary_max_words", DEFAULT_SUMMARY_MAX_WORDS)
        keep_count = self._config_int("history_summary_keep", DEFAULT_SUMMARY_KEEP)
        multiplier = max(1, len(entries) // max(1, keep_count))
        max_words = base_words * multiplier
        prompt = (
            f"Summarize the following SolCoder chat history in no more than {max_words} words. "
            "Highlight user goals, decisions, constraints, and any open questions.\n"
            f"Conversation:\n{transcript_text}\n"
            "Return plain text without bullet characters unless required."
        )
        tokens: list[str] = []
        try:
            result = self._llm.stream_chat(
                prompt,
                history=(),
                system_prompt="You are a concise summarization engine for coding assistant transcripts.",
                on_chunk=tokens.append,
            )
            summary_text = "".join(tokens).strip() or result.text.strip()
        except LLMError as exc:
            logger.warning("LLM summarization failed: %s", exc)
            summary_text = "Summary unavailable. Recent highlights:\n" + "\n".join(conversation_lines[-3:])
        if not summary_text:
            summary_text = "Summary not available."
        return summary_text

    def _estimate_context_tokens(self) -> int:
        total = 0
        for entry in self.session_context.transcript:
            message = entry.get("message")
            if isinstance(message, str):
                total += len(message.split())
        return total

    def _config_int(self, attr: str, default: int) -> int:
        if self.config_context is None:
            return default
        return int(getattr(self.config_context.config, attr, default) or default)

    def _config_float(self, attr: str, default: float) -> float:
        if self.config_context is None:
            return default
        return float(getattr(self.config_context.config, attr, default) or default)

    def _force_compact_history(self) -> str:
        before = len(self.session_context.transcript)
        self._compress_full_history()
        after = len(self.session_context.transcript)
        return f"Compacted history from {before} entries to {after}."

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
        input_limit = self._config_int("llm_input_token_limit", DEFAULT_LLM_INPUT_LIMIT)
        recent_input = metadata.llm_last_input_tokens or 0
        percent_input = min((recent_input / input_limit * 100) if input_limit else 0.0, 100.0)
        output_total = metadata.llm_output_tokens or 0
        tokens_display = (
            f"ctx in last {recent_input:,}/{input_limit:,} ({percent_input:.1f}%) • "
            f"out total {output_total:,}"
        )
        status = Text(
            f"Session: {session_id} • Project: {project_display} • Wallet: {wallet_display} • "
            f"Balance: {balance_display} • Spend: {spend_display} • Tokens: {tokens_display}",
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
