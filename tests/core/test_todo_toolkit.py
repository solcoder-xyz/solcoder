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
        {"title": "Implement feature", "description": "Wire up CLI", "show_todo_list": True},
    )

    assert result.data["show_todo_list"] is True
    assert "[ ]" in result.data["todo_render"]
    assert len(result.data["tasks"]) == 1


def test_todo_toolkit_mark_and_clear() -> None:
    manager = TodoManager()
    registry = ToolRegistry()
    registry.add_toolkit(todo_toolkit(manager))

    add_result = registry.invoke("todo_add_task", {"title": "Write tests"})
    task_id = add_result.data["tasks"][0]["id"]

    registry.invoke("todo_mark_complete", {"task_id": task_id})
    render = manager.render()
    assert "[x]" in render

    registry.invoke("todo_clear_tasks", {})
    assert manager.tasks() == []
