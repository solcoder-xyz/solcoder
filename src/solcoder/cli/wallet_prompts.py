"""Prompt helpers for wallet-related secrets."""

from __future__ import annotations

from typing import Optional

from prompt_toolkit import PromptSession
from rich.console import Console


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
        try:
            value = session.prompt(f"{message}: ", is_password=True)
            if not confirmation:
                return value
            confirm = session.prompt("Confirm passphrase: ", is_password=True)
            if value == confirm:
                return value
            console.print("[red]Passphrases do not match. Try again.[/red]")
        finally:
            # Ensure subsequent prompts are not masked in case PromptSession retains the flag
            try:
                # Newer prompt_toolkit uses `.is_password`; older may use `.password`
                if hasattr(session.default_buffer, "is_password"):
                    session.default_buffer.is_password = False  # type: ignore[attr-defined]
                if hasattr(session.default_buffer, "password"):
                    session.default_buffer.password = False  # type: ignore[attr-defined]
            except Exception:
                pass


def prompt_text(session: PromptSession, message: str) -> str:
    """Prompt the user for plain text input."""
    # Be explicit to avoid accidental carry-over of password masking
    return session.prompt(f"{message}: ", is_password=False)


__all__ = ["prompt_secret", "prompt_text"]
