# Task 2.5 — Agent Tool Registry Integration

- Milestone: [MILESTONE-2_CONVERSATIONAL_CORE](../milestones/MILESTONE-2_CONVERSATIONAL_CORE.md)

## Objective
Expose deterministic Python callables for plan/code/review/deploy so the LLM orchestrator can choose tools, with fallbacks when the model is unavailable.

## Deliverables
- Tool registry module registering functions for planning, coding, reviewing, deploying, diagnostics, and knowledge retrieval/command execution.
- LLM client wrapper handling timeouts, retries, and fallback text responses.
- `/plan`, `/code`, `/review` commands invoking registry functions directly (bypassing LLM) for deterministic runs.
- Tests validating tool registration, fallback execution, and CLI dispatch.

## Key Steps
1. Define tool signature schema (inputs, outputs) aligning with LLM tool-calling spec.
2. Implement orchestrator that routes chat messages to tools or LLM as appropriate.
3. Provide offline fallback that returns deterministic instructions when LLM key missing.
4. Expose hooks for future tools (`kb.search`, `command.run`, `wallet.*`) so they can be registered declaratively once implemented.
5. Update CLI help text and documentation to describe new commands and behavior.
6. Write tests in `tests/core/test_tool_registry.py` and `tests/cli/test_plan_code_review.py`.

## Dependencies
- Task 1.2 CLI shell, Task 1.3 session services.
- Task 2.5a LLM integration spike.
- Task 2.4 deploy adapters for `/deploy` integration.

## Acceptance Criteria
- `/plan` and `/review` run without LLM credentials and produce meaningful output (template-driven).
- LLM-enabled runs call registered tools (including knowledge search and command runner once available) and capture structured results, logging errors gracefully.
- Tests cover tool registration, fallback path, and CLI command behavior.

## Owners
- CLI engineer and Tech Lead (LLM orchestration), QA validates fallback behavior.
