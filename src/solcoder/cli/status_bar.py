"""Rich-powered status bar rendering for the SolCoder CLI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from prompt_toolkit.formatted_text import ANSI
from rich.console import Console
from rich.text import Text

from solcoder.core.context import ContextManager, DEFAULT_LLM_INPUT_LIMIT

if TYPE_CHECKING:  # pragma: no cover
    from solcoder.core.logs import LogBuffer


@dataclass(slots=True)
class StatusSnapshot:
    """Materialised status information for display and testing."""

    session_id: str
    project: str
    network: str
    wallet: str
    balance: str
    spend: str
    tokens: str
    last_log: str | None = None

    def to_text(self) -> Text:
        """Return a Rich Text renderable representing the snapshot."""
        fields: list[tuple[str, str, str, str]] = [
            ("Session", self.session_id, "dim", "dim"),
            ("Project", self.project, "bold cyan", "bright_white"),
            ("Network", self.network, "bold magenta", "bright_white"),
            ("Wallet", self.wallet, "bold yellow", "bright_white"),
            ("Balance", self.balance, "bold green", "bright_white"),
            ("Spend", self.spend, "bold red", "bright_white"),
            ("Tokens", self.tokens, "bold blue", "bright_white"),
        ]
        if self.last_log is not None:
            fields.append(("Last Log", self.last_log, "bold white", "bright_white"))

        text = Text()
        separator = Text(" │ ", style="dim")
        for idx, (label, value, label_style, value_style) in enumerate(fields):
            if idx:
                text.append_text(separator)
            text.append(f"{label}: ", style=label_style)
            text.append(value, style=value_style)
        return text

    def to_plain(self) -> str:
        """Return a plain-text representation without styling."""
        parts = [
            f"Session: {self.session_id}",
            f"Project: {self.project}",
            f"Network: {self.network}",
            f"Wallet: {self.wallet}",
            f"Balance: {self.balance}",
            f"Spend: {self.spend}",
            f"Tokens: {self.tokens}",
        ]
        if self.last_log is not None:
            parts.append(f"Last Log: {self.last_log}")
        return " | ".join(parts)


class StatusBar:
    """Produces a Rich-rendered status line for the CLI bottom toolbar."""

    def __init__(
        self,
        *,
        console: Console,
        context_manager: ContextManager,
        log_buffer: LogBuffer | None = None,
    ) -> None:
        self._console = console
        self._context_manager = context_manager
        self._log_buffer = log_buffer
        self._supports_toolbar = console.is_terminal

    @property
    def supports_toolbar(self) -> bool:
        return self._supports_toolbar

    def snapshot(self) -> StatusSnapshot:
        metadata = self._context_manager.session_context.metadata
        session_id = metadata.session_id
        project_display = metadata.active_project or "unknown"
        network = "unknown"
        if self._context_manager.config_context is not None:
            network = getattr(self._context_manager.config_context.config, "network", "unknown") or "unknown"
        wallet_display = metadata.wallet_status or "---"
        balance_display = (
            f"{metadata.wallet_balance:.3f} SOL" if metadata.wallet_balance is not None else "--"
        )
        spend_display = f"{metadata.spend_amount:.2f} SOL"
        input_limit = self._context_manager.config_int("llm_input_token_limit", DEFAULT_LLM_INPUT_LIMIT)
        recent_input = metadata.llm_last_input_tokens or 0
        percent_input = min((recent_input / input_limit * 100) if input_limit else 0.0, 100.0)
        output_total = metadata.llm_output_tokens or 0
        tokens_display = (
            f"in {recent_input:,}/{input_limit:,} ({percent_input:.1f}%) • out {output_total:,}"
        )
        last_log = None
        if self._log_buffer is not None:
            entry = self._log_buffer.latest()
            if entry is not None:
                last_log = f"{entry.category}/{entry.severity.upper()}"
        return StatusSnapshot(
            session_id=session_id,
            project=project_display,
            network=network,
            wallet=wallet_display,
            balance=balance_display,
            spend=spend_display,
            tokens=tokens_display,
            last_log=last_log,
        )

    def render_text(self) -> Text:
        return self.snapshot().to_text()

    def render_plain(self) -> str:
        return self.snapshot().to_plain()

    def toolbar(self) -> ANSI | str:
        if not self.supports_toolbar:
            return ""
        with self._console.capture() as capture:
            self._console.print(self.render_text(), end="")
        rendered = capture.get()
        return ANSI(rendered)
