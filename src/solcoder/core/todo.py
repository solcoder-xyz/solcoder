"""In-memory TODO manager shared by CLI and agent tooling."""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Any, Iterable, Literal


def _normalize_title(title: str) -> str:
    return " ".join(title.strip().split()).lower()


TaskStatus = Literal["todo", "done"]


@dataclass(slots=True)
class TodoItem:
    """Single TODO entry tracked during an agent session."""

    id: str
    title: str
    description: str | None = None
    status: TaskStatus = "todo"
    normalized_title: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
        }


class TodoManager:
    """Maintains the agent's current TODO list."""

    def __init__(self) -> None:
        self._counter = itertools.count(1)
        self._tasks: list[TodoItem] = []
        self.revision = 0
        self._acknowledged = False
        self._last_revision_mismatch = False

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------
    def create_task(
        self,
        title: str,
        *,
        description: str | None = None,
        expected_revision: int | None = None,
    ) -> TodoItem:
        if not title or not title.strip():
            raise ValueError("Task title is required.")
        normalized = _normalize_title(title)
        self._check_revision(expected_revision)
        duplicate = self._find_duplicate(normalized)
        if duplicate and duplicate.status != "done":
            raise ValueError(f"Task already exists: {duplicate.id}")
        task = TodoItem(
            id=f"T{next(self._counter)}",
            title=title.strip(),
            description=description,
            normalized_title=normalized,
        )
        self._tasks.append(task)
        self._touch()
        return task

    def update_task(
        self,
        task_id: str,
        *,
        title: str | None = None,
        description: str | None = None,
        status: TaskStatus | None = None,
        expected_revision: int | None = None,
    ) -> TodoItem:
        self._check_revision(expected_revision)
        task = self._find_task(task_id)
        if title is not None:
            if not title.strip():
                raise ValueError("Task title cannot be empty.")
            normalized = _normalize_title(title)
            duplicate = self._find_duplicate(normalized)
            if duplicate and duplicate.id != task.id and duplicate.status != "done":
                raise ValueError(f"Task already exists: {duplicate.id}")
            task.title = title.strip()
            task.normalized_title = normalized
        if description is not None:
            task.description = description or None
        if status is not None:
            if status not in ("todo", "done"):
                raise ValueError("Task status must be 'todo' or 'done'.")
            task.status = status
        self._touch()
        return task

    def mark_complete(self, task_id: str, *, expected_revision: int | None = None) -> TodoItem:
        self._check_revision(expected_revision)
        task = self._find_task(task_id)
        task.status = "done"
        self._touch()
        return task

    def remove_task(self, task_id: str, *, expected_revision: int | None = None) -> None:
        self._check_revision(expected_revision)
        task = self._find_task(task_id)
        self._tasks.remove(task)
        self._touch()

    def clear(self, *, expected_revision: int | None = None) -> None:
        self._check_revision(expected_revision)
        self._tasks.clear()
        self._counter = itertools.count(1)
        self._touch()

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

    def _find_duplicate(self, normalized_title: str) -> TodoItem | None:
        for task in self._tasks:
            if task.normalized_title == normalized_title:
                return task
        return None

    def _touch(self) -> None:
        self.revision += 1
        self._acknowledged = False

    def _check_revision(self, expected_revision: int | None) -> bool:
        mismatch = False
        if expected_revision is not None:
            try:
                expected_int = int(expected_revision)
            except (TypeError, ValueError):
                mismatch = True
            else:
                mismatch = expected_int != self.revision
        self._last_revision_mismatch = mismatch
        return mismatch

    def pop_revision_mismatch(self) -> bool:
        mismatch = self._last_revision_mismatch
        self._last_revision_mismatch = False
        return mismatch

    def acknowledge(self) -> None:
        self._acknowledged = True

    @property
    def acknowledged(self) -> bool:
        return self._acknowledged

    def has_unfinished_tasks(self) -> bool:
        return any(task.status != "done" for task in self._tasks)

    def unfinished_tasks(self) -> list[TodoItem]:
        return [task for task in self._tasks if task.status != "done"]

    def acknowledge_if_empty(self) -> None:
        if not self._tasks:
            self._acknowledged = True


def serialize_tasks(tasks: Iterable[TodoItem]) -> list[dict[str, Any]]:
    """Return primitive representation of the provided tasks."""
    return [task.to_dict() for task in tasks]


__all__ = ["TodoManager", "TodoItem", "serialize_tasks"]
