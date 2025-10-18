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
        value = session.prompt(f"{message}: ", is_password=True)
        if not confirmation:
            return value
        confirm = session.prompt("Confirm passphrase: ", is_password=True)
        if value == confirm:
            return value
        console.print("[red]Passphrases do not match. Try again.[/red]")


def prompt_text(session: PromptSession, message: str) -> str:
    """Prompt the user for plain text input."""
    return session.prompt(f"{message}: ")


__all__ = ["prompt_secret", "prompt_text"]
