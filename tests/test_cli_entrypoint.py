from __future__ import annotations

import sys
from pathlib import Path

import pytest

import solcoder.cli as cli_mod


def test_main_launches_shell_without_command(monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, object] = {}

    def fake_launch(verbose: bool, session: str | None, new_session: bool, config_file: Path | None) -> None:  # type: ignore[override]
        called["args"] = (verbose, session, new_session, config_file)

    monkeypatch.setenv("SOLCODER_DEBUG", "1")
    monkeypatch.setattr(cli_mod, "_launch_shell", fake_launch)
    monkeypatch.setattr(sys, "argv", ["solcoder"])

    cli_mod.main()

    assert called["args"] == (True, None, False, None)


def test_main_routes_run_options(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[bool, str | None, bool, Path | None]] = []

    def fake_launch(verbose: bool, session: str | None, new_session: bool, config_file: Path | None) -> None:  # type: ignore[override]
        calls.append((verbose, session, new_session, config_file))

    monkeypatch.delenv("SOLCODER_DEBUG", raising=False)
    monkeypatch.setattr(cli_mod, "_launch_shell", fake_launch)
    monkeypatch.setattr(sys, "argv", ["solcoder", "--session", "abc123"])

    cli_mod.main()

    assert calls == [(False, "abc123", False, None)]


def test_main_template_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    destination = tmp_path / "demo"
    monkeypatch.setattr(sys, "argv", ["solcoder", "--template", "counter", str(destination)])

    cli_mod.main()

    assert (destination / "Anchor.toml").exists()
