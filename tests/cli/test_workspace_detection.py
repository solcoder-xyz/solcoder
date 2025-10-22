from __future__ import annotations

from pathlib import Path

from solcoder.cli import _detect_anchor_workspace


def _touch_anchor(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "Anchor.toml").write_text("[workspace]\n")


def test_detects_anchor_workspace_in_subdirectory(tmp_path: Path) -> None:
    candidate = tmp_path / "apps" / "demo"
    _touch_anchor(candidate)

    detected = _detect_anchor_workspace(tmp_path)

    assert detected == candidate


def test_ignored_directories_are_skipped(tmp_path: Path) -> None:
    ignored = tmp_path / "node_modules" / "demo"
    _touch_anchor(ignored)

    detected = _detect_anchor_workspace(tmp_path)

    assert detected is None
