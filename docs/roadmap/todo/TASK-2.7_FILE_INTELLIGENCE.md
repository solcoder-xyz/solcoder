# Task 2.7 — Workspace Discovery & File Intelligence

- Milestone: [MILESTONE-4_CODING_WORKFLOW](../milestones/MILESTONE-4_CODING_WORKFLOW.md)

## Objective
Equip the agent with conversational and deterministic tools to survey the project workspace, search for symbols, and preview files so it can reason about code before proposing edits.

## Deliverables
- Natural-language handler (e.g., “list the project files”, “open src/solcoder/core/config.py”) that routes through the same utilities the LLM can call.
- `/files` command producing a Rich tree view (depth-limited) of the active project with filters for `src/`, `tests/`, and template directories.
- `/search "<pattern>"` powered by ripgrep (or Python fallback) returning filepath, line, and context snippets.
- `/open <path> [--start N --end M]` command streaming highlighted file excerpts with line numbers.
- Safety guardrails preventing access outside the active project root unless explicitly whitelisted.
- `@filename` mention parsing that resolves shorthand references in chat to absolute workspace paths (with disambiguation prompts when multiple matches exist).
- Unit tests covering file listing, search filtering, and path sanitisation edge cases.

## Key Steps
1. Integrate `rg` or pure-Python search with sensible defaults and fallback when binary missing.
2. Build tree view component with collapsible directories and size limits for large repos.
3. Implement file reader that enforces path constraints, supports partial slices, and redacts secrets.
4. Wire commands into the CLI router and status bar so the agent can call them via LLM tools.
5. Add tests in `tests/cli/test_file_commands.py` exercising listing, search, and open operations.

## Dependencies
- Task 1.3 session services (project root tracking).
- Task 2.5 tool registry to expose commands to the LLM agent.

## Acceptance Criteria
- Invoking `/files --depth 2` lists the workspace structure without exceeding 2 seconds on reference hardware.
- `/search "Program ID"` returns relevant matches with surrounding lines and truncation for large hits.
- `/open src/solcoder/cli/app.py --start 1 --end 120` streams syntax-highlighted content without crashing.
- Chatting “show me the CLI app file” triggers the same functionality without needing the slash command and returns within expected latency.
- Referencing `@wallet.py` in chat inserts the resolved path in the agent plan and echoes it back to the user, with a clarification prompt if multiple matches exist.
- Tests validate sanitisation and fallback behaviour, and documentation includes usage examples.

## Owners
- CLI engineer primary; QA validates performance and path safety.
