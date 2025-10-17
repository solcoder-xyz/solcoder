
from pathlib import Path
from datetime import UTC, datetime

import json
import sys

import pytest
import typer

from solcoder.cli import main
from solcoder.session import SessionManager


def create_session(root: Path) -> str:
    manager = SessionManager(root=root)
    context = manager.start()
    context.transcript.append(
        {
            "role": "user",
            "message": "Wallet VkgXGe7czUXXcWzeWgt6H9VxLJhqioU5AnqRC1Ry2GK",
            "timestamp": datetime.now(UTC).isoformat(),
        }
    )
    manager.save(context)
    return context.metadata.session_id


def test_dump_session_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    home = tmp_path / "solcoder_home"
    monkeypatch.setenv("SOLCODER_HOME", str(home))
    sessions_root = home / "sessions"
    sessions_root.mkdir(parents=True, exist_ok=True)
    session_id = create_session(sessions_root)
    monkeypatch.setattr(sys, "argv", ["solcoder", "--dump-session", session_id, "--dump-format", "json"])

    with pytest.raises(typer.Exit) as exc:
        main()
    assert exc.value.exit_code == 0

    output = capsys.readouterr().out
    data = json.loads(output)
    assert data["metadata"]["session_id"] == session_id
    assert data["transcript"][0]["message"].endswith("VkgX…y2GK")
    assert "timestamp" in data["transcript"][0]


def test_dump_session_text_output_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "solcoder_home"
    monkeypatch.setenv("SOLCODER_HOME", str(home))
    sessions_root = home / "sessions"
    sessions_root.mkdir(parents=True, exist_ok=True)
    session_id = create_session(sessions_root)
    output_path = tmp_path / "export.txt"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "solcoder",
            "--dump-session",
            session_id,
            "--dump-format",
            "text",
            "--dump-output",
            str(output_path),
        ],
    )

    with pytest.raises(typer.Exit) as exc:
        main()
    assert exc.value.exit_code == 0

    content = output_path.read_text()
    assert "Session Export" in content
    assert "VkgX…y2GK" in content
    assert "[user]" in content


def test_dump_session_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    home = tmp_path / "solcoder_home"
    home.mkdir(parents=True)
    monkeypatch.setenv("SOLCODER_HOME", str(home))
    monkeypatch.setattr(sys, "argv", ["solcoder", "--dump-session", "unknown"])

    with pytest.raises(typer.Exit) as exc:
        main()
    assert exc.value.exit_code == 1

    stderr = capsys.readouterr().out.lower()
    assert "not found" in stderr
