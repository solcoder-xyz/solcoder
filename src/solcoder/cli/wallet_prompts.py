"""Prompt helpers for wallet-related secrets."""

from __future__ import annotations

from typing import Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.layout.processors import PasswordProcessor
from rich.console import Console


_MASKING_PROCESSORS = (PasswordProcessor(char=""),)


def prompt_secret(
    session: PromptSession,
    console: Console,
    message: str,
    *,
    master_passphrase: Optional[str],
    confirmation: bool = False,
    allow_master: bool = True,
) -> str:
    """Prompt the user for a passphrase/secret, with optional confirmation."""
    if allow_master and master_passphrase is not None:
        return master_passphrase

    while True:
        # Temporarily disable persistent history to avoid storing secrets.
        old_history = getattr(session.default_buffer, "history", None)
        old_processors = list(getattr(session.default_buffer, "input_processors", ()) or [])
        try:
            session.default_buffer.history = InMemoryHistory()  # type: ignore[assignment]
            session.default_buffer.input_processors = list(_MASKING_PROCESSORS)
            try:
                value = session.prompt(f"{message}: ", is_password=True)
                if not confirmation:
                    return value
                confirm = session.prompt("Confirm passphrase: ", is_password=True)
                if value == confirm:
                    return value
                console.print("[red]Passphrases do not match. Try again.[/red]")
            finally:
                try:
                    session.default_buffer.reset()  # clear any masked characters from the buffer
                except Exception:
                    pass
                try:
                    session.default_buffer.is_password = False  # type: ignore[attr-defined]
                except Exception:
                    pass
                session.default_buffer.input_processors = old_processors
        finally:
            try:
                if old_history is not None:
                    session.default_buffer.history = old_history  # type: ignore[assignment]
            except Exception:
                pass


def prompt_text(session: PromptSession, message: str) -> str:
    """Prompt the user for plain text input."""
    # Be explicit to avoid accidental carry-over of password masking
    return session.prompt(f"{message}: ", is_password=False)


__all__ = ["prompt_secret", "prompt_text"]
