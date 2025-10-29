# Task 2.15 — Knowledge Embedding Index (Offline RAG)

- Milestone: [MILESTONE-5_KNOWLEDGE_PROMPTS](../milestones/MILESTONE-5_KNOWLEDGE_PROMPTS.md)
- Status: Completed — finished 2025-10-29 (packaged hybrid index + lexical fallback)

## Objective
Enhance SolCoder’s knowledge retrieval by shipping a lightweight, fully offline embedding index that boosts semantic recall over the curated knowledge base without relying on external vector databases.

## Deliverables
- Embedding generator script (`scripts/build_kb_index.py`) that processes `knowledge/` entries into vectors using an open-source, locally runnable model (e.g., `sentence-transformers/all-MiniLM`).
- Persisted index file (FAISS, AnnLite, or SQLite-based) stored under `knowledge/index.faiss` (or similar) with metadata linking vectors back to knowledge documents.
- Retrieval wrapper that falls back to keyword search when the embedding model/index is missing, ensuring compatibility on constrained environments.
- Tests validating embedding build determinism and hybrid search ranking (embedding score + keyword score).
- Documentation covering how to rebuild the index locally, replace the embedding model, and respect distribution/licensing constraints.

## Key Steps
1. Evaluate small-footprint embedding models that can run locally (CPU-friendly) and document installation requirements.
2. Implement index builder: load knowledge entries, generate embeddings, store vectors plus metadata in a reproducible format.
3. Update knowledge retrieval service (Task 2.14) to perform hybrid ranking: embeddings for semantic relevance, ripgrep keyword match as a fallback.
4. Provide CLI hook (`poetry run python scripts/build_kb_index.py`) and CI guard to ensure the index stays in sync with knowledge content.
5. Write tests in `tests/core/test_kb_embeddings.py` covering similarity queries and fallback behaviour.

## Dependencies
- Task 2.13 knowledge base curation.

## Acceptance Criteria
- Repository ships with a prebuilt embedding index matching the committed knowledge content; rebuilding produces identical checksum on supported platforms.
- `/kb search` leverages embeddings when available, improving results for semantic queries (e.g., “secure keypair storage”).
- Fallback to keyword-only search works when embeddings are unavailable (e.g., minimal install).
- Documentation explains resource requirements, rebuild steps, and how to disable embeddings if desired.

## Owners
- CLI engineer / ML engineer for embedding infrastructure; QA validates determinism and fallback logic.

## Outcome
- Vendored LightRAG workspace (`solana-knowledge-pack.tgz`) includes chunk/relationship/vector stores, providing semantic retrieval out-of-the-box.
- `KnowledgeBaseClient` transparently initializes LightRAG when installed and drops to a lexical `_LocalKnowledgeBase` implementation when `SOLCODER_KB_BACKEND=local` or dependencies are missing.
- Documentation now teaches `make setup-kb`, `scripts/setup_kb.py --force`, and environment toggles so contributors can refresh or operate the index offline.
