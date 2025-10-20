# Task 3.2 — Agent Output Tuning & Fallbacks

- Milestone: [MILESTONE-6_DEMO_POLISH](../milestones/MILESTONE-6_DEMO_POLISH.md)

## Objective
Fine-tune `/plan`, `/code`, and `/review` outputs for clarity and ensure deterministic fallback messaging when LLM access is limited or offline.

## Deliverables
- Prompt templates or system messages producing concise, actionable plan/review summaries.
- Offline fallback scripts covering core templates with deterministic text blocks.
- Command-line flags for summary vs detailed view, honored across LLM and fallback paths.
- Unit tests verifying fallback behavior and ensuring outputs stay within length constraints.

## Key Steps
1. Iterate on prompts with recorded transcripts; capture best-performing variants.
2. Implement fallback content generator referencing template metadata and known risks.
3. Add CLI options (`--summary`, `--detailed`) and integrate with tool registry.
4. Validate outputs inside demo scenario; adjust tone/length per feedback.
5. Add tests in `tests/cli/test_agent_outputs.py` covering fallback and flag handling.

## Dependencies
- Task 2.5 tool registry integration.

## Acceptance Criteria
- `/plan --summary` and `/review --detailed` produce judge-ready narratives in under 10s.
- Disconnecting LLM credentials still yields informative fallback advice for both templates.
- Tests cover fallback path and length checks; manual transcripts archived for demo.

## Owners
- Tech Lead / CLI engineer; QA verifies offline path.
