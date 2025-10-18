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
    assert second.status == "pending"
    assert manager.active_task_id == first.id

    manager.set_active(second.id)
    assert second.status == "in_progress"
    assert first.status == "pending"
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

    reopened = manager.update_task(task.id, status="pending")
    assert reopened.status == "in_progress"  # guard ensures active task remains

    manager.clear()
    assert manager.tasks() == []
