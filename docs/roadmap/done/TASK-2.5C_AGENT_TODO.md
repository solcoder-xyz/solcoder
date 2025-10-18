# Task 2.5c — Agent TODO Memory

- Milestone: [MILESTONE-2_CONVERSATIONAL_CORE](../milestones/MILESTONE-2_CONVERSATIONAL_CORE.md)
- Status: In progress (follow-up to 2.5b)

## Objective
Augment the agentic loop with an in-memory TODO list so the LLM can track active work, mark steps complete, recall outstanding tasks, and clear the list when done. Planning and TODO remain distinct: the existing `generate_plan` tool stays available for brainstorming long-term strategy, while the TODO tools focus on the current execution steps. The agent should:

1. Offer TODO operations as an explicit tool the LLM must acknowledge in the master prompt (it may defer usage, but initial instructions highlight TODO as the default way to manage active steps).
2. Support commands to add/update/remove items (`name`, `description`, `status`) and optionally request the CLI to display the list (via a `show_todo_list: true|false` flag on relevant tool responses).
3. Allow the user to interact with the same TODO manager through a `/todo` command in the CLI.
4. Summarize the session and clear the list when the task is finished.

## Deliverables
- TODO list manager (in-memory for now) with operations: `add`, `update`, `complete`, `list`, `clear`, and a `show` flag controlling UI rendering.
- Tool registry module exposing TODO operations to the LLM orchestration loop (distinct from `generate_plan` but encouraged in the master prompt).
- LLM prompt guidelines explaining when to lean on TODO tools, clarifying that `generate_plan` is for strategic planning and TODO is for tracking execution.
- CLI hooks so both the agent and the `/todo` command can manipulate the same data store, with optional UI output labelled **TODO List** using checkbox-style markers.
- Tests covering add/update/complete/clear flows, the `show_todo_list` behaviour, and ensuring the list resets after summaries.

## Key Steps
1. **Data model** – Decide on a simple schema (e.g., list of dicts with `id`, `title`, `description`, `status`, `show_todo_list` defaulting to `False`).
2. **TODO module + tools** – Implement new tool module (e.g., `solcoder.todo`) with actions `create_task`, `update_task`, `mark_complete`, `list_tasks`, `clear_tasks`, each accepting the optional `show_todo_list` toggle.
3. **Loop integration** – Update the agent loop (2.5b) prompt to highlight the TODO toolkit, honour the `show_todo_list` flag when deciding whether to render the checklist (labelled and with checkbox markers), and leave long-range strategy to `generate_plan`.
4. **CLI integration** – Add a `/todo` command exposing the same CRUD operations, reusing the shared manager and UI formatting.
5. **Cleanup** – When the agent issues a final summary or the user clears tasks, auto-reset the TODO list.

## Acceptance Criteria
- Agent can store plan steps in the TODO list and retrieve them later in the session.
- TODO list updates become visible only when the LLM (or user) requests display via `show_todo_list`, using checkbox markers under a **TODO List** heading.
- TODO list is cleared automatically when the agent signals completion.
- Unit tests cover tool invocation and end-to-end scenarios of plan ingestion, step completion, and cleanup.

## Notes
- Initial implementation can remain in-memory; persistence/backups can be a future enhancement.
- Ensure concurrency with other tools—TODO operations should be fast and safe to call repeatedly.
