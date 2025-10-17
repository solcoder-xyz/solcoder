from __future__ import annotations

from solcoder.core.env_diag import collect_environment_diagnostics
from solcoder.core.tools.base import Module, Tool, ToolResult


def _diagnostics_handler(_payload: dict[str, str]) -> ToolResult:
    results = collect_environment_diagnostics()
    lines = ["Environment diagnostics:", ""]
    for item in results:
        status = item.status.upper()
        detail = item.version or item.details or "status unknown"
        lines.append(f"- {item.name}: {status} ({detail})")
    summary = f"{sum(r.found for r in results)} of {len(results)} tools detected"
    data = [result.model_dump() for result in results]  # type: ignore[call-arg]
    return ToolResult(content="\n".join(lines), summary=summary, data=data)


def diagnostics_module() -> Module:
    tool = Tool(
        name="collect_env_diagnostics",
        description="Gather environment diagnostics relevant to SolCoder operations.",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        handler=_diagnostics_handler,
    )
    return Module(
        name="solcoder.diagnostics",
        version="1.0.0",
        description="Environment inspection helpers for SolCoder agents.",
        tools=[tool],
    )
