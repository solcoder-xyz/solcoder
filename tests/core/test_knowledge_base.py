from __future__ import annotations
from pathlib import Path
from typing import Any

import pytest

from solcoder.core.knowledge_base import (
    KnowledgeBaseAnswer,
    KnowledgeBaseClient,
    KnowledgeBaseError,
)


@pytest.fixture
def kb_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "kb" / "lightrag"
    workspace.mkdir(parents=True)
    return workspace


@pytest.fixture
def stub_lightrag(monkeypatch):
    instances = []

    class DummyQueryParam:
        def __init__(self, mode: str) -> None:
            self.mode = mode

    class FakeLightRAG:
        return_value: Any = "solana info"

        def __init__(self, working_dir: str) -> None:
            self.working_dir = working_dir
            self.initialize_calls = 0
            self.finalize_calls = 0
            self.calls: list[tuple[str, str | None]] = []
            instances.append(self)

        async def initialize_storages(self) -> None:
            self.initialize_calls += 1

        async def finalize_storages(self) -> None:
            self.finalize_calls += 1

        async def aquery(self, question: str, param: DummyQueryParam) -> Any:
            self.calls.append((question, param.mode))
            return self.return_value

    monkeypatch.setattr("solcoder.core.knowledge_base.LightRAG", FakeLightRAG)
    monkeypatch.setattr("solcoder.core.knowledge_base.QueryParam", DummyQueryParam)
    return {"instances": instances, "cls": FakeLightRAG}


@pytest.mark.asyncio
async def test_aquery_handles_string_result(
    kb_workspace: Path, stub_lightrag: dict[str, Any]
) -> None:
    client = KnowledgeBaseClient(working_dir=kb_workspace)
    result = await client.aquery("What is Proof of History?")

    assert result.text == "solana info"
    assert result.citations == []

    rag_instance = stub_lightrag["instances"][0]
    assert rag_instance.working_dir == str(kb_workspace)
    assert rag_instance.calls == [("What is Proof of History?", "mix")]
    assert rag_instance.initialize_calls == 1
    assert rag_instance.finalize_calls == 1


def test_query_runs_async_path(kb_workspace: Path, stub_lightrag) -> None:
    client = KnowledgeBaseClient(working_dir=kb_workspace)
    result = client.query("Explain staking rewards.")

    assert result.text == "solana info"
    rag_instance = stub_lightrag["instances"][0]
    assert rag_instance.calls == [("Explain staking rewards.", "mix")]


@pytest.mark.asyncio
async def test_query_while_loop_running_raises_error(
    kb_workspace: Path, stub_lightrag
) -> None:
    client = KnowledgeBaseClient(working_dir=kb_workspace)
    with pytest.raises(KnowledgeBaseError):
        client.query("Should fail inside loop.")


@pytest.mark.asyncio
async def test_missing_workspace_raises_error(tmp_path: Path, stub_lightrag) -> None:
    missing_dir = tmp_path / "missing" / "lightrag"
    client = KnowledgeBaseClient(working_dir=missing_dir)
    with pytest.raises(KnowledgeBaseError):
        await client.aquery("Where is the data?")


@pytest.mark.asyncio
async def test_aquery_handles_dict_result(
    kb_workspace: Path, stub_lightrag: dict[str, Any]
) -> None:
    stub_lightrag["cls"].return_value = {
        "response": "Solana details",
        "references": [{"title": "Whitepaper"}],
    }
    client = KnowledgeBaseClient(working_dir=kb_workspace)
    result = await client.aquery("Dict response?")
    assert result.text == "Solana details"
    assert result.citations == [{"title": "Whitepaper"}]


@pytest.mark.asyncio
async def test_aquery_handles_async_iterable(
    kb_workspace: Path, stub_lightrag: dict[str, Any]
) -> None:
    async def generator():
        yield "First "
        yield {"response": "chunk", "references": ["Doc"]}

    stub_lightrag["cls"].return_value = generator()
    client = KnowledgeBaseClient(working_dir=kb_workspace)
    result = await client.aquery("Async?")
    assert result.text == "First chunk"
    assert result.citations == ["Doc"]


@pytest.mark.asyncio
async def test_aquery_falls_back_when_lightrag_init_fails(
    kb_workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class BrokenLightRAG:
        def __init__(self, working_dir: str) -> None:  # noqa: D401 - stub
            raise TypeError("no embedding func")

    class DummyQueryParam:
        def __init__(self, mode: str) -> None:
            self.mode = mode

    async def fake_query_local(self, question: str, *, failure: Exception | None = None):
        assert failure is None
        return KnowledgeBaseAnswer(text="local fallback", citations=["local"])

    monkeypatch.setattr("solcoder.core.knowledge_base.LightRAG", BrokenLightRAG)
    monkeypatch.setattr("solcoder.core.knowledge_base.QueryParam", DummyQueryParam)
    monkeypatch.setattr(
        KnowledgeBaseClient, "_query_local", fake_query_local, raising=False
    )

    client = KnowledgeBaseClient(working_dir=kb_workspace)
    result = await client.aquery("Does Proof of History work?")

    assert result.text == "local fallback"
    assert result.citations == ["local"]
