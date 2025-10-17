from __future__ import annotations

from solcoder.core.tools.base import Tool, Toolkit, ToolResult


def _plan_handler(payload: dict[str, str]) -> ToolResult:
    goal = payload.get("goal") or "unspecified goal"
    steps = [
        "Clarify success criteria with the requestor.",
        "Review existing project files for relevant context.",
        "Outline implementation tasks with owners and checkpoints.",
        "List risks, open questions, and next follow-ups.",
    ]
    content = ["Plan for:", goal, ""]
    content.extend(f"- {step}" for step in steps)
    return ToolResult(content="\n".join(content), summary=f"Plan drafted for: {goal}")


def plan_toolkit() -> Toolkit:
    tool = Tool(
        name="generate_plan",
        description="Produce a structured project plan from a natural language goal.",
        input_schema={
            "type": "object",
            "properties": {
                "goal": {"type": "string", "description": "Human-provided objective to plan."}
            },
            "required": ["goal"],
        },
        output_schema={"type": "object"},
        handler=_plan_handler,
    )
    return Toolkit(
        name="solcoder.planning",
        version="1.0.0",
        description="Planning utilities for SolCoder orchestration workflows.",
        tools=[tool],
    )
