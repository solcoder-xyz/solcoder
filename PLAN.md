# Minimal Knowledge Base Integration Plan

## Goal
- Enable `/kb "query"` in the CLI and a matching agent tool that answer from the exported
  Solana LightRAG workspace with as little new infrastructure as possible.

## What We Assume
- We already have `solana-knowledge-pack.tgz` containing the populated `lightrag/`
  workspace.
- LightRAG only needs to run in read/query mode inside this project.
- We can touch the CLI router and tool registry without larger refactors.

## Step 1 — Drop In the Assets
- Commit the tarball under `third_party/solana-rag/solana-knowledge-pack.tgz`.
- Add a `.gitignore` entry for `var/lightrag/` and create a simple helper script
  (`scripts/setup_kb.py` or `make setup-kb`) that untars into `var/lightrag/solana/`.

## Step 2 — Wire LightRAG
- Add `LightRAG[api]` to `pyproject.toml` and run `poetry lock`.
- Introduce the smallest possible wrapper (`KnowledgeBaseClient`) that:
  - reads `WORKING_DIR` from config/env (defaulting to `var/lightrag/solana/lightrag`),
  - calls `LightRAG.aquery` with `QueryParam(mode="mix")`,
  - returns the answer text (plus optional citations if available).
- Write unit tests with a mocked LightRAG object to keep feedback fast.

## Step 3 — Expose `/kb`
- Add a CLI command module that parses `/kb "<question>"`, awaits the client, and streams
  the reply to the REPL.
- Cover it with a single CLI test that stubs the client and checks output formatting.

## Step 4 — Add the Agent Tool
- Register a `knowledge_base_lookup` tool in the tool registry that reuses the same client.
- Provide a concise tool description so the planner knows it is for Solana protocol or
  whitepaper questions.
- Add a regression test that the tool is discoverable and returns mocked answers.

## Step 5 — Document Quick Start
- Update `README.md` (or a short doc in `docs/`) with:
  - how to run `poetry install`,
  - how to execute `make setup-kb`,
  - example `/kb` usage and the fact that the agent can auto-call the tool.
- Note troubleshooting tips: missing tarball, missing OpenAI API key.

## Nice-to-Have Later
- Richer logging/metrics on KB usage.
- Automatic pack version checks or downloads.
- Advanced routing between raw LLM answers and the KB.
