# Task 2.5d — TODO / Plan Workflow Parity

- Milestone: [MILESTONE-2_CONVERSATIONAL_CORE](../milestones/MILESTONE-2_CONVERSATIONAL_CORE.md)
- Status: Completed — todo manager and plan loop now share a single active-step workflow
- Completion Date: 2025-10-19

## Summary
The shared TODO manager now mirrors the agent plan board: tasks progress through `pending → in_progress → done`, only one item can be active at a time, and agent plan imports require at least two actionable steps. CLI and toolkit surfaces gained an explicit activation helper, persistent state respects the richer lifecycle, and the Rich TODO panel reflects the new semantics.

## Deliverables
- Upgraded `TodoManager` with guarded lifecycle transitions, auto-selection of the next active task, and persistence of the new schema.
- Updated todo toolkit and CLI commands (including `/todo start`) plus UI panel cueing active steps.
- Agent loop guard that skips bootstrapping singleton plans and reuses the enhanced checklist states.

## Verification
- `poetry run pytest tests/core/test_todo.py tests/core/test_todo_toolkit.py tests/cli/test_shell.py::test_todo_command_add_and_complete tests/cli/test_shell.py::test_single_step_plan_isnt_bootstrapped`

## Notes
- Follow-up idea: expose active-step transitions in the status bar when the CLI has multiple pending items.
