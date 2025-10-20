"""Rich-powered status bar rendering for the SolCoder CLI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

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
    workspace: str
    network: str
    agent_mode: str
    wallet: str
    balance: str
    tokens: str
    context: str
    last_log: str | None = None

    def to_text(self) -> Text:
        """Return a Rich Text renderable representing the snapshot."""
        fields: list[tuple[str, str, str, str]] = [
            ("Workspace", self.workspace, "bold #14F195", "#0EA5E9"),
            ("Network", self.network, "bold #8264FF", "#cbd5f5"),
            ("Mode", self.agent_mode, "bold #F472B6", "#fbcfe8"),
            ("Wallet", self.wallet, "bold #22D3EE", "#bae6fd"),
            ("Balance", self.balance, "bold #5EEAD4", "#a7f3d0"),
            ("Tokens", self.tokens, "bold #38BDF8", "#7dd3fc"),
            ("Context", self.context, "bold #06B6D4", "#22d3ee"),
        ]
        if self.last_log is not None:
            fields.append(("Last Log", self.last_log, "bold #F472B6", "#fbcfe8"))

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
            f"Workspace: {self.workspace}",
            f"Network: {self.network}",
            f"Mode: {self.agent_mode}",
            f"Wallet: {self.wallet}",
            f"Balance: {self.balance}",
            f"Tokens: {self.tokens}",
            f"Context: {self.context}",
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
        workspace_resolver: Callable[[], str] | None = None,
        agent_mode_resolver: Callable[[], str] | None = None,
    ) -> None:
        self._console = console
        self._context_manager = context_manager
        self._log_buffer = log_buffer
        self._workspace_resolver = workspace_resolver or (lambda: "unknown")
        self._agent_mode_resolver = agent_mode_resolver or (lambda: "assistive")
        self._supports_toolbar = console.is_terminal

    @property
    def supports_toolbar(self) -> bool:
        return self._supports_toolbar

    def set_toolbar_support(self, value: bool) -> None:
        self._supports_toolbar = value

    def snapshot(self) -> StatusSnapshot:
        metadata = self._context_manager.session_context.metadata
        session_id = metadata.session_id
        workspace_display = self._workspace_resolver() or "unknown"
        network = "unknown"
        if self._context_manager.config_context is not None:
            network = getattr(self._context_manager.config_context.config, "network", "unknown") or "unknown"
        agent_mode = self._agent_mode_resolver() or "assistive"
        wallet_status = metadata.wallet_status or "---"
        wallet_display = wallet_status
        wallet_icon = "⚠️"
        if "Unlocked" in wallet_status:
            wallet_icon = "✅"
            wallet_display = wallet_status.replace("Unlocked", "connected")
        elif "Locked" in wallet_status:
            wallet_icon = "🔒"
            wallet_display = wallet_status.replace("Locked", "locked")
        elif "missing" in wallet_status:
            wallet_icon = "⚠️"
            wallet_display = "missing wallet"
        wallet_display = f"{wallet_display} {wallet_icon}".strip()
        balance_display = (
            f"{metadata.wallet_balance:.3f} SOL" if metadata.wallet_balance is not None else "--"
        )
        input_limit = self._context_manager.config_int("llm_input_token_limit", DEFAULT_LLM_INPUT_LIMIT)
        recent_input = metadata.llm_last_input_tokens or 0
        percent_input = min((recent_input / input_limit * 100) if input_limit else 0.0, 100.0)
        context_remaining = max(0.0, 100.0 - percent_input)
        output_total = metadata.llm_output_tokens or 0
        tokens_display = (
            f"in {recent_input:,} • out {output_total:,}"
        )
        context_display = f"{context_remaining:.1f}% context free"
        last_log = None
        if self._log_buffer is not None:
            entry = self._log_buffer.latest()
            if entry is not None:
                last_log = f"{entry.category}/{entry.severity.upper()}"
        return StatusSnapshot(
            session_id=session_id,
            workspace=workspace_display,
            network=network,
            agent_mode=agent_mode,
            wallet=wallet_display,
            balance=balance_display,
            tokens=tokens_display,
            context=context_display,
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
