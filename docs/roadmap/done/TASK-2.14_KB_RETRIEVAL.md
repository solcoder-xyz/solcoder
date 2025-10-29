# Task 2.14 — Knowledge Retrieval & Context Injection

- Milestone: [MILESTONE-5_KNOWLEDGE_PROMPTS](../milestones/MILESTONE-5_KNOWLEDGE_PROMPTS.md)
- Status: Completed — finished 2025-10-29 (CLI `/kb` and agent tool online)

## Objective
Build a retrieval tool that searches the curated knowledge base, surfaces relevant snippets via chat or `/kb search`, and feeds those snippets into the context builder so the LLM can enrich its reasoning with Solana expertise.

## Deliverables
- Search utility (ripgrep or lightweight embedding-free ranker) that matches user queries against knowledge metadata and content.
- `/kb search <query>` command plus natural-language handler (“What’s the mint authority flow?”) returning top matches with excerpts and citations.
- Integration with context builder so selected knowledge snippets are appended when the user references related topics or when the plan/review tools detect relevant tags.
- Tests covering ranking, tie-breaking, and context injection (ensuring token budgeting respects knowledge snippets).
- Logging/audit hooks recording knowledge entries used in each session for later review.

## Key Steps
1. Implement knowledge loader parsing `knowledge/index.json` and individual markdown entries.
2. Build search logic using ripgrep + scoring (tag matches > title > body) with configurable result limits.
3. Hook results into CLI output (pretty table with citation) and chat responses.
4. Update context builder to merge knowledge snippets when tags match the user query or current task.
5. Add tests in `tests/core/test_knowledge_retrieval.py` and `tests/cli/test_kb_command.py`.

## Dependencies
- Task 2.13 knowledge base curation.
- Task 2.15 knowledge embedding index (for semantic ranking; fallback allowed when absent).
- Task 2.11 context builder (for injection) and Task 2.5 tool registry.

## Acceptance Criteria
- `/kb search anchor macros` returns concise excerpts with source links and is referenced in the session log.
- When a user asks the agent about SPL tokens, the context builder includes the relevant knowledge snippet automatically.
- Tests pass, and documentation teaches contributors how to use/extend the knowledge retrieval tool.

## Owners
- CLI engineer (search + integration); Tech Lead ensures content accuracy; QA validates context injection.

## Outcome
- `/kb "<question>"` streams LightRAG answers with citation formatting handled in `src/solcoder/cli/commands/kb.py`.
- `knowledge_base_lookup` toolkit wires the retrieval client into the orchestration layer, enabling autonomous plans to inject Solana context mid-run.
- Tests in `tests/core/test_tool_registry.py` and `tests/cli/test_shell.py` guard the command handler, tool registration, and planner integration.
