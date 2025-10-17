# Task 2.9 — Automated Command Runner & Test Hooks

- Milestone: [MILESTONE-4_CODING_WORKFLOW](../milestones/MILESTONE-4_CODING_WORKFLOW.md)

## Objective
Enable the agent to execute shell commands (tests, lint, builds) with streamed output, structured results, and timeout protections so it can validate changes autonomously from either natural-language chat or optional slash commands.

## Deliverables
- Command runner service that executes whitelisted commands (`poetry run pytest`, `poetry run ruff check`, `poetry run black --check`, `anchor build`) within the project root.
- Natural-language intent handler that maps phrases like “run tests”, “format the code”, or “lint the project” onto the same command runner.
- `/run <alias>` CLI command plus `/test` shortcut for standard test pipelines (remain as deterministic fallbacks).
- Output streaming into the chat pane with log folding, exit status, and duration metrics.
- Timeout and resource guards with user prompts for long-running tasks.
- Unit/integration tests mocking subprocess calls to ensure correct parsing and error handling.

## Key Steps
1. Define command alias registry (JSON/TOML) mapping friendly names to actual shell commands and expose them to the LLM planner.
2. Implement subprocess wrapper capturing stdout/stderr incrementally and sanitising paths/secrets.
3. Add timeout handling, cancellation support, and non-zero exit summarisation.
4. Integrate results with status bar and `/logs` so users can review past runs and ensure summaries post back into the chat transcript.
5. Add natural-language routing (“run lint”, “execute the deploy command”) to the same runner and confirm parity with slash commands.
6. Write tests in `tests/cli/test_command_runner.py` simulating success, failure, timeout, cancellation, and conversational triggers.

## Dependencies
- Task 2.5 tool registry (expose runner to LLM/functions).
- Task 1.2 CLI shell for streaming UI.

## Acceptance Criteria
- Running `/test` triggers `poetry run pytest --maxfail=1` and streams progress with final pass/fail summary.
- Typing “run tests” or “lint the code” in chat invokes the same pipeline and returns structured feedback without extra commands.
- Timeouts and manual cancellations cleanly terminate processes and log results.
- Tests cover command mapping, conversational intents, output parsing, and error paths; documentation updated with alias list.

## Owners
- CLI engineer primary; QA validates behaviour on macOS/Ubuntu; Tech Lead approves command allowlist.
