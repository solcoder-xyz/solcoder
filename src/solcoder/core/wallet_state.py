"""Helpers for synchronising wallet status with session metadata."""

from __future__ import annotations

import logging

from solcoder.session import SessionMetadata
from solcoder.solana import SolanaRPCClient, WalletStatus

logger = logging.getLogger(__name__)


def update_wallet_metadata(metadata: SessionMetadata, status: WalletStatus, *, balance: float | None) -> None:
    """Update session metadata based on the current wallet status."""
    if not status.exists:
        metadata.wallet_status = "missing"
        metadata.wallet_balance = None
        return
    lock_state = "Unlocked" if status.is_unlocked else "Locked"
    address = status.masked_address if status.public_key else "---"
    metadata.wallet_status = f"{lock_state} ({address})"
    metadata.wallet_balance = balance


def fetch_balance(rpc_client: SolanaRPCClient | None, public_key: str | None) -> float | None:
    """Fetch the SOL balance, returning None when unavailable."""
    if not public_key or rpc_client is None:
        return None
    try:
        return rpc_client.get_balance(public_key)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Unable to fetch balance for %s: %s", public_key, exc)
        return None


__all__ = ["update_wallet_metadata", "fetch_balance"]
