# Task 2.10 — LLM System Prompts & Safety Rails

- Milestone: [MILESTONE-5_KNOWLEDGE_PROMPTS](../milestones/MILESTONE-5_KNOWLEDGE_PROMPTS.md)

## Objective
Design and implement the prompt engineering layer that instructs the LLM on SolCoder’s capabilities, safety rules, and tool usage so every conversational turn behaves like a disciplined coding agent.

## Deliverables
- Versioned system prompt template (`prompts/system.md` or similar) describing role, goals, tool invocation etiquette, and explicit constraints (no destructive commands without confirmation, respect spend caps, etc.).
- Assistant/response templates that steer the LLM toward concise action plans, patch generation, and test execution before completing tasks.
- Tool schema metadata bundled with prompts so the LLM knows how to call file-inspection, editing, command runner, wallet, and deploy utilities.
- Configuration loader that injects prompts into the orchestrator and supports environment-specific overrides (demo vs development).
- Documentation referencing how to update prompts, run sandbox evaluations, and capture regression snapshots.

## Key Steps
1. Gather behavioural requirements from PRD, milestone briefs, and security guidance; encode them into an initial system prompt draft.
2. Define assistant prompts for plan/code/review/deploy flows, ensuring they request diffs, summarize logs, and confirm before applying risky changes.
3. Update the tool registry to surface JSON schemas or structured descriptions exposed to the LLM (e.g., `files.list`, `edit.apply_patch`, `command.run`).
4. Implement orchestrator hooks that load prompts, set stop sequences, and log token-level interactions for observability.
5. Run dry-run conversations (recorded transcripts) validating file mention resolution, editing pipeline calls, and test execution autopilot.
6. Document the prompt update process in `AGENTS.md` or a dedicated prompt README.

## Dependencies
- Task 2.5a LLM integration spike.
- Task 2.5 tool registry integration.
- Tasks 2.7–2.9 to ensure referenced tools exist and expose proper metadata.
- Tasks 2.13–2.15 so knowledge retrieval tooling is available for prompt references.

## Acceptance Criteria
- System prompt and assistant templates checked into version control with clear changelog comments.
- Recorded sessions show the agent following the mandate: inspect → edit → test before declaring success; refuses destructive actions without explicit approval.
- Prompt loader supports swapping variants via config flag or environment variable for experiments.
- Documentation describes how to evaluate prompt changes and roll back if regressions occur.

## Owners
- Tech Lead / Prompt engineer primary; CLI engineer assists with orchestrator wiring; QA validates behaviour through scripted transcripts.
