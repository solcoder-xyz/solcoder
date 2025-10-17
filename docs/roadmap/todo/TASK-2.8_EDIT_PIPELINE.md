# Task 2.8 — Automated Editing & Patch Pipeline

- Milestone: [MILESTONE-4_CODING_WORKFLOW](../milestones/MILESTONE-4_CODING_WORKFLOW.md)

## Objective
Give SolCoder a safe editing workflow that stages diffs, applies patches, and rolls back mistakes so the agent can modify code autonomously like Codex/Claude Code in response to natural-language instructions.

## Deliverables
- `/diff` command summarising git status with staged/unstaged changes and per-file stats, plus a conversational surface (“show me the current diff”).
- Patch application utility supporting unified diff input (from LLM tools) with dry-run validation.
- `/apply <patchfile>` and `/edit` commands that show previews, request confirmation, and update workspace plus git staging area while exposing the same mechanics when users describe edits in plain language.
- Scratch branch or lightweight commit/restore mechanism to recover from failed edits.
- Integration tests verifying patch success, conflict reporting, and rollback functionality.

## Key Steps
1. Implement diff snapshot service using `git` CLI or `dulwich`, capturing before/after metadata.
2. Build patch validator that runs `git apply --check` (or equivalent) before committing changes.
3. Provide rollback command (`/revert last`) restoring workspace from scratch commit or stash and surface the capability via phrases like “undo the last change”.
4. Expose editing functions via tool registry so the LLM can apply patches when users request edits in plain language.
5. Wire conversational handlers (“apply this diff”, “rename the command function”) to the same pipeline for parity with slash commands.
6. Write tests in `tests/cli/test_editing_pipeline.py` covering happy path, conflicts, rollback, and conversational triggers.

## Dependencies
- Task 2.7 file intelligence (context retrieval).
- Task 1.1 repo tooling (git installed/configured).

## Acceptance Criteria
- Submitting a generated patch applies cleanly—whether sent via `/apply` or through a chat instruction—and updates status bar with modified files.
- Conflicting patches surface descriptive errors and leave workspace unchanged.
- `/diff` reflects current state and `/revert last` restores clean working tree; conversational requests hit the same paths without requiring slash syntax.
- Tests run in CI using temporary git repos to validate workflows.

## Owners
- CLI engineer primary; QA ensures rollback safety; Tech Lead reviews git strategy.
