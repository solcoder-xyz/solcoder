from __future__ import annotations

import os
from subprocess import CompletedProcess
from typing import Iterable
from pathlib import Path

from solcoder.core.env_diag import (
    DiagnosticResult,
    ToolRequirement,
    collect_environment_diagnostics,
)


def _runner_factory(outputs: dict[str, CompletedProcess[str]]):
    def _runner(command: list[str]) -> CompletedProcess[str]:
        key = command[0]
        if key not in outputs:
            raise RuntimeError(f"Unexpected command {command}")
        return outputs[key]

    return _runner


def _resolver_factory(paths: dict[str, str]):
    def _resolver(executable: str) -> str | None:
        return paths.get(executable)

    return _resolver


def _tools() -> Iterable[ToolRequirement]:
    return (
        ToolRequirement(
            name="Example Tool",
            executable="example",
            version_args=["--version"],
            remediation="Install example.",
        ),
        ToolRequirement(
            name="Missing Tool",
            executable="missing",
            version_args=["--version"],
            remediation="Install missing.",
        ),
    )


def test_collect_environment_diagnostics_reports_versions() -> None:
    tools = _tools()
    runner = _runner_factory(
        {
            "/usr/bin/example": CompletedProcess(
                args=["/usr/bin/example", "--version"],
                returncode=0,
                stdout="example 1.2.3\n",
                stderr="",
            )
        }
    )
    resolver = _resolver_factory({"example": "/usr/bin/example"})

    results = collect_environment_diagnostics(runner=runner, resolver=resolver, tools=tools)

    assert len(results) == 2
    ok = results[0]
    missing = results[1]
    assert ok.name == "Example Tool"
    assert ok.status == "ok"
    assert ok.version == "example 1.2.3"
    assert ok.remediation is None
    assert not missing.found
    assert missing.status == "missing"
    assert missing.remediation == "Install missing."


def test_collect_environment_diagnostics_handles_runner_errors() -> None:
    tools = (
        ToolRequirement(
            name="Flaky Tool",
            executable="flaky",
            version_args=["--version"],
            remediation="Reinstall flaky tool.",
        ),
    )

    def resolver(executable: str) -> str | None:
        return "/opt/flaky" if executable == "flaky" else None

    def runner(command: list[str]) -> CompletedProcess[str]:
        raise RuntimeError("boom")

    results = collect_environment_diagnostics(runner=runner, resolver=resolver, tools=tools)

    assert len(results) == 1
    result = results[0]
    assert result.status == "error"
    assert result.details == "boom"
    assert result.remediation == "Reinstall flaky tool."


def test_collect_environment_diagnostics_reports_fallback_hint(tmp_path: Path) -> None:
    fallback = tmp_path / "bin" / "example"
    fallback.parent.mkdir(parents=True)
    fallback.write_text("#!/bin/sh\nexit 0\n")
    os.chmod(fallback, 0o755)

    tool = ToolRequirement(
        name="Example Tool",
        executable="example",
        version_args=["--version"],
        remediation="Install example.",
        fallback_paths=(str(fallback),),
    )

    def resolver(_executable: str) -> str | None:
        return None

    runner = _runner_factory(
        {
            str(fallback): CompletedProcess(
                args=[str(fallback), "--version"],
                returncode=0,
                stdout="example 2.0.0\n",
                stderr="",
            )
        }
    )

    results = collect_environment_diagnostics(
        runner=runner,
        resolver=resolver,
        tools=(tool,),
    )

    assert len(results) == 1
    result = results[0]
    assert not result.found
    assert result.status == "missing"
    assert result.version == "example 2.0.0"
    assert result.details == f"Detected at {fallback}, but it is not on PATH."
    assert "Add" in (result.remediation or "")
