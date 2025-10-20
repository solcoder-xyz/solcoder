from __future__ import annotations

from solcoder.core.tools.command import command_toolkit


def test_execute_shell_command_truncates_multiline_command() -> None:
    toolkit = command_toolkit()
    tool = next(tool for tool in toolkit.tools if tool.name == "execute_shell_command")

    command = "\n".join(
        [
            "cat <<'EOF'",
            "line1",
            "line2",
            "line3",
            "line4",
            "line5",
            "line6",
            "line7",
            "EOF",
        ]
    )

    result = tool.handler({"command": command})

    first_lines = result.content.splitlines()
    assert first_lines[0].startswith("$ cat <<'EOF'")
    assert "more lines truncated" in result.content
