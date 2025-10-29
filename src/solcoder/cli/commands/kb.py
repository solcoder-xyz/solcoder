"""Slash command for querying the Solana knowledge base."""

from __future__ import annotations

from typing import TYPE_CHECKING

from solcoder.cli.types import CommandResponse, CommandRouter, SlashCommand
from solcoder.core.knowledge_base import KnowledgeBaseClient, KnowledgeBaseError

if TYPE_CHECKING:  # pragma: no cover
    from solcoder.cli.app import CLIApp


USAGE = 'Usage: /kb "How does Proof of History work?"'


def register(app: "CLIApp", router: CommandRouter) -> None:
    """Register the `/kb` slash command."""

    def handle(app: "CLIApp", args: list[str]) -> CommandResponse:
        if not args:
            return CommandResponse(messages=[("system", USAGE)])

        question = " ".join(args).strip()
        if not question:
            return CommandResponse(messages=[("system", USAGE)])

        client = getattr(app, "_knowledge_base_client", None)
        if client is None:
            client = KnowledgeBaseClient()
            setattr(app, "_knowledge_base_client", client)

        try:
            answer = client.query(question)
        except KnowledgeBaseError as exc:
            return CommandResponse(messages=[("system", f"Knowledge base unavailable: {exc}")])
        except Exception as exc:  # noqa: BLE001
            return CommandResponse(messages=[("system", f"Knowledge base error: {exc}")])

        message_lines = [answer.text.strip() or "(No response)"]
        citation_lines = _format_citations(answer.citations)
        if citation_lines:
            message_lines.append("")
            message_lines.append("Sources:")
            message_lines.extend(citation_lines)

        return CommandResponse(messages=[("system", "\n".join(message_lines))])

    router.register(SlashCommand("kb", handle, "Query the Solana knowledge base"))


def _format_citations(citations: list[object]) -> list[str]:
    formatted: list[str] = []
    for idx, citation in enumerate(citations, 1):
        label = _describe_citation(citation)
        formatted.append(f"{idx}. {label}")
    return formatted


def _describe_citation(citation: object) -> str:
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
