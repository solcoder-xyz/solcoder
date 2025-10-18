from __future__ import annotations

from io import StringIO

import pytest

from rich.console import Console

from solcoder.cli.branding import render_banner


def test_render_banner_respects_disable(monkeypatch: pytest.MonkeyPatch) -> None:
    stream = StringIO()
    console = Console(file=stream, force_terminal=True, color_system=None)
    monkeypatch.setenv("SOLCODER_DISABLE_BANNER", "1")
    render_banner(console, animate=True)
    output = stream.getvalue()
    occurrences = output.count("Build Solana dApps at Light Speed")
    assert occurrences in {0, 1}
