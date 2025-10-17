from typer.testing import CliRunner

from solcoder.cli import app

runner = CliRunner()


def test_version_command_runs() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "SolCoder CLI version" in result.stdout
