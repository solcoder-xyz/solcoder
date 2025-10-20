from __future__ import annotations

from solcoder.cli.status_bar import StatusBar
from solcoder.core.context import ContextManager
from solcoder.core.config import SolCoderConfig
from solcoder.session.manager import SessionContext, SessionMetadata
from rich.console import Console
from datetime import datetime, timezone


def test_status_bar_includes_spent() -> None:
    now = datetime.now(timezone.utc)
    metadata = SessionMetadata(
        session_id="test",
        created_at=now,
        updated_at=now,
        wallet_status="Unlocked (xxxx…yyyy)",
        wallet_balance=1.234,
        spend_amount=0.123,
    )
    ctx = SessionContext(metadata=metadata, transcript=[])
    cfg_ctx = type("CfgCtx", (), {"config": SolCoderConfig()})()
    cm = ContextManager(ctx, llm=None, config_context=cfg_ctx)
    sb = StatusBar(console=Console(file=None, force_terminal=False), context_manager=cm)
    plain = sb.render_plain()
    assert "spent 0.123" in plain

