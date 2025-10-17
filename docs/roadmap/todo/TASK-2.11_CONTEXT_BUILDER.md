# Task 2.11 — Ephemeral Context Builder

- Milestone: [MILESTONE-4_CODING_WORKFLOW](../milestones/MILESTONE-4_CODING_WORKFLOW.md)

## Objective
Mirror Codex CLI’s transient knowledge gathering by building an on-demand context packer that scans the workspace, summarizes relevant files, diffs, and metadata for each session turn without maintaining a persistent vector database.

## Deliverables
- Context builder service that collects directory structure, selected file snippets, git branch/diff info, curated knowledge snippets, and recent session transcript before each LLM call.
- Heuristics for selecting relevant files (recently edited, mentioned via `@filename`, template defaults) with token budgeting and truncation policies.
- Cache strategy that stores the latest context bundle in memory per session but regenerates it when the user restarts SolCoder.
- Instrumentation hooks logging which files/snippets were sent to the LLM for observability.
- Unit tests for file selection heuristics and token budgeting; integration test simulating “plan → edit → test” loop with context refreshes.

## Key Steps
1. Define context payload schema (paths, snippets, diffs, metadata) and size limits per LLM model (e.g., 8k/16k tokens).
2. Implement file selection heuristics: include `@`-mentioned files, recent git changes, top N from template manifests, plus fallback to REPL history.
3. Add diff summarizer that highlights staged/unstaged changes and recent commits.
4. Incorporate knowledge retrieval results (Task 2.14) so relevant snippets are appended when available while respecting token budgets.
5. Integrate builder with orchestrator so every tool call receives fresh context; ensure caches reset when session ID changes.
6. Log context usage for debugging, with redaction for secrets and ability to export summaries.
7. Write tests in `tests/core/test_context_builder.py` covering heuristics, knowledge snippet injection, truncation, and refresh triggers.

## Dependencies
- Task 2.7 file intelligence (file listings, search, `@` mentions).
- Task 2.8 edit pipeline (diff data) and Task 1.4 session lifecycle.
- Task 2.14 knowledge retrieval (for snippet injection).
- Task 2.10 system prompts to consume generated context payloads.

## Acceptance Criteria
- LLM call logs show structured context bundles referencing relevant files and diffs.
- Restarting SolCoder creates a new session with a fresh context cache; `--session <id>` reloads previous transcripts but rebuilds file context on demand.
- Token budgeting prevents exceeding model limits; truncated files (including knowledge snippets) include ellipsis markers and instructions for deeper exploration.
- Tests pass, and documentation explains the transient nature of context (no persistent vector DB).

## Owners
- Tech Lead / CLI engineer; QA validates heuristics with sample projects; Prompt engineer reviews integration.
