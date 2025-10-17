"""Solana JSON-RPC helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

import httpx

logger = logging.getLogger(__name__)

LAMPORTS_PER_SOL = 1_000_000_000


class SolanaRPCError(RuntimeError):
    """Raised when Solana RPC calls fail."""


RequestFn = Callable[[str, Any], httpx.Response]


@dataclass
class SolanaRPCClient:
    """Thin wrapper around Solana's JSON-RPC interface."""

    endpoint: str
    timeout: float = 10.0
    _request: RequestFn | None = None

    def __post_init__(self) -> None:
        if self._request is None:
            self._request = httpx.post

    def get_balance(self, public_key: str) -> float:
        """Return balance for `public_key` in SOL."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [public_key, {"commitment": "confirmed"}],
        }
        response = self._request(self.endpoint, json=payload, timeout=self.timeout)  # type: ignore[arg-type]
        try:
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise SolanaRPCError(f"RPC request failed: {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:  # pragma: no cover - unexpected for compliant RPC
            raise SolanaRPCError("Invalid JSON in RPC response") from exc

        if "error" in data:
            message = data["error"].get("message", "Unknown RPC error")
            raise SolanaRPCError(message)

        try:
            lamports = data["result"]["value"]
        except KeyError as exc:
            raise SolanaRPCError("Malformed RPC response; missing balance value") from exc

        if not isinstance(lamports, int):
            raise SolanaRPCError("Balance value is not an integer")

        balance = lamports / LAMPORTS_PER_SOL
        logger.debug("Fetched balance %.9f SOL for %s", balance, public_key)
        return balance
