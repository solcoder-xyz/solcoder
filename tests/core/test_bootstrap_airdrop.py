from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import types
import pytest

import typer

from solcoder.cli.__init__ import _bootstrap_wallet  # type: ignore[attr-defined]
from solcoder.solana.wallet import WalletManager


class _RPC:
    def __init__(self) -> None:
        self.endpoint = "https://api.devnet.solana.com"
        self._balance = 0.0

    def request_airdrop(self, _addr: str, _amt: float) -> str:
        # pretend success
        self._balance = _amt
        return "sig-ok"

    def get_balance(self, _addr: str) -> float:
        return self._balance


def test_bootstrap_airdrop_prompt_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Force confirm() to return True
    monkeypatch.setattr(typer, "confirm", lambda *a, **k: True)
    # Wallet
    mgr = WalletManager(keys_dir=tmp_path / "keys")
    mgr.create_wallet("pass", force=True)
    rpc = _RPC()
    # Should return a timestamp when airdrop succeeds
    ts = _bootstrap_wallet(mgr, rpc, "pass")
    assert isinstance(ts, datetime)
