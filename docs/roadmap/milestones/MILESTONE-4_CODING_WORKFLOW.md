# Milestone 4 — Coding Workflow & Controls

## Timeframe
Day 2 (midday–afternoon)

## Objective
Enable the full inspect → edit → test loop inside the CLI, complete with safety rails and context building so the agent can modify code confidently.

## Key Deliverables
- File intelligence commands (`/files`, `/search`, `/open`) and natural-language equivalents for exploring the workspace.
- Automated editing pipeline with diff previews, patch validation, and rollback.
- Command runner for lint/tests/build aliases, triggered via chat (“run tests”) or optional slash commands.
- Ephemeral context builder aggregating files/diffs/knowledge snippets each turn.
- Tool controls enforcing allow/confirm/deny policies with audit logging.

## Suggested Task Order
1. Task 2.7 — Workspace Discovery & File Intelligence
2. Task 2.8 — Automated Editing & Patch Pipeline
3. Task 2.9 — Automated Command Runner & Test Hooks
4. Task 2.11 — Ephemeral Context Builder
5. Task 2.12 — Tool Controls & Audit Logging

## Success Criteria
- Asking “show me the CLI app file” or `/open src/...` streams highlighted content with line numbers.
- “Apply this diff” runs through validation, shows summary, and updates git status; `/revert last` restores previous state.
- “Run tests” launches the configured command, streams output, and posts pass/fail summary; cancellations and timeouts are handled gracefully.
- Context logs display which files/snippets were sent to the LLM; history resets appropriately when sessions restart.
- Tool policy changes via config or `/tools set` take effect immediately and all invocations are logged with session ID + outcome.

## Dependencies
- Milestone 2 conversational loop and Milestone 3 deploy pipeline (workspace metadata, status bar).
- Tasks 2.13–2.15 optional: knowledge snippets can be appended once retrieval is ready.

## Owners & Contributors
- CLI engineer: commands, editing pipeline, command runner, context builder.
- Tech Lead / Prompt engineer: ensure tool metadata aligns with LLM expectations.
- QA: regression tests for diffs, command execution, and policy enforcement.

## Risks & Mitigations
- **Risk:** Patch application corrupts workspace. **Mitigation:** Use git checkpoints, dry-run checks, and confirmation prompts.
- **Risk:** Long-running commands stall UX. **Mitigation:** Provide cancel options, timeouts, and progress indicators.
- **Risk:** Context window overflow. **Mitigation:** Implement token budgeting and summarization hooks in context builder.

## Hand-off
With editing and testing solid, advance to Milestone 5 to enrich responses with curated Solana knowledge and finalize prompt tuning.
