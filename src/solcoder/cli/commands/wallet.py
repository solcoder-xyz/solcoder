"""Wallet management commands."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from solcoder.cli.types import CommandResponse, CommandRouter, SlashCommand
from solcoder.solana import WalletError

if TYPE_CHECKING:  # pragma: no cover
    from solcoder.cli.app import CLIApp


def register(app: CLIApp, router: CommandRouter) -> None:
    """Register the /wallet command."""

    def handle(app: CLIApp, args: list[str]) -> CommandResponse:
        manager = app.wallet_manager
        if manager is None:
            app.log_event("wallet", "Wallet manager unavailable", severity="error")
            return CommandResponse(messages=[("system", "Wallet manager unavailable in this session.")])

        if not args or args[0].lower() == "status":
            status = manager.status()
            balance = app._fetch_balance(status.public_key)
            app._update_wallet_metadata(status, balance=balance)
            if not status.exists:
                app.log_event("wallet", "Wallet status requested (missing)", severity="warning")
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
            app.log_event("wallet", f"Status checked: {lock_state} ({status.masked_address})")
            return CommandResponse(messages=[("system", message)])

        command, *rest = args
        command = command.lower()

        if command == "create":
            if manager.wallet_exists():
                app.log_event("wallet", "Wallet create aborted: already exists", severity="warning")
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
            app.log_event("wallet", f"Wallet created {status.masked_address}")
            return CommandResponse(messages=[("system", message)])

        if command == "restore":
            if not rest:
                secret = app._prompt_text("Paste secret key (JSON array, base58, or recovery phrase)")
            else:
                candidate = Path(rest[0]).expanduser()
                secret = candidate.read_text().strip() if candidate.exists() else " ".join(rest)
            passphrase = app._prompt_secret("Wallet passphrase", confirmation=True)
            try:
                status, mnemonic = manager.restore_wallet(secret, passphrase, overwrite=True)
            except WalletError as exc:
                app.log_event("wallet", f"Wallet restore failed: {exc}", severity="error")
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
            app.log_event("wallet", f"Wallet restored {status.masked_address}")
            return CommandResponse(messages=[("system", " ".join(restored_lines))])

        if command == "unlock":
            initial_pass = app._prompt_secret("Wallet passphrase")
            try:
                status = manager.unlock_wallet(initial_pass)
            except WalletError:
                app.log_event("wallet", "Stored passphrase unlock failed", severity="warning")
                app.console.print("[yellow]Stored passphrase failed; please re-enter.[/yellow]")
                retry_pass = app._prompt_secret("Wallet passphrase", allow_master=False)
                try:
                    status = manager.unlock_wallet(retry_pass)
                except WalletError as exc:
                    app.log_event("wallet", f"Wallet unlock failed: {exc}", severity="error")
                    return CommandResponse(messages=[("system", str(exc))])
            balance = app._fetch_balance(status.public_key)
            app._update_wallet_metadata(status, balance=balance)
            balance_line = f" Current balance {balance:.3f} SOL." if balance is not None else "."
            app.log_event("wallet", f"Wallet unlocked {status.masked_address}")
            return CommandResponse(messages=[("system", f"Wallet unlocked for {status.public_key}.{balance_line}")])

        if command == "lock":
            status = manager.lock_wallet()
            app._update_wallet_metadata(status, balance=None)
            app.log_event("wallet", "Wallet locked")
            return CommandResponse(messages=[("system", "Wallet locked.")])

        if command == "export":
            passphrase = app._prompt_secret("Wallet passphrase")
            try:
                secret = manager.export_wallet(passphrase)
            except WalletError as exc:
                app.log_event("wallet", f"Wallet export failed: {exc}", severity="error")
                return CommandResponse(messages=[("system", str(exc))])
            if rest:
                target_path = Path(rest[0]).expanduser()
                app._write_secret_file(target_path, secret)
                app.log_event("wallet", f"Wallet exported to {target_path}")
                return CommandResponse(messages=[("system", f"Exported secret to {target_path}")])
            app.log_event("wallet", "Wallet secret exported inline", severity="warning")
            return CommandResponse(messages=[("system", f"Exported secret: {secret}")])

        if command in {"phrase", "mnemonic"}:
            passphrase = app._prompt_secret("Wallet passphrase", allow_master=False)
            try:
                mnemonic = manager.get_mnemonic(passphrase)
            except WalletError as exc:
                app.log_event("wallet", f"Wallet mnemonic request failed: {exc}", severity="error")
                return CommandResponse(messages=[("system", str(exc))])
            app.log_event("wallet", "Wallet mnemonic retrieved", severity="warning")
            return CommandResponse(messages=[("system", f"Recovery phrase:\n{mnemonic}")])

        app.log_event("wallet", f"Unknown wallet command '{command}'", severity="warning")
        return CommandResponse(
            messages=[
                (
                    "system",
                    "Unknown wallet command. Available: `/wallet status`, `/wallet create`, `/wallet restore`, `/wallet unlock`, `/wallet lock`, `/wallet export`, `/wallet phrase`.",
                )
            ]
        )

    router.register(SlashCommand("wallet", handle, "Wallet management commands"))


__all__ = ["register"]
