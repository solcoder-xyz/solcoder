# Task 2.13 — Solana Knowledge Base Curation

- Milestone: [MILESTONE-5_KNOWLEDGE_PROMPTS](../milestones/MILESTONE-5_KNOWLEDGE_PROMPTS.md)
- Status: Completed — finished 2025-10-29 (bundled LightRAG workspace shipped)

## Objective
Assemble a localized, attribution-friendly knowledge base covering Solana core concepts (runtime, accounts, fees), Anchor patterns, SPL token standards, Rust ergonomics, and cryptography cheatsheets so the agent can reference them without network access.

## Deliverables
- `knowledge/` directory with curated markdown briefs (e.g., `solana-runtime.md`, `anchor-macros.md`, `spl-token.md`, `cryptography.md`) summarizing the most relevant concepts and linking to official docs.
- Front-matter metadata for each entry (title, tags, source URL, version/date, token cost estimate).
- Index manifest (`knowledge/index.json`) listing entries, tags, and summary blurbs for fast lookup.
- Contribution guidelines outlining how to add/update entries while respecting upstream licenses (prefer summaries, include citations).
- Script or instructions for periodic manual refresh (e.g., `scripts/update_knowledge.md`) noting which docs to review.

## Key Steps
1. Identify high-value topics from Solana/Anchor docs, SPL token manuals, Rust book chapters, and cryptography references.
2. Draft concise summaries (target 300–600 tokens) with diagrams or code snippets where allowed; add citation footnotes.
3. Capture metadata (tags: `runtime`, `anchor`, `token`, `crypto`, etc.) and create the index JSON.
4. Add lint/check step ensuring metadata schema is valid and links resolve.
5. Document the curation process in `README`/`AGENTS` so future contributors can extend the library.

## Dependencies
- Task 1.1 tooling (lint) and Task 1.3 config services for path references.

## Acceptance Criteria
- `knowledge/` directory committed with at least core topics (runtime, Anchor, SPL token, wallet security, cryptography).
- Index file validates against schema; knowledge entries include citations and stay within token budget.
- Documentation provides clear instructions for maintaining the knowledge base, including citation format and licensing caveats.

## Owners
- Tech Lead / Solana engineer for content accuracy; documentation support from PM/Docs lead.

## Outcome
- Curated Solana briefs and metadata live inside the packaged `solana-knowledge-pack.tgz`, keeping licensing-friendly summaries in a distributable archive.
- Extracted workspace lands in `var/lightrag/solana/lightrag/` via `make setup-kb`, matching the structure expected by LightRAG.
- Contributor docs (`README.md`, `AGENTS.md`) explain how to refresh the pack and cite sources when authoring new entries.
