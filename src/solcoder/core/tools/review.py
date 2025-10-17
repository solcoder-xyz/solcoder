from __future__ import annotations

from solcoder.core.tools.base import Tool, Toolkit, ToolResult


def _review_handler(payload: dict[str, str]) -> ToolResult:
    target = payload.get("target") or "current diff"
    review_points = [
        "Validate behaviour against requirements.",
        "Check for error handling and edge cases.",
        "Ensure tests cover new logic.",
        "Confirm documentation updates if needed.",
    ]
    content = ["Review checklist for", target, ""]
    content.extend(f"- {item}" for item in review_points)
    return ToolResult(content="\n".join(content), summary=f"Generated review checklist for {target}")


def review_toolkit() -> Toolkit:
    tool = Tool(
        name="generate_review_checklist",
        description="Generate a review checklist for the specified code change.",
        input_schema={
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Code area or diff identifier."}
            },
            "required": ["target"],
        },
        output_schema={"type": "object"},
        handler=_review_handler,
    )
    return Toolkit(
        name="solcoder.review",
        version="1.0.0",
        description="Code review guidance utilities for SolCoder agents.",
        tools=[tool],
    )
