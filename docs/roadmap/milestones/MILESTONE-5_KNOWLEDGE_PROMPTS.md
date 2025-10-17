# Milestone 5 — Knowledge Hub & Prompts

## Timeframe
Day 2 (evening)

## Objective
Seed SolCoder with curated Solana knowledge and tune prompts so the agent can surface authoritative guidance alongside code changes without relying on the internet.

## Key Deliverables
- Local knowledge base (`knowledge/`) covering runtime fundamentals, Anchor patterns, SPL token standards, wallet security, and cryptography tips with citations.
- Optional embedding index for semantic search, plus fallback keyword ranking for minimal installs.
- Knowledge retrieval tool (`/kb search`, natural-language triggers) that feeds relevant snippets into the context builder.
- Versioned system/assistant prompts describing tool schemas, safety rails, and knowledge usage patterns.

## Suggested Task Order
1. Task 2.13 — Solana Knowledge Base Curation
2. Task 2.15 — Knowledge Embedding Index (Offline RAG)
3. Task 2.14 — Knowledge Retrieval & Context Injection
4. Task 2.10 — LLM System Prompts & Safety Rails

## Success Criteria
- `/kb search anchor macros` returns concise excerpts with citations; context builder logs show snippets included when relevant.
- Knowledge entries stay within token budget, include metadata/front-matter, and pass lint checks.
- Embedding index builds deterministically; hybrid search improves results for fuzzy queries while keyword fallback works when embeddings disabled.
- Prompts encode current tool schemas, call out safety requirements, and can be swapped via config; recorded transcripts confirm the LLM follows inspect → edit → test guardrails.

## Dependencies
- Milestones 2–4 (LLM loop, deploy pipeline, coding workflow).
- Tasks 2.7–2.9, 2.11 to consume knowledge snippets.

## Owners & Contributors
- Tech Lead / Solana engineer: curate content and citations.
- CLI/ML engineer: embedding build + retrieval integration.
- Prompt engineer: finalize prompt templates referencing knowledge tools.
- QA: validate knowledge search, context injection, and prompt regression tests.

## Risks & Mitigations
- **Risk:** Knowledge staleness or licensing issues. **Mitigation:** Use summarized content with clear attributions and note refresh cadence.
- **Risk:** Embedding build incompatibility on constrained machines. **Mitigation:** Provide fallback keyword search and optional index download.
- **Risk:** Prompt drift. **Mitigation:** Version prompts, record transcripts, and require review for changes.

## Hand-off
With knowledge and prompts locked, Milestone 6 focuses on polish, packaging, and demo readiness.
