from __future__ import annotations

from solcoder.core.tools.base import Tool, Toolkit, ToolResult


def _deploy_handler(payload: dict[str, str]) -> ToolResult:
    environment = payload.get("environment")
    cmd = "/deploy"
    if environment and environment.strip():
        cmd = f"/deploy --cluster {environment.strip()}"
    content = [
        "Dispatching deploy command.",
        f"Use `{cmd}` to build and deploy the active workspace.",
    ]
    return ToolResult(
        content="\n".join(content),
        summary=f"Deploy workspace ({environment or 'current cluster'})",
        data={"dispatch_command": cmd, "suppress_preview": True},
    )


def deploy_toolkit() -> Toolkit:
    tool = Tool(
        name="create_deploy_checklist",
        description="Provide a deployment checklist for the requested environment.",
        input_schema={
            "type": "object",
            "properties": {
                "environment": {
                    "type": "string",
                    "description": "Target network such as devnet, testnet, or mainnet.",
                }
            },
            "required": [],
        },
        output_schema={"type": "object"},
        handler=_deploy_handler,
    )
    return Toolkit(
        name="solcoder.deploy",
        version="1.0.0",
        description="Deployment preparation utilities for SolCoder workflows.",
        tools=[tool],
    )
