"""In-memory TODO manager shared by CLI and agent tooling."""

from __future__ import annotations

import itertools
from dataclasses import dataclass, asdict
from typing import Any, Iterable, Literal


TaskStatus = Literal["todo", "done"]


@dataclass(slots=True)
class TodoItem:
    """Single TODO entry tracked during an agent session."""

    id: str
    title: str
    description: str | None = None
    status: TaskStatus = "todo"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TodoManager:
    """Maintains the agent's current TODO list."""

    def __init__(self) -> None:
        self._counter = itertools.count(1)
        self._tasks: list[TodoItem] = []

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------
    def create_task(self, title: str, *, description: str | None = None) -> TodoItem:
        if not title or not title.strip():
            raise ValueError("Task title is required.")
        task = TodoItem(id=f"T{next(self._counter)}", title=title.strip(), description=description)
        self._tasks.append(task)
        return task

    def update_task(
        self,
        task_id: str,
        *,
        title: str | None = None,
        description: str | None = None,
        status: TaskStatus | None = None,
    ) -> TodoItem:
        task = self._find_task(task_id)
        if title is not None:
            if not title.strip():
                raise ValueError("Task title cannot be empty.")
            task.title = title.strip()
        if description is not None:
            task.description = description or None
        if status is not None:
            if status not in ("todo", "done"):
                raise ValueError("Task status must be 'todo' or 'done'.")
            task.status = status
        return task

    def mark_complete(self, task_id: str) -> TodoItem:
        task = self._find_task(task_id)
        task.status = "done"
        return task

    def remove_task(self, task_id: str) -> None:
        task = self._find_task(task_id)
        self._tasks.remove(task)

    def clear(self) -> None:
        self._tasks.clear()
        self._counter = itertools.count(1)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------
    def tasks(self) -> list[TodoItem]:
        return list(self._tasks)

    def as_dicts(self) -> list[dict[str, Any]]:
        return [task.to_dict() for task in self._tasks]

    def render(self, *, empty_message: str = "No open tasks.") -> str:
        lines = ["TODO List", "---------"]
        if not self._tasks:
            lines.append(empty_message)
            return "\n".join(lines)
        for idx, task in enumerate(self._tasks, start=1):
            marker = "[x]" if task.status == "done" else "[ ]"
            line = f"{idx}. {marker} {task.title}"
            if task.description:
                line = f"{line} — {task.description}"
            lines.append(line)
        return "\n".join(lines)

    def _find_task(self, task_id: str) -> TodoItem:
        for task in self._tasks:
            if task.id == task_id:
                return task
        raise ValueError(f"Task '{task_id}' not found.")


def serialize_tasks(tasks: Iterable[TodoItem]) -> list[dict[str, Any]]:
    """Return primitive representation of the provided tasks."""
    return [task.to_dict() for task in tasks]


__all__ = ["TodoManager", "TodoItem", "serialize_tasks"]
