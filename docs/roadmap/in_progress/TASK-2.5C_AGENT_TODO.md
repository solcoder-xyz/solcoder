# Task 2.5c — Agent TODO Memory

- Milestone: [MILESTONE-2_CONVERSATIONAL_CORE](../milestones/MILESTONE-2_CONVERSATIONAL_CORE.md)
- Status: In progress (follow-up to 2.5b)

## Objective
Augment the agentic loop with an in-memory TODO list so the LLM can persist its plan, mark steps complete, recall outstanding work, and clear the list when done. The agent should:

1. Accept plan steps (e.g. from the initial plan phase) and store them in the TODO list.
2. Support commands to add/update/remove items (`name`, `description`, `status`).
3. Report progress back to the user by reading from the TODO list.
4. Summarize the session and clear the list when the task is finished.

## Deliverables
- TODO list manager (in-memory for now) with operations: `add`, `update`, `complete`, `list`, `clear`.
- Tool registry module exposing TODO operations to the LLM orchestration loop.
- LLM prompt guidelines explaining how to use the TODO tools for planning and progress tracking.
- CLI hooks to display TODO state alongside the progress preview during agent runs.
- Tests covering add/update/complete/clear flows and ensuring the list resets after summaries.

## Key Steps
1. **Data model** – Decide on a simple schema (e.g., list of dicts with `id`, `title`, `description`, `status`).
2. **TODO module + tools** – Implement new tool module (e.g., `solcoder.todo`) with actions `create_task`, `update_task`, `mark_complete`, `list_tasks`, `clear_tasks`.
3. **Loop integration** – Teach the agent loop (2.5b) how to call the TODO tools during the plan phase and throughout execution.
4. **UI integration** – Display current TODO items (and completion percentages) in the CLI status/preview.
5. **Cleanup** – When the agent issues a final summary, auto-clear the TODO list.

## Acceptance Criteria
- Agent can store plan steps in the TODO list and retrieve them later in the session.
- TODO list updates are visible to the user while the agent works.
- TODO list is cleared automatically when the agent signals completion.
- Unit tests cover tool invocation and end-to-end scenarios of plan ingestion, step completion, and cleanup.

## Notes
- Initial implementation can remain in-memory; persistence/backups can be a future enhancement.
- Ensure concurrency with other tools—TODO operations should be fast and safe to call repeatedly.
