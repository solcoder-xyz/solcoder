"""Wallet management commands."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from solcoder.core.qr import (
    DataOverflowError,
    QRUnavailableError,
    format_qr_block,
    render_qr_ascii,
)

from solcoder.cli.types import CommandResponse, CommandRouter, SlashCommand
from solcoder.solana import WalletError
from solcoder.solana.rpc import SolanaRPCClient
import time

if TYPE_CHECKING:  # pragma: no cover
    from solcoder.cli.app import CLIApp


def register(app: CLIApp, router: CommandRouter) -> None:
    """Register the /wallet command."""

    def handle(app: CLIApp, args: list[str]) -> CommandResponse:
        manager = app.wallet_manager
        if manager is None:
            app.log_event("wallet", "Wallet manager unavailable", severity="error")
            return CommandResponse(messages=[("system", "Wallet manager unavailable in this session.")])

        def _address_qr_block(address: str) -> str:
            try:
                qr_lines = render_qr_ascii(address).splitlines()
            except (DataOverflowError, QRUnavailableError):
                return "(QR unavailable for address)"
            return format_qr_block(qr_lines)

        if not args or args[0].lower() == "status":
            status = manager.status()
            balance = app._fetch_balance(status.public_key)
            app._update_wallet_metadata(status, balance=balance)
            if not status.exists:
                app.log_event("wallet", "Wallet status requested (missing)", severity="warning")
                return CommandResponse(messages=[("system", "No wallet found. Run `/wallet create` to set one up.")])
            lock_state = "Unlocked" if status.is_unlocked else "Locked"
            balance_line = f"Balance: {balance:.3f} SOL" if balance is not None else "Balance: unavailable"
            qr_block = _address_qr_block(status.public_key or "")
            message = "\n".join(
                [
                    f"Wallet {lock_state}",
                    f"Address: {status.public_key} ({status.masked_address})",
                    balance_line,
                    "Address QR:",
                    qr_block,
                ]
            )
            app.log_event("wallet", f"Status checked: {lock_state} ({status.masked_address})")
            return CommandResponse(messages=[("system", message)])

        command, *rest = args
        command = command.lower()

        if command == "address":
            status = manager.status()
            if not status.exists:
                return CommandResponse(messages=[("system", "No wallet found. Run `/wallet create` to set one up.")])
            if not status.public_key:
                return CommandResponse(messages=[("system", "Wallet address unavailable.")])
            qr_block = _address_qr_block(status.public_key)
            message = "\n".join(
                [
                    f"Wallet address: {status.public_key} ({status.masked_address})",
                    "Address QR:",
                    qr_block,
                ]
            )
            return CommandResponse(messages=[("system", message)])

        if command == "help":
            usage = "\n".join(
                [
                    "Usage: /wallet <subcommand>",
                    "",
                    "Subcommands:",
                    "  status              Show wallet lock state, address, balance, and QR code.",
                    "  address             Print wallet address with QR code.",
                    "  create              Generate a new wallet (prompts for passphrase).",
                    "  restore <secret>    Restore wallet from secret key or mnemonic.",
                    "  unlock              Unlock wallet (prompts for passphrase).",
                    "  lock                Lock the wallet.",
                    "  export [path]       Export secret key (optionally to file).",
                    "  phrase              Display recovery mnemonic (requires passphrase).",
                    "  send <addr> <amt>   Transfer SOL after confirmation and passphrase check.",
                    "  airdrop [amt]       Request a faucet airdrop on devnet/testnet (default 2 SOL).",
                ]
            )
            return CommandResponse(messages=[("system", usage)])

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

        if command == "send":
            if len(rest) < 2:
                return CommandResponse(
                    messages=[("system", "Usage: /wallet send <address> <amount> [--allow-unfunded-recipient]")]
                )
            status = manager.status()
            if not status.exists or not status.public_key:
                return CommandResponse(messages=[("system", "No wallet available. Create or restore one first.")])
            destination = rest[0]
            try:
                amount = float(rest[1])
            except ValueError:
                return CommandResponse(messages=[("system", "Amount must be numeric (SOL).")])
            if amount <= 0:
                return CommandResponse(messages=[("system", "Amount must be greater than zero.")])

            config = getattr(app, "config_context", None)
            rpc_url = getattr(getattr(config, "config", None), "rpc_url", "https://api.devnet.solana.com")
            max_spend = getattr(getattr(config, "config", None), "max_session_spend", None)
            metadata = app.session_context.metadata
            if max_spend is not None and max_spend > 0 and (metadata.spend_amount + amount) > max_spend:
                return CommandResponse(
                    messages=[
                        (
                            "system",
                            f"Session spend cap exceeded. Attempted {amount:.3f} SOL against limit {max_spend:.3f} SOL.",
                        )
                    ]
                )

            qr_block = _address_qr_block(destination)
            confirmation_lines = [
                f"Destination: {destination}",
                f"Amount: {amount:.3f} SOL",
                "Destination QR:",
                qr_block,
                "Type 'send' to confirm or anything else to cancel.",
            ]
            app.console.print("\n".join(confirmation_lines))
            passphrase = app._prompt_secret("Wallet passphrase", allow_master=False)
            acknowledgement = app._prompt_text("Confirm transfer").strip().lower()
            if acknowledgement != "send":
                return CommandResponse(messages=[("system", "Transfer cancelled.")])
            try:
                signature = manager.send_transfer(
                    passphrase,
                    rpc_url=rpc_url,
                    destination=destination,
                    amount_sol=amount,
                )
            except WalletError as exc:
                app.log_event("wallet", f"Transfer failed: {exc}", severity="error")
                return CommandResponse(messages=[("system", f"Transfer failed: {exc}")])

            metadata.spend_amount += amount
            status = manager.status()
            wallet_balance = app._fetch_balance(status.public_key)
            app._update_wallet_metadata(status, balance=wallet_balance)
            app.log_event("wallet", f"Transfer sent {amount:.3f} SOL to {destination}")
            response_lines = [f"Transfer submitted. Signature: {signature}"]
            if wallet_balance is not None:
                response_lines.append(f"Wallet balance: {wallet_balance:.3f} SOL")
            return CommandResponse(messages=[("system", "\n".join(response_lines))])

        if command == "airdrop":
            status = manager.status()
            if not status.exists or not status.public_key:
                return CommandResponse(messages=[("system", "No wallet available. Create or restore one first.")])

            cfg = getattr(app, "config_context", None)
            network = getattr(getattr(cfg, "config", None), "network", "devnet")
            rpc_url = getattr(getattr(cfg, "config", None), "rpc_url", "https://api.devnet.solana.com")
            if str(network).lower() not in {"devnet", "testnet"}:
                return CommandResponse(messages=[("system", "Airdrop is only available on devnet or testnet.")])

            try:
                amount = float(rest[0]) if rest else 2.0
            except ValueError:
                return CommandResponse(messages=[("system", "Amount must be numeric (SOL).")])
            if amount <= 0:
                return CommandResponse(messages=[("system", "Amount must be greater than zero.")])

            rpc_client = app.rpc_client or SolanaRPCClient(endpoint=rpc_url)
            # If we created a fallback client, persist it so subsequent calls use it
            if app.rpc_client is None:
                app.rpc_client = rpc_client
            address = status.public_key
            # Use the resolved rpc_client to fetch balances (not app._fetch_balance)
            try:
                before = rpc_client.get_balance(address)
            except Exception:  # noqa: BLE001
                before = None

            # Show spinner while waiting for airdrop to land
            with app.console.status(f"Requesting {amount:.3f} SOL airdrop…", spinner="dots") as _status:
                # Retry transient faucet errors with simple backoff
                attempts = 3
                delay = 2.0
                last_err: Exception | None = None
                sig: str | None = None
                for i in range(attempts):
                    try:
                        sig = rpc_client.request_airdrop(address, amount)
                        last_err = None
                        break
                    except Exception as exc:  # noqa: BLE001
                        last_err = exc
                        if i < attempts - 1:
                            _status.update("Faucet busy; retrying shortly…")
                            time.sleep(delay)
                            delay *= 1.5
                            continue
                if sig is None:
                    app.log_event("wallet", f"Airdrop failed: {last_err}", severity="error")
                    hint = "Faucet may be rate-limited. Try again in ~30s or reduce the amount."
                    return CommandResponse(messages=[("system", f"Airdrop failed: {last_err}\n{hint}")])

                # Poll balance until it increases or timeout
                deadline = time.time() + 30.0
                final_balance = before
                while time.time() < deadline:
                    time.sleep(1.0)
                    try:
                        current = rpc_client.get_balance(address)
                    except Exception:  # noqa: BLE001
                        continue
                    final_balance = current
                    if before is None or current > (before or 0.0):
                        break
                    _status.update("Waiting for airdrop confirmation…")

            # Update metadata and respond
            status = manager.status()
            app._update_wallet_metadata(status, balance=final_balance)
            if final_balance is not None and (before is None or final_balance > (before or 0.0)):
                app.log_event("wallet", f"Airdrop received ({amount:.3f} SOL)")
                return CommandResponse(
                    messages=[
                        (
                            "system",
                            f"Airdrop submitted (sig: {sig}). New balance: {final_balance:.3f} SOL",
                        )
                    ]
                )
            app.log_event("wallet", "Airdrop submitted; balance unchanged yet", severity="warning")
            return CommandResponse(
                messages=[
                    (
                        "system",
                        f"Airdrop submitted (sig: {sig}). Balance may update shortly.",
                    )
                ]
            )

        app.log_event("wallet", f"Unknown wallet command '{command}'", severity="warning")
        return CommandResponse(
            messages=[
                (
                    "system",
                    "Unknown wallet command. Available: `/wallet status`, `/wallet address`, `/wallet create`, `/wallet restore`, `/wallet unlock`, `/wallet lock`, `/wallet export`, `/wallet phrase`, `/wallet send`, `/wallet help`.",
                )
            ]
        )

    router.register(
        SlashCommand(
            "wallet",
            handle,
            "Wallet management: status | address | create | restore | unlock | lock | export | phrase | send | airdrop",
        )
    )


__all__ = ["register"]
