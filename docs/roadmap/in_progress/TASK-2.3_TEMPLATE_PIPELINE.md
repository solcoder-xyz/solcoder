# Task 2.3 — `/new` Template Pipeline

- Milestone: [MILESTONE-3_SOLANA_DEPLOY_LOOP](../milestones/MILESTONE-3_SOLANA_DEPLOY_LOOP.md)

## Objective
Connect templates to user prompts so `/new "<prompt>"` selects an Anchor blueprint, renders it, and registers the workspace for subsequent build/deploy commands.

## Deliverables
- Prompt classification logic mapping requests to available templates (counter, NFT mint).
- Template renderer integrated with session state, storing project path and metadata.
- CLI feedback summarizing generated files and next-step hints.
- Tests validating template selection and idempotent re-generation safeguards.

## Key Steps
1. Design mapping heuristics and optional `--template` override flags.
2. Implement rendering pipeline with conflict detection (prompt user before overwriting).
3. Update session to persist active project directory and Anchor workspace config.
4. Write tests in `tests/cli/test_new_command.py` covering selection, overrides, and error paths.
5. Document usage examples in README and milestone notes.

## Dependencies
- Task 1.9 counter template and upcoming NFT template assets.
- Task 1.3 session services.

## Acceptance Criteria
- `/new "create a counter app"` generates counter template and registers workspace.
- CLI outputs follow-up commands (`/deploy`, `/code`) and handles existing directories gracefully.
- Tests cover mapping, overrides, and repeated execution scenarios.

## Owners
- CLI engineer primary; Solana engineer validates template wiring.
