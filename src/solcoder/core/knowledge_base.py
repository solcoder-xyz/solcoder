"""
Lightweight client helper for the SolCoder knowledge base powered by LightRAG.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from collections import Counter
from collections.abc import AsyncIterable
from dataclasses import dataclass
from heapq import nlargest
from pathlib import Path
from typing import Any

try:  # pragma: no cover - exercised via tests with monkeypatch
    from lightrag import LightRAG, QueryParam
except ImportError:  # pragma: no cover
    LightRAG = None  # type: ignore[assignment]
    QueryParam = None  # type: ignore[assignment]


DEFAULT_WORKING_DIR = Path("var/lightrag/solana/lightrag")


logger = logging.getLogger(__name__)


class KnowledgeBaseError(RuntimeError):
    """Raised when the knowledge base cannot be queried."""


@dataclass(slots=True)
class KnowledgeBaseAnswer:
    """Structured response from the knowledge base."""

    text: str
    citations: list[Any]


class KnowledgeBaseClient:
    """Minimal wrapper for querying the packaged LightRAG workspace."""

    def __init__(
        self,
        *,
        working_dir: Path | None = None,
        query_mode: str = "mix",
    ) -> None:
        env_working_dir = os.environ.get("WORKING_DIR")
        resolved_dir = working_dir or (
            Path(env_working_dir) if env_working_dir else DEFAULT_WORKING_DIR
        )
        self.working_dir = Path(resolved_dir)
        self.query_mode = query_mode
        self._prefer_local = os.environ.get("SOLCODER_KB_BACKEND", "").lower() == "local"
        self._local_backend: _LocalKnowledgeBase | None = None
        self._local_backend_error: str | None = None

    async def aquery(self, question: str, *, mode: str | None = None) -> KnowledgeBaseAnswer:
        """Run an async query against the knowledge base."""

        question = question.strip()
        if not question:
            raise KnowledgeBaseError("Knowledge base query requires a non-empty question.")

        if not self.working_dir.exists():
            raise KnowledgeBaseError(
                f"Knowledge pack missing at {self.working_dir}. "
                "Run `make setup-kb` to unpack it."
            )

        if self._prefer_local or LightRAG is None or QueryParam is None:
            return await self._query_local(question)

        try:
            rag = self._build_client()
        except KnowledgeBaseError as exc:
            logger.debug("LightRAG unavailable, falling back to local backend: %s", exc)
            return await self._query_local(question)

        try:
            await rag.initialize_storages()
            try:
                raw_result = await rag.aquery(question, param=self._build_params(mode))
            finally:
                await rag.finalize_storages()
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "LightRAG query failed; attempting local fallback", exc_info=True
            )
            return await self._query_local(question, failure=exc)

        text, citations = await self._extract_text_and_citations(raw_result)
        return KnowledgeBaseAnswer(text=text, citations=citations)

    def query(self, question: str, *, mode: str | None = None) -> KnowledgeBaseAnswer:
        """Synchronous helper for environments without an event loop."""

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.aquery(question, mode=mode))
        raise KnowledgeBaseError(
            "Cannot run synchronous query while an event loop is active; await aquery() instead."
        )

    def _build_client(self):
        if LightRAG is None or QueryParam is None:
            raise KnowledgeBaseError(
                "LightRAG is not installed. Add `LightRAG[api]` to project dependencies."
            )
        if not self.working_dir.exists():
            raise KnowledgeBaseError(
                f"Knowledge pack missing at {self.working_dir}. "
                "Run `make setup-kb` to unpack it."
            )
        try:
            return LightRAG(working_dir=str(self.working_dir))
        except Exception as exc:  # noqa: BLE001
            raise KnowledgeBaseError(f"LightRAG initialization failed: {exc}") from exc

    def _build_params(self, mode: str | None):
        effective_mode = mode or self.query_mode
        return QueryParam(mode=effective_mode)

    async def _query_local(
        self, question: str, *, failure: Exception | None = None
    ) -> KnowledgeBaseAnswer:
        backend = self._ensure_local_backend()
        try:
            return await asyncio.to_thread(backend.query, question)
        except KnowledgeBaseError:
            raise
        except Exception as exc:  # noqa: BLE001
            message = "Local knowledge base query failed"
            if failure is not None:
                message += f" after LightRAG error: {failure}"
            raise KnowledgeBaseError(message) from exc

    def _ensure_local_backend(self) -> _LocalKnowledgeBase:
        if self._local_backend is not None:
            return self._local_backend
        if self._local_backend_error is not None:
            raise KnowledgeBaseError(self._local_backend_error)
        try:
            self._local_backend = _LocalKnowledgeBase(self.working_dir)
            return self._local_backend
        except KnowledgeBaseError as exc:
            self._local_backend_error = str(exc)
            raise
        except FileNotFoundError as exc:  # pragma: no cover - validated earlier
            self._local_backend_error = (
                f"Knowledge pack expected at {self.working_dir} is incomplete ({exc})."
            )
            raise KnowledgeBaseError(self._local_backend_error) from exc

    async def _extract_text_and_citations(self, raw_result: Any) -> tuple[str, list[Any]]:
        if isinstance(raw_result, str):
            return raw_result, []

        if isinstance(raw_result, dict):
            return self._parse_dict_result(raw_result)

        if isinstance(raw_result, AsyncIterable):
            text_chunks: list[str] = []
            citations: list[Any] = []
            async for chunk in raw_result:
                chunk_text, chunk_refs = await self._extract_text_and_citations(chunk)
                if chunk_text:
                    text_chunks.append(chunk_text)
                if chunk_refs:
                    citations.extend(chunk_refs)
            return "".join(text_chunks), citations

        response_attr = getattr(raw_result, "response", None)
        references_attr = getattr(raw_result, "references", None)
        if response_attr is not None or references_attr is not None:
            text = str(response_attr or "")
            citations = self._coerce_citations(references_attr)
            return text, citations

        return str(raw_result), []

    def _parse_dict_result(self, payload: dict[str, Any]) -> tuple[str, list[Any]]:
        possible_text_keys = ("response", "answer", "result", "text", "output")
        text: str = ""
        for key in possible_text_keys:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                text = value
                break
            if value is not None and not text:
                text = str(value)

        if not text and "context" in payload:
            context = payload["context"]
            if isinstance(context, str):
                text = context
            else:
                text = str(context)

        citations_keys = ("references", "citations", "sources", "docs")
        citations_value: Any = []
        for key in citations_keys:
            if key in payload:
                citations_value = payload[key]
                break

        citations = self._coerce_citations(citations_value)
        return text, citations

    def _coerce_citations(self, value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, (set, tuple)):
            return list(value)
        if isinstance(value, dict):
            return list(value.values())
        return [value]


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"[a-z0-9]+")
_MAX_SUMMARY_CHARS = 900


class _LocalKnowledgeBase:
    """Lightweight lexical fallback when LightRAG dependencies are unavailable."""

    def __init__(self, working_dir: Path) -> None:
        self.working_dir = working_dir
        self._entity_chunks: dict[str, Any] = self._load_json("kv_store_entity_chunks.json")
        self._text_chunks: dict[str, Any] = self._load_json("kv_store_text_chunks.json")
        try:
            llm_cache: dict[str, Any] = self._load_json("kv_store_llm_response_cache.json")
        except KnowledgeBaseError:
            llm_cache = {}

        self._entity_summaries = self._build_entity_summaries(llm_cache)
        self._normalized_entities = {name: _normalize(name) for name in self._entity_chunks}

        if not self._entity_chunks:
            raise KnowledgeBaseError("Knowledge base entity index is empty.")

    def query(self, question: str) -> KnowledgeBaseAnswer:
        normalized_query = _normalize(question)
        entity_name = self._match_entity(normalized_query)

        if entity_name:
            summary = self._entity_summaries.get(entity_name)
            if not summary:
                summary = self._summarize_entity(entity_name, normalized_query)
            citations = self._entity_citations(entity_name)
            summary = _trim_summary(summary)
            if summary:
                return KnowledgeBaseAnswer(text=summary, citations=citations)

        fallback_summary, fallback_citations = self._search_chunks(normalized_query)
        fallback_summary = _trim_summary(fallback_summary)
        if fallback_summary:
            return KnowledgeBaseAnswer(text=fallback_summary, citations=fallback_citations)

        raise KnowledgeBaseError("Knowledge base has no matching content for the supplied query.")

    def _load_json(self, name: str) -> dict[str, Any]:
        path = self.working_dir / name
        if not path.exists():
            raise KnowledgeBaseError(f"Required knowledge base file missing: {path}")
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _match_entity(self, normalized_query: str) -> str | None:
        if not normalized_query:
            return None

        query_tokens = set(normalized_query.split())
        best_entity: str | None = None
        best_score = 0.0
        for name, normalized_name in self._normalized_entities.items():
            if not normalized_name:
                continue
            score = 0.0
            if normalized_name in normalized_query:
                score = float(len(normalized_name.split()))
            else:
                name_tokens = set(normalized_name.split())
                overlap = query_tokens & name_tokens
                if overlap:
                    score = len(overlap) / max(len(name_tokens), 1)
            if score > best_score:
                best_score = score
                best_entity = name

        if best_entity is None:
            return None
        if best_score == 0.0:
            return None
        return best_entity

    def _summarize_entity(self, entity_name: str, normalized_query: str) -> str:
        chunk_meta = self._entity_chunks.get(entity_name, {})
        chunk_ids = chunk_meta.get("chunk_ids", [])
        if not chunk_ids:
            return ""

        query_tokens = set(normalized_query.split())
        sentences: list[str] = []
        for chunk_id in chunk_ids:
            chunk = self._text_chunks.get(chunk_id)
            if not chunk:
                continue
            cleaned = _clean_chunk_text(chunk.get("content", ""))
            for sentence in _split_sentences(cleaned):
                if not sentence:
                    continue
                sentence_tokens = set(_normalize(sentence).split())
                if query_tokens and not (sentence_tokens & query_tokens):
                    continue
                sentences.append(sentence.strip())
                if len(sentences) >= 4:
                    break
            if len(sentences) >= 4:
                break
        return " ".join(sentences)

    def _entity_citations(self, entity_name: str) -> list[dict[str, str]]:
        chunk_meta = self._entity_chunks.get(entity_name, {})
        chunk_ids = chunk_meta.get("chunk_ids", [])
        citations: list[dict[str, str]] = []
        seen_sources: set[str] = set()
        for chunk_id in chunk_ids:
            chunk = self._text_chunks.get(chunk_id)
            if not chunk:
                continue
            source = _extract_source_line(chunk.get("content", ""))
            if not source or source in seen_sources:
                continue
            citations.append(_make_citation(source))
            seen_sources.add(source)
            if len(citations) >= 3:
                break
        return citations

    def _search_chunks(self, normalized_query: str) -> tuple[str, list[dict[str, str]]]:
        query_tokens = set(normalized_query.split())
        if not query_tokens:
            return "", []

        scored: list[tuple[float, str]] = []
        for chunk_id, chunk in self._text_chunks.items():
            text = chunk.get("content", "")
            tokens = _tokenize(text)
            if not tokens:
                continue
            counts = Counter(tokens)
            score = float(sum(counts[token] for token in query_tokens if token in counts))
            if score == 0.0:
                continue
            scored.append((score, chunk_id))

        if not scored:
            return "", []

        top_matches = nlargest(3, scored, key=lambda item: item[0])
        snippets: list[str] = []
        citations: list[dict[str, str]] = []
        seen_sources: set[str] = set()

        for _score, chunk_id in top_matches:
            chunk = self._text_chunks.get(chunk_id)
            if not chunk:
                continue
            content = chunk.get("content", "")
            cleaned = _clean_chunk_text(content)
            snippets.append(_summarize_chunk_text(cleaned, query_tokens))
            source = _extract_source_line(content)
            if source and source not in seen_sources:
                citations.append(_make_citation(source))
                seen_sources.add(source)
            if len(snippets) >= 3:
                break

        return " ".join(snippet for snippet in snippets if snippet), citations

    def _build_entity_summaries(self, cache: dict[str, Any]) -> dict[str, str]:
        summaries: dict[str, str] = {}
        for entry in cache.values():
            if not isinstance(entry, dict):
                continue
            if entry.get("cache_type") != "summary":
                continue
            summary = (entry.get("return") or "").strip()
            if not summary:
                continue
            prompt = entry.get("original_prompt", "")
            entity_name = _extract_entity_name(prompt)
            if not entity_name:
                continue
            cleaned = summary.replace("<|COMPLETE|>", "").strip()
            if cleaned.startswith("entity<|#|>"):
                # Skip extraction fragments
                continue
            summaries.setdefault(entity_name, cleaned)
        return summaries


def _normalize(text: str) -> str:
    return " ".join(_WORD_RE.findall(text.lower()))


def _tokenize(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def _split_sentences(text: str) -> list[str]:
    if not text:
        return []
    return _SENTENCE_SPLIT_RE.split(text)


def _clean_chunk_text(text: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# Source:"):
            continue
        if stripped.startswith("# "):
            continue
        lines.append(stripped)
    return " ".join(lines)


def _extract_source_line(text: str) -> str | None:
    for line in text.splitlines():
        if line.startswith("# Source:"):
            return line.split(":", 1)[1].strip()
    return None


def _make_citation(source: str) -> dict[str, str]:
    title = Path(source).name or source
    return {"title": title, "path": source}


def _summarize_chunk_text(text: str, query_tokens: set[str]) -> str:
    sentences = _split_sentences(text)
    selections: list[str] = []
    for sentence in sentences:
        if not sentence:
            continue
        tokens = set(_normalize(sentence).split())
        if query_tokens and not (tokens & query_tokens):
            continue
        selections.append(sentence.strip())
        if len(" ".join(selections)) > 400:
            break
    if not selections and sentences:
        selections.append(sentences[0].strip())
    return " ".join(selections)


def _extract_entity_name(prompt: str) -> str | None:
    match = re.search(r"Entity Name:\s*(.+)", prompt)
    if match:
        name = match.group(1).strip()
        return name if name else None
    return None


def _trim_summary(summary: str) -> str:
    summary = summary.strip()
    if not summary:
        return ""
    if len(summary) <= _MAX_SUMMARY_CHARS:
        return summary
    return summary[: _MAX_SUMMARY_CHARS - 3].rstrip() + "..."
