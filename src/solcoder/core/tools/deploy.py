from __future__ import annotations

from solcoder.core.tools.base import Module, Tool, ToolResult


def _deploy_handler(payload: dict[str, str]) -> ToolResult:
    environment = payload.get("environment", "devnet")
    steps = [
        "Run `anchor build` (or relevant build command).",
        f"Deploy to {environment} environment.",
        "Verify logs and post-deploy health checks.",
    ]
    content = ["Deployment checklist:", ""]
    content.extend(f"- {step}" for step in steps)
    return ToolResult(content="\n".join(content), summary=f"Deployment checklist for {environment}")


def deploy_module() -> Module:
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
        },
        output_schema={"type": "object"},
        handler=_deploy_handler,
    )
    return Module(
        name="solcoder.deploy",
        version="1.0.0",
        description="Deployment preparation utilities for SolCoder workflows.",
        tools=[tool],
    )
