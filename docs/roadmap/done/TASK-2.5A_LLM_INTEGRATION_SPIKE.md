# Task 2.5a — LLM Integration Spike

- Milestone: [MILESTONE-2_CONVERSATIONAL_CORE](../milestones/MILESTONE-2_CONVERSATIONAL_CORE.md)
- Status: In progress — started 2025-10-17 (prep for Milestone 2 kickoff)

## Objective
Connect SolCoder to a live LLM (GPT-4/5, Claude, etc.) early in development to validate API access, streaming, token budgeting, and error handling before layering higher-level tooling.

## Deliverables
- Minimal LLM client wrapper that can send a prompt, stream responses, handle timeouts/retries, and redact logs.
- Reads persisted provider settings/API token from secure storage (Tasks 1.3/1.4) with a fallback prompt when missing.
- Configuration for API keys (env vars) with clear setup steps and local/offline fallbacks.
- Smoke script demonstrating a conversational turn and a tool-call round-trip (even if tools return stubs initially).
- Telemetry/logging that captures latency, token usage, and failure modes for analysis.

## Key Steps
1. Choose primary LLM provider (OpenAI, Anthropic, etc.) and document rate limits + pricing.
2. Implement streaming client with retries/backoff; support both sync and async command execution.
3. Add CLI flag/env toggles for `--llm-provider`, `--llm-base-url`, `--llm-model`, `--llm-api-key`, and `--offline-mode`.
4. Execute a scripted conversation (“hello world”, “run a plan”) to verify streaming output and tool-call JSON parsing.
5. Log token counts and store sample transcripts for regression.

## Dependencies
- Task 1.2 CLI shell (basic REPL) and Task 2.5 tool registry skeleton.

## Acceptance Criteria
- `poetry run solcoder --dry-run-llm` sends a real request and streams tokens to the CLI.
- Tool-call responses (even if mocked) flow through the orchestrator without JSON parsing errors.
- Failure cases (invalid key, timeout) surface actionable messages and fall back to offline stubs when configured.
- Documentation explains how to configure API keys, switch providers, and run in offline mode.

## Owners
- CLI engineer / Prompt engineer to implement client; QA validates streaming behaviour.
