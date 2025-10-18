"""TODO management toolset for agent orchestration."""

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
        }
        if extra:
            data.update(extra)
        if data["revision_mismatch"]:
            data["show_todo_list"] = True
        return ToolResult(content=content, summary=summary, data=data)

    def _create(payload: dict[str, Any]) -> ToolResult:
        title = payload.get("title")
        description = payload.get("description")
        show = _bool_flag(payload, "show_todo_list", default=False)
        expected_rev = payload.get("if_match", manager.revision)
        try:
            task = manager.create_task(title or "", description=description, expected_revision=expected_rev)
        except ValueError as exc:
            todo_render = manager.render()
            raise ToolInvocationError(f"{exc}\n\n{todo_render}") from exc
        return _result(
            f"Task '{task.title}' added (id: {task.id}).",
            summary=f"Task added: {task.id}",
            show=show,
        )

    def _update(payload: dict[str, Any]) -> ToolResult:
        task_id = payload.get("task_id")
        if not task_id:
            raise ToolInvocationError("Field 'task_id' is required.")
        fields = {key: payload.get(key) for key in ("title", "description", "status")}
        show = _bool_flag(payload, "show_todo_list", default=False)
        if all(value is None for value in fields.values()):
            raise ToolInvocationError("Provide at least one field to update.")
        expected_rev = payload.get("if_match", manager.revision)
        try:
            task = manager.update_task(
                task_id,
                title=fields["title"],
                description=fields["description"],
                status=fields["status"],
                expected_revision=expected_rev,
            )
        except ValueError as exc:
            todo_render = manager.render()
            raise ToolInvocationError(f"{exc}\n\n{todo_render}") from exc
        return _result(
            f"Task '{task.id}' updated.",
            summary=f"Task updated: {task.id}",
            show=show,
        )

    def _complete(payload: dict[str, Any]) -> ToolResult:
        task_id = payload.get("task_id")
        if not task_id:
            raise ToolInvocationError("Field 'task_id' is required.")
        show = _bool_flag(payload, "show_todo_list", default=False)
        expected_rev = payload.get("if_match", manager.revision)
        try:
            task = manager.mark_complete(task_id, expected_revision=expected_rev)
        except ValueError as exc:
            todo_render = manager.render()
            raise ToolInvocationError(f"{exc}\n\n{todo_render}") from exc
        return _result(
            f"Task '{task.id}' marked complete.",
            summary=f"Task completed: {task.id}",
            show=show,
        )

    def _remove(payload: dict[str, Any]) -> ToolResult:
        task_id = payload.get("task_id")
        if not task_id:
            raise ToolInvocationError("Field 'task_id' is required.")
        show = _bool_flag(payload, "show_todo_list", default=False)
        expected_rev = payload.get("if_match", manager.revision)
        try:
            manager.remove_task(task_id, expected_revision=expected_rev)
        except ValueError as exc:
            todo_render = manager.render()
            raise ToolInvocationError(f"{exc}\n\n{todo_render}") from exc
        return _result(
            f"Task '{task_id}' removed.",
            summary=f"Task removed: {task_id}",
            show=show,
        )

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
            name="todo_add_task",
            description="Add a new TODO item for the current task.",
            input_schema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Short label for the task."},
                    "description": {"type": "string", "description": "Optional details for later reference."},
                    "show_todo_list": {
                        "type": "boolean",
                        "description": "Set true to request the CLI render the TODO list.",
                    },
                    "if_match": {
                        "type": "integer",
                        "description": "Expected TODO revision before applying the change.",
                    },
                },
                "required": ["title"],
            },
            output_schema={"type": "object"},
            handler=_create,
        ),
        Tool(
            name="todo_update_task",
            description="Update the title, description, or status of an existing TODO item.",
            input_schema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Identifier of the task to update."},
                    "title": {"type": "string", "description": "Replacement title for the task."},
                    "description": {"type": "string", "description": "Replacement description."},
                    "status": {"type": "string", "enum": ["todo", "done"], "description": "Update the completion status."},
                    "show_todo_list": {
                        "type": "boolean",
                        "description": "Set true to request the CLI render the TODO list.",
                    },
                    "if_match": {
                        "type": "integer",
                        "description": "Expected TODO revision before applying the change.",
                    },
                },
                "required": ["task_id"],
            },
            output_schema={"type": "object"},
            handler=_update,
        ),
        Tool(
            name="todo_mark_complete",
            description="Mark a TODO item as done.",
            input_schema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Identifier of the task to complete."},
                    "show_todo_list": {
                        "type": "boolean",
                        "description": "Set true to request the CLI render the TODO list.",
                    },
                    "if_match": {
                        "type": "integer",
                        "description": "Expected TODO revision before applying the change.",
                    },
                },
                "required": ["task_id"],
            },
            output_schema={"type": "object"},
            handler=_complete,
        ),
        Tool(
            name="todo_remove_task",
            description="Remove a TODO item from the list.",
            input_schema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Identifier of the task to remove."},
                    "show_todo_list": {
                        "type": "boolean",
                        "description": "Set true to request the CLI render the TODO list.",
                    },
                    "if_match": {
                        "type": "integer",
                        "description": "Expected TODO revision before applying the change.",
                    },
                },
                "required": ["task_id"],
            },
            output_schema={"type": "object"},
            handler=_remove,
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
        description="Manage the agent's active TODO items.",
        tools=tools,
    )


__all__ = ["todo_toolkit"]
