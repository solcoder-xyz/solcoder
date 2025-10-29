from __future__ import annotations

from typing import Any

from solcoder.core.knowledge_base import KnowledgeBaseClient, KnowledgeBaseError
from solcoder.core.tools.base import Tool, Toolkit, ToolInvocationError, ToolResult

_KB_CLIENT: KnowledgeBaseClient | None = None


def _get_client() -> KnowledgeBaseClient:
    global _KB_CLIENT
    if _KB_CLIENT is None:
        _KB_CLIENT = KnowledgeBaseClient()
    return _KB_CLIENT


def _knowledge_handler(payload: dict[str, Any]) -> ToolResult:
    query = (payload.get("query") or "").strip()
    if not query:
        raise ToolInvocationError(
            "knowledge_base_lookup requires a non-empty 'query' field."
        )

    client = _get_client()
    try:
        answer = client.query(query)
    except KnowledgeBaseError as exc:
        raise ToolInvocationError(str(exc)) from exc

    citations = _format_citations(answer.citations)
    lines = [answer.text.strip() or "(No response)"]
    if citations:
        lines.append("")
        lines.append("Sources:")
        lines.extend(f"- {cite}" for cite in citations)

    summary = answer.text.strip() if answer.text else None
    if summary and len(summary) > 200:
        summary = summary[:197] + "..."

    return ToolResult(
        content="\n".join(lines),
        summary=summary,
        data={
            "citations": answer.citations,
            "query": query,
            "suppress_preview": True,
        },
    )


def _format_citations(citations: list[Any]) -> list[str]:
    formatted: list[str] = []
    for idx, citation in enumerate(citations, 1):
        formatted.append(f"{idx}. {_describe_citation(citation)}")
    return formatted


def _describe_citation(citation: Any) -> str:
    if isinstance(citation, dict):
        title = citation.get("title") or citation.get("name") or citation.get("id")
        location = citation.get("url") or citation.get("source") or citation.get("path")
        if title and location:
            return f"{title} ({location})"
        if title:
            return str(title)
        if location:
            return str(location)
        return str(citation)
    return str(citation)


def knowledge_toolkit() -> Toolkit:
    tool = Tool(
        name="knowledge_base_lookup",
        description="Query the Solana knowledge base for protocol and ecosystem context.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural-language question to ask the knowledge base.",
                }
            },
            "required": ["query"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "citations": {"type": "array"},
            },
        },
        handler=_knowledge_handler,
    )
    return Toolkit(
        name="solcoder.knowledge",
        version="0.1.0",
        description="Access to the SolCoder Solana knowledge base.",
        tools=[tool],
    )
