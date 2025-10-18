from __future__ import annotations

import pytest

from solcoder.core.todo import TodoManager


def test_todo_manager_crud_and_render() -> None:
    manager = TodoManager()
    task = manager.create_task("Write docs", description="Outline new section")
    assert task.id == "T1"
    assert "Write docs" in manager.render()

    manager.update_task(task.id, title="Write README", description="Update quickstart")
    manager.mark_complete(task.id)
    output = manager.render()
    assert "[x] Write README" in output

    manager.remove_task(task.id)
    assert "No open tasks" in manager.render()


def test_update_validation() -> None:
    manager = TodoManager()
    task = manager.create_task("Investigate bug")
    with pytest.raises(ValueError):
        manager.update_task(task.id, status="blocked")  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        manager.update_task("missing", title="noop")

    manager.clear()
    assert manager.tasks() == []
