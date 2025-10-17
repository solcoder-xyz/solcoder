from __future__ import annotations

from solcoder.core.tools.base import Module, Tool, ToolResult


def _knowledge_handler(payload: dict[str, str]) -> ToolResult:
    query = payload.get("query") or "unspecified query"
    content = (
        f"Knowledge search for '{query}' is not implemented yet.\n"
        "Integrate with knowledge base retrieval before enabling."
    )
    return ToolResult(content=content, summary=f"Knowledge search stub for '{query}'")


def knowledge_module() -> Module:
    tool = Tool(
        name="lookup_knowledge",
        description="Placeholder for knowledge base retrieval (returns stub response).",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query for the knowledge base."}
            },
            "required": ["query"],
        },
        output_schema={"type": "object"},
        handler=_knowledge_handler,
    )
    return Module(
        name="solcoder.knowledge",
        version="0.1.0",
        description="Knowledge retrieval stubs awaiting backend integration.",
        tools=[tool],
    )
