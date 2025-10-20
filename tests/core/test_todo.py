from __future__ import annotations

import pytest

from solcoder.core.todo import TodoManager


def test_todo_manager_lifecycle_and_render() -> None:
    manager = TodoManager()
    first = manager.create_task("Write docs", description="Outline new section")
    assert first.id == "T1"
    assert first.status == "in_progress"
    assert manager.active_task_id == first.id

    second = manager.create_task("Review tests")
    assert second.status == "todo"
    assert manager.active_task_id == first.id

    manager.set_active(second.id)
    assert second.status == "in_progress"
    assert first.status == "todo"
    assert manager.active_task_id == second.id

    manager.mark_complete(second.id)
    assert second.status == "done"
    assert manager.active_task_id == first.id

    manager.update_task(first.id, title="Write README", description="Update quickstart")
    manager.mark_complete(first.id)
    assert first.status == "done"
    assert manager.active_task_id is None

    output = manager.render_plain()
    assert "[x]" in output

    manager.remove_task(first.id)
    manager.remove_task(second.id)
    assert "No open tasks" in manager.render_plain()


def test_update_validation_and_single_active_guard() -> None:
    manager = TodoManager()
    task = manager.create_task("Investigate bug")

    with pytest.raises(ValueError):
        manager.update_task(task.id, status="blocked")  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        manager.update_task("missing", title="noop")

    reopened = manager.update_task(task.id, status="todo")
    assert reopened.status == "in_progress"  # guard ensures active task remains

    manager.clear()
    assert manager.tasks() == []


def test_replace_tasks_rejects_single_item_payload() -> None:
    manager = TodoManager()
    with pytest.raises(ValueError) as excinfo:
        manager.replace_tasks([{"name": "Only item", "status": "todo"}])
    assert "TODO_SINGLE_ITEM_NOT_ALLOWED" in str(excinfo.value)


def test_clear_if_all_done_only_clears_on_completion() -> None:
    manager = TodoManager()
    task_a = manager.create_task("Ship feature")
    task_b = manager.create_task("Write docs")
    assert manager.clear_if_all_done() is False

    manager.mark_complete(task_a.id)
    assert manager.clear_if_all_done() is False

    manager.mark_complete(task_b.id)
    assert manager.clear_if_all_done() is True
    assert manager.tasks() == []
