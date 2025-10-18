from __future__ import annotations

from solcoder.core.todo import TodoManager
from solcoder.core.tool_registry import ToolRegistry
from solcoder.core.tools.todo import todo_toolkit


def test_todo_toolkit_add_and_show() -> None:
    manager = TodoManager()
    registry = ToolRegistry()
    registry.add_toolkit(todo_toolkit(manager))

    result = registry.invoke(
        "todo_add_task",
        {
            "title": "Implement feature",
            "description": "Wire up CLI",
            "show_todo_list": True,
            "if_match": manager.revision,
        },
    )

    assert result.data["show_todo_list"] is True
    assert result.data["todo_render"] == "[[RENDER_TODO_PANEL]]"
    assert len(result.data["tasks"]) == 1
    assert result.data["tasks"][0]["status"] == "in_progress"
    assert result.data["active_task_id"] == result.data["tasks"][0]["id"]

    second_result = registry.invoke(
        "todo_add_task",
        {
            "title": "Document feature",
            "if_match": manager.revision,
        },
    )
    second_id = second_result.data["tasks"][-1]["id"]
    activate_result = registry.invoke(
        "todo_set_active_task",
        {
            "task_id": second_id,
            "if_match": manager.revision,
        },
    )
    assert activate_result.data["active_task_id"] == second_id
    assert manager.active_task_id == second_id
    duplicate_error = None
    try:
        registry.invoke(
            "todo_add_task",
            {"title": "Implement feature", "if_match": manager.revision},
        )
    except Exception as exc:  # noqa: BLE001
        duplicate_error = str(exc)
    assert duplicate_error and "already exists" in duplicate_error


def test_todo_toolkit_mark_and_clear() -> None:
    manager = TodoManager()
    registry = ToolRegistry()
    registry.add_toolkit(todo_toolkit(manager))

    add_result = registry.invoke("todo_add_task", {"title": "Write tests", "if_match": manager.revision})
    task_id = add_result.data["tasks"][0]["id"]
    revision = add_result.data["revision"]

    registry.invoke("todo_mark_complete", {"task_id": task_id, "if_match": revision})
    assert manager.tasks()[0].status == "done"

    registry.invoke("todo_clear_tasks", {"if_match": manager.revision})
    assert manager.tasks() == []
