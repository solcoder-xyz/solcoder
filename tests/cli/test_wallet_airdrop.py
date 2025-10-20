from __future__ import annotations

import types
from pathlib import Path
import pytest

from solcoder.cli.commands import wallet as wallet_cmd
from solcoder.solana.wallet import WalletManager


class _DummyStatusCM:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def update(self, _msg: str) -> None:  # pragma: no cover - smoke only
        pass


class _DummyConsole:
    def status(self, _text: str, spinner: str = "dots") -> _DummyStatusCM:  # noqa: ARG002
        return _DummyStatusCM()


class _FakeRPC:
    def __init__(self, balances: list[float], airdrop_failures: int = 0) -> None:
        self._balances = balances
        self._idx = 0
        self._failures = airdrop_failures

    def request_airdrop(self, _address: str, _amount: float) -> str:
        if self._failures > 0:
            self._failures -= 1
            raise RuntimeError("faucet busy")
        return "sig123"

    def get_balance(self, _address: str) -> float:
        if self._idx < len(self._balances):
            val = self._balances[self._idx]
            self._idx += 1
            return val
        return self._balances[-1]


def _make_app(tmp_path: Path, rpc) -> types.SimpleNamespace:
    mgr = WalletManager(keys_dir=tmp_path / "keys")
    status, _ = mgr.create_wallet("pass", force=True)
    app = types.SimpleNamespace()
    app.wallet_manager = mgr
    app.rpc_client = rpc
    app.console = _DummyConsole()
    app.session_context = types.SimpleNamespace(metadata=types.SimpleNamespace(spend_amount=0.0))
    app.session_manager = types.SimpleNamespace(save=lambda _ctx: None)

    def _fetch_balance(pubkey: str | None) -> float | None:
        return None if not pubkey else rpc.get_balance(pubkey)

    def _update_wallet_metadata(_status, *, balance):  # noqa: ARG001
        return None

    app._fetch_balance = _fetch_balance
    app._update_wallet_metadata = _update_wallet_metadata
    app.log_event = lambda *_a, **_k: None
    app.config_context = types.SimpleNamespace(config=types.SimpleNamespace(network="devnet", rpc_url="http://dummy"))
    return app


def test_wallet_airdrop_retries_then_succeeds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # RPC returns 0.0, then 1.0 on polling; airdrop fails first then succeeds
    rpc = _FakeRPC([0.0, 0.0, 1.0], airdrop_failures=1)
    app = _make_app(tmp_path, rpc)

    # Register command and dispatch
    router = types.SimpleNamespace(register=lambda *_a, **_k: None)  # unused by handler
    cmd_router = wallet_cmd
    # Access inner handler via registering to capture closure
    captured = {}

    def _capture_register(_app, _router):
        def inner(app_inner, args):
            return handler(app_inner, args)  # type: ignore[name-defined]

        # Reach into closure by recreating register and extracting handler
        nonlocal captured
        def fake_register(appX, routerX):  # noqa: N802
            nonlocal captured
            def handle_proxy(appY, argsY):
                return handle(appY, argsY)  # type: ignore[name-defined]
            captured["handle"] = handle
            return None
        return None

    # Simpler: call register() and pull out handler from function locals via exec
    local = {}
    def capture(appX, routerX):
        nonlocal local
        # replicate register to bind handle into local dict
        def _local_register(appL, routerL):
            def handle(appH, argsH):
                manager = appH.wallet_manager
                def _address_qr_block(_):
                    return ""
                # We reimport original module register to get correct handler
            return None
        return None

    # Directly import and call the module's register to access generated handler
    holder = {}
    def grab_handler(appZ, routerZ):
        def record(cmd):
            holder["handler"] = cmd.handler
        # emulate router.register storing SlashCommand
        class R:
            def register(self, cmd):
                record(cmd)
        wallet_cmd.register(app, R())
    grab_handler(app, router)
    handle = holder["handler"]

    resp = handle(app, ["airdrop", "1"])  # type: ignore[misc]
    # Expect success path mentioning new balance
    assert any("Airdrop submitted" in msg for role, msg in resp.messages)

