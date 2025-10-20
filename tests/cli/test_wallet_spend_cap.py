from __future__ import annotations

import types
from pathlib import Path

from solcoder.cli.commands import wallet as wallet_cmd
from solcoder.solana.wallet import WalletManager


class _DummyConsole:
    def print(self, *_a, **_k) -> None:
        pass


def _make_app(tmp_path: Path, cap_sol: float) -> types.SimpleNamespace:
    mgr = WalletManager(keys_dir=tmp_path / "keys")
    mgr.create_wallet("pass", force=True)
    app = types.SimpleNamespace()
    app.wallet_manager = mgr
    app.console = _DummyConsole()
    app.session_context = types.SimpleNamespace(metadata=types.SimpleNamespace(spend_amount=0.0))
    app.config_context = types.SimpleNamespace(config=types.SimpleNamespace(max_session_spend=cap_sol, rpc_url="http://dummy"))
    app._fetch_balance = lambda _pk: 1.0
    app._update_wallet_metadata = lambda *_a, **_k: None
    app.log_event = lambda *_a, **_k: None
    # Provide spend-cap helper similar to CLIApp implementation
    app._would_exceed_spend_cap = lambda additional: (
        (additional + app.session_context.metadata.spend_amount) > cap_sol,
        (additional + app.session_context.metadata.spend_amount),
        cap_sol,
    )
    return app


def test_send_blocked_by_spend_cap(tmp_path: Path) -> None:
    app = _make_app(tmp_path, cap_sol=0.05)

    # capture handler
    holder = {}
    class R:
        def register(self, cmd):
            holder["handler"] = cmd.handler
    wallet_cmd.register(app, R())
    handle = holder["handler"]

    resp = handle(app, ["send", "Dest11111111111111111111111111111111111111", "0.1"])  # type: ignore[misc]
    assert any("cap exceeded" in msg.lower() for _role, msg in resp.messages)
