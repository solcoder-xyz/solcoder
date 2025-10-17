# Milestone 2 — Conversational Core

## Timeframe
Day 1 (hours 12–18)

## Objective
Light up the conversational experience by connecting to the live LLM, routing tool calls, and presenting responses in the CLI so subsequent features can build on a proven dialogue loop.

## Key Deliverables
- Live LLM client (`poetry run solcoder --dry-run-llm`) using stored credentials, with streaming output, retries, and offline fallback.
- Tool registry skeleton registering plan/code/review stubs plus placeholder handlers for future commands.
- Status bar and `/logs` views reflecting session ID, active command, and recent tool invocations during chat.
- Updated configuration docs describing how to set/rotate LLM provider settings.

## Suggested Task Order
1. Task 2.5a — LLM Integration Spike
2. Task 2.5 — Agent Tool Registry Integration (baseline tools)
3. Task 2.6 — Live Status Bar & Logs (initial version)

## Success Criteria
- Users can launch `poetry run solcoder --dry-run-llm` and see streamed tokens from the real provider without errors.
- Chatting “plan hello world” routes through the registry, logs the tool call, and returns a stubbed plan.
- Status bar updates with session ID and active tool; `/logs tools` shows recent invocations.
- Offline mode flag (no API key) falls back to deterministic responses with clear messaging.

## Dependencies
- Builds on Milestone 1 CLI shell, session/config services, and secured LLM credentials.

## Owners & Contributors
- CLI engineer / Prompt engineer: LLM client, registry, UI wiring.
- QA: validate streaming, retry behaviour, and offline fallback.

## Risks & Mitigations
- **Risk:** API rate limits or streaming hiccups. **Mitigation:** Implement retries/backoff and document environment variables for throttling.
- **Risk:** Credential misconfiguration. **Mitigation:** Provide first-run wizard prompts and `/config` rotation commands with validation.

## Hand-off
With the conversational loop working, move to Milestone 3 to deliver the Solana deploy pipeline on top of the live chat experience.
