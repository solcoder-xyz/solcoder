"""TODO management toolset for agent orchestration.

The toolkit enforces milestone-focused usage for the shared TODO list. It should
only be used to manage larger outcomes that benefit from tracking across agent
turns rather than single micro-actions.
"""

from __future__ import annotations

from typing import Any

from solcoder.core.todo import TodoManager, serialize_tasks
from solcoder.core.tools.base import Tool, ToolInvocationError, Toolkit, ToolResult


def _bool_flag(payload: dict[str, Any], key: str, *, default: bool = False) -> bool:
    raw = payload.get(key)
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        return raw.strip().lower() in {"1", "true", "yes", "y"}
    if isinstance(raw, (int, float)):
        return bool(raw)
    return default


def todo_toolkit(manager: TodoManager) -> Toolkit:
    """Return a toolkit exposing TODO CRUD operations backed by the provided manager."""

    def _result(
        content: str,
        *,
        summary: str,
        show: bool,
        status: str = "success",
        extra: dict[str, Any] | None = None,
    ) -> ToolResult:
        data = {
            "tasks": serialize_tasks(manager.tasks()),
            "show_todo_list": show,
            "todo_render": manager.render(),
            "revision": manager.revision,
            "revision_mismatch": manager.pop_revision_mismatch(),
            "acknowledged": manager.acknowledged,
            "status": status,
            "active_task_id": manager.active_task_id,
        }
        if extra:
            data.update(extra)
        if data["revision_mismatch"]:
            show = True
        data["show_todo_list"] = show
        data["event"] = content
        rendered_content = content
        if show:
            rendered_content = manager.render()
        return ToolResult(content=rendered_content, summary=summary, data=data)

    def _update_list(payload: dict[str, Any]) -> ToolResult:
        tasks_payload = payload.get("tasks")
        if tasks_payload is None:
            raise ToolInvocationError("Field 'tasks' is required.")
        if not isinstance(tasks_payload, list):
            raise ToolInvocationError("Field 'tasks' must be an array.")
        show = _bool_flag(payload, "show_todo_list", default=True)
        expected_rev = payload.get("if_match", manager.revision)
        try:
            updated = manager.replace_tasks(tasks_payload, expected_revision=expected_rev)
        except ValueError as exc:
            todo_render = manager.render()
            raise ToolInvocationError(f"{exc}\n\n{todo_render}") from exc
        total = len(updated)
        summary = f"TODO list now has {total} item{'s' if total != 1 else ''}."
        event = f"TODO list updated ({total} task{'s' if total != 1 else ''})."
        show = show or total > 0
        return _result(event, summary=summary, show=show)

    def _list_tasks(payload: dict[str, Any]) -> ToolResult:
        show = _bool_flag(payload, "show_todo_list", default=False)
        count = len(manager.tasks())
        plural = "task" if count == 1 else "tasks"
        extra = {"revision": manager.revision}
        return _result(
            f"{count} {plural} tracked.",
            summary=f"{count} {plural}",
            show=show,
            extra=extra,
        )

    def _clear(payload: dict[str, Any]) -> ToolResult:
        show = _bool_flag(payload, "show_todo_list", default=False)
        expected_rev = payload.get("if_match", manager.revision)
        manager.clear(expected_revision=expected_rev)
        return _result(
            "",
            summary="TODO list cleared",
            show=show,
        )

    def _acknowledge(payload: dict[str, Any]) -> ToolResult:
        show = _bool_flag(payload, "show_todo_list", default=True)
        manager.acknowledge()
        return _result(
            "Remaining tasks acknowledged.",
            summary="TODO list acknowledged",
            show=show,
        )

    tools = [
        Tool(
            name="todo_update_list",
            description=(
                "Replace the TODO list with an ordered milestone checklist. "
                "Keep the list empty or track two or more outcomes, skip micro-steps or TODO management entries, "
                "and only mark items done after validators/tests succeed."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "tasks": {
                        "type": "array",
                        "description": "Ordered tasks to track. Send an empty array to clear the list.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {
                                    "type": "string",
                                    "description": "Optional existing task id to preserve when reordering.",
                                },
                                "name": {
                                    "type": "string",
                                    "description": "Short label for the task (required).",
                                },
                                "title": {
                                    "type": "string",
                                    "description": "Alias for 'name' to ease transition; prefer 'name'.",
                                },
                                "description": {
                                    "type": "string",
                                    "description": "Optional additional context for the task.",
                                },
                                "status": {
                                    "type": "string",
                                    "enum": ["todo", "in_progress", "done"],
                                    "description": "Lifecycle state for the task.",
                                },
                            },
                            "required": ["name", "status"],
                        },
                    },
                    "show_todo_list": {
                        "type": "boolean",
                        "description": "Set true to request the CLI render the TODO list after updating.",
                    },
                    "if_match": {
                        "type": "integer",
                        "description": "Expected TODO revision before applying the change.",
                    },
                },
                "required": ["tasks"],
            },
            output_schema={"type": "object"},
            handler=_update_list,
        ),
        Tool(
            name="todo_list_tasks",
            description="Summarize current TODO items.",
            input_schema={
                "type": "object",
                "properties": {
                    "show_todo_list": {
                        "type": "boolean",
                        "description": "Set true to request the CLI render the TODO list.",
                    },
                },
                "required": [],
            },
            output_schema={"type": "object"},
            handler=_list_tasks,
        ),
        Tool(
            name="todo_clear_tasks",
            description="Remove all TODO items.",
            input_schema={
                "type": "object",
                "properties": {
                    "show_todo_list": {
                        "type": "boolean",
                        "description": "Set true to request the CLI render the TODO list (will be empty after clearing).",
                    },
                    "if_match": {
                        "type": "integer",
                        "description": "Expected TODO revision before clearing the list.",
                    },
                },
                "required": [],
            },
            output_schema={"type": "object"},
            handler=_clear,
        ),
        Tool(
            name="todo_acknowledge_remaining",
            description="Mark outstanding TODO items as acknowledged to suppress reminders.",
            input_schema={
                "type": "object",
                "properties": {
                    "show_todo_list": {
                        "type": "boolean",
                        "description": "Set true to display the current TODO list after acknowledging.",
                    },
                },
                "required": [],
            },
            output_schema={"type": "object"},
            handler=_acknowledge,
        ),
    ]

    return Toolkit(
        name="solcoder.todo",
        version="1.0.0",
        description=(
            "Manage milestone-level TODO items for the agent. Use it to track multi-step deliverables, "
            "not trivial actions or TODO maintenance tasks."
        ),
        tools=tools,
    )


__all__ = ["todo_toolkit"]
