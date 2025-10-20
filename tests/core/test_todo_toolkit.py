from __future__ import annotations

import pytest

from solcoder.core.todo import TodoManager
from solcoder.core.tool_registry import ToolRegistry
from solcoder.core.tools.todo import todo_toolkit
from solcoder.core.tools.base import ToolInvocationError


def test_todo_update_list_replaces_tasks() -> None:
    manager = TodoManager()
    registry = ToolRegistry()
    registry.add_toolkit(todo_toolkit(manager))

    initial = registry.invoke(
        "todo_update_list",
        {
            "tasks": [
                {"name": "Implement feature", "description": "Wire up CLI", "status": "in_progress"},
                {"name": "Document feature", "status": "todo"},
            ],
            "show_todo_list": True,
            "if_match": manager.revision,
        },
    )

    assert initial.data["show_todo_list"] is True
    assert initial.data["todo_render"] == "[[RENDER_TODO_PANEL]]"
    assert [task["status"] for task in initial.data["tasks"]] == ["in_progress", "todo"]

    implement_id = initial.data["tasks"][0]["id"]

    updated = registry.invoke(
        "todo_update_list",
        {
            "tasks": [
                {"id": implement_id, "name": "Implement feature", "status": "done"},
                {"name": "Write examples", "status": "in_progress"},
                {"name": "Document feature", "status": "todo"},
            ],
            "if_match": manager.revision,
        },
    )

    statuses = [task["status"] for task in updated.data["tasks"]]
    assert statuses == ["done", "in_progress", "todo"]
    assert manager.active_task_id == updated.data["tasks"][1]["id"]
    assert updated.data["active_task_id"] == manager.active_task_id


def test_todo_update_list_can_clear_and_use_clear_tool() -> None:
    manager = TodoManager()
    registry = ToolRegistry()
    registry.add_toolkit(todo_toolkit(manager))

    registry.invoke(
        "todo_update_list",
        {
            "tasks": [
                {"name": "Write tests", "status": "in_progress"},
                {"name": "Review fixtures", "status": "todo"},
            ],
            "if_match": manager.revision,
        },
    )
    assert len(manager.tasks()) == 2

    cleared = registry.invoke("todo_update_list", {"tasks": [], "if_match": manager.revision})
    assert cleared.data["tasks"] == []
    assert manager.tasks() == []

    registry.invoke(
        "todo_update_list",
        {
            "tasks": [
                {"name": "Lint", "status": "in_progress"},
                {"name": "Update docs", "status": "todo"},
            ],
            "if_match": manager.revision,
        },
    )
    registry.invoke("todo_clear_tasks", {"if_match": manager.revision})
    assert manager.tasks() == []


def test_todo_update_list_rejects_single_task_payload() -> None:
    manager = TodoManager()
    registry = ToolRegistry()
    registry.add_toolkit(todo_toolkit(manager))

    with pytest.raises(ToolInvocationError) as excinfo:
        registry.invoke(
            "todo_update_list",
            {
                "tasks": [{"name": "Inspect file", "status": "todo"}],
                "if_match": manager.revision,
            },
        )
    assert "TODO_SINGLE_ITEM_NOT_ALLOWED" in str(excinfo.value)
