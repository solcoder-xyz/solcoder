# Task 1.2 — CLI Shell & Slash Parser

- Milestone: [MILESTONE-1_FOUNDATIONS](../milestones/MILESTONE-1_FOUNDATIONS.md)

## Objective
Implement the Prompt Toolkit REPL with base layout, history, and a slash-command parser that routes `/help` and placeholder handlers.

## Deliverables
- `src/solcoder/cli/app.py` (or equivalent) launching the REPL via `prompt_toolkit`.
- Command router supporting `/help`, `/quit`, and generic dispatch to future handlers.
- Basic Rich layout showing chat panel and status bar placeholder.
- Integration test asserting slash commands bypass LLM path.

## Key Steps
1. Scaffold the CLI entrypoint (`poetry run solcoder`) that initializes prompt session, history, and event loop.
2. Create a slash-command registry object with parsing and unknown-command feedback.
3. Implement `/help` output enumerating commands defined to date.
4. Add skeleton chat handling for free-form text (stub LLM adapter returning placeholder responses).
5. Capture initial tests under `tests/cli/test_shell.py`.

## Dependencies
- Task 1.1 for project tooling.

## Acceptance Criteria
- Starting `poetry run solcoder` opens the REPL, accepts text, and responds to `/help` without crashing.
- Tests covering parser behavior pass in CI.
- Logging includes trace-level entries for command dispatch.

## Owners
- CLI engineer primary; Tech Lead reviews UX decisions.
