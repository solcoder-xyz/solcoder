# Task 2.5d — TODO / Plan Workflow Parity

- Milestone: [MILESTONE-2_CONVERSATIONAL_CORE](../milestones/MILESTONE-2_CONVERSATIONAL_CORE.md)
- Status: In progress — scoped after Task 2.5c validation

## Objective
Bring the shared TODO manager in line with the agent plan tooling so both surfaces enforce a consistent execution workflow (multi-step minimum, single active step, automatic wrap-up) while retaining the CLI’s collaborative checklist experience.

## Deliverables
- Extended TODO schema with `pending`/`in_progress`/`done` states and helpers that limit the list to one active item at a time.
- Auto-import guard that skips bootstrapping plans with fewer than two meaningful steps, matching the plan tool’s non-trivial requirement.
- Completion handler that clears or auto-acknowledges the TODO list once all items are finished, keeping parity with the plan board’s teardown.
- Updated CLI `/todo` commands, agent toolkit responses, and persistence tests covering the richer status lifecycle.

## Key Steps
1. Update `TodoManager` data model and toolkit payloads to support the three-state lifecycle plus an explicit “set active” operation.
2. Adjust agent loop bootstrap/acknowledgement flow to enforce the ≥2-step rule and to auto-clear finished lists.
3. Refresh CLI command handling, renderers, and state persistence to respect the new status enum and single-active guard.
4. Expand test coverage (core + CLI) to assert state transitions, revision handling, and aggregate parity with plan usage.

## Dependencies
- Task 2.5c (baseline TODO tooling) must remain stable.
- Plan tool governance rules (system prompt + orchestration) inform acceptance criteria.

## Acceptance Criteria
- Creating or importing a plan enforces at least two actionable steps; the agent refuses to treat singleton checklists as plans.
- At most one TODO entry can hold `in_progress`; updates that would violate the guard are rejected in both CLI and tool calls.
- Finishing the final `todo` automatically acknowledges or clears the list, and the agent stops requesting TODO management reminders.
- Tests in `tests/core/test_todo.py`, `tests/core/test_todo_toolkit.py`, and `tests/cli/test_shell.py` cover the new status transitions and parity behaviours.

## Owners
- Core agent engineer for data model and loop coordination.
- CLI engineer for command updates and render ergonomics.
