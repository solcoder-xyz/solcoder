"""In-memory TODO manager shared by CLI and agent tooling."""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass
from typing import Any, Iterable, Literal


TRAILING_PUNCTUATION = ".,;:!?"


def _normalize_title(title: str) -> str:
    collapsed = re.sub(r"\s+", " ", title.strip())
    stripped = collapsed.rstrip(TRAILING_PUNCTUATION)
    return stripped.lower()


def _is_management_task(normalized_title: str) -> bool:
    if "todo" not in normalized_title:
        return False
    phrases = [
        "todo list",
        "review the todo",
        "review current todo",
        "mark the todo",
        "manage the todo",
        "acknowledge remaining todo",
        "acknowledge the todo",
    ]
    return any(phrase in normalized_title for phrase in phrases)


TaskStatus = Literal["todo", "in_progress", "done"]


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
        if _is_management_task(normalized):
            raise ValueError("Task describes TODO management and was skipped.")
        if self._check_revision(expected_revision):
            raise ValueError("TODO list has changed. Refresh tasks and retry.")
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
        if not any(
            existing.status == "in_progress"
            for existing in self._tasks
            if existing is not task and existing.status != "done"
        ):
            task.status = "in_progress"
        self._normalize_active_state()
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
        if self._check_revision(expected_revision):
            raise ValueError("TODO list has changed. Refresh tasks and retry.")
        task = self._find_task(task_id)
        if title is not None:
            if not title.strip():
                raise ValueError("Task title cannot be empty.")
            normalized = _normalize_title(title)
            if _is_management_task(normalized):
                raise ValueError("Task describes TODO management and was skipped.")
            duplicate = self._find_duplicate(normalized)
            if duplicate and duplicate.id != task.id and duplicate.status != "done":
                raise ValueError(f"Task already exists: {duplicate.id}")
            task.title = title.strip()
            task.normalized_title = normalized
        if description is not None:
            task.description = description or None
        if status is not None:
            self._apply_status(task, status)
        self._touch()
        return task

    def mark_complete(self, task_id: str, *, expected_revision: int | None = None) -> TodoItem:
        if self._check_revision(expected_revision):
            raise ValueError("TODO list has changed. Refresh tasks and retry.")
        task = self._find_task(task_id)
        self._apply_status(task, "done")
        self._touch()
        return task

    def set_active(self, task_id: str, *, expected_revision: int | None = None) -> TodoItem:
        if self._check_revision(expected_revision):
            raise ValueError("TODO list has changed. Refresh tasks and retry.")
        task = self._find_task(task_id)
        if task.status == "done":
            raise ValueError("Completed tasks cannot be set active.")
        self._set_active_task(task)
        self._touch()
        return task

    def remove_task(self, task_id: str, *, expected_revision: int | None = None) -> None:
        if self._check_revision(expected_revision):
            raise ValueError("TODO list has changed. Refresh tasks and retry.")
        task = self._find_task(task_id)
        was_active = task.status == "in_progress"
        self._tasks.remove(task)
        if was_active:
            self._ensure_active_task()
        self._touch()

    def replace_tasks(
        self,
        tasks: Iterable[dict[str, Any]] | None,
        *,
        expected_revision: int | None = None,
    ) -> list[TodoItem]:
        if self._check_revision(expected_revision):
            raise ValueError("TODO list has changed. Refresh tasks and retry.")

        payload = list(tasks or [])
        if not payload:
            self._tasks.clear()
            self._counter = itertools.count(1)
            self._touch()
            return []
        if len(payload) == 1:
            raise ValueError(
                "TODO_SINGLE_ITEM_NOT_ALLOWED: Provide either zero tasks or two or more milestones."
            )

        current_max = self._max_numeric_id()
        seen_ids: set[str] = set()
        seen_titles: dict[str, TodoItem] = {}
        in_progress_count = 0
        new_tasks: list[TodoItem] = []

        for entry in payload:
            if not isinstance(entry, dict):
                raise ValueError("Each task must be an object with 'name'/'title' and 'status'.")
            title = str(entry.get("name") or entry.get("title") or "").strip()
            if not title:
                raise ValueError("Task title is required.")
            normalized_title = _normalize_title(title)
            if _is_management_task(normalized_title):
                raise ValueError("Task describes TODO management and was skipped.")
            description = entry.get("description")
            description_text = None
            if description is not None:
                as_text = str(description).strip()
                description_text = as_text or None
            status = self._normalize_status_value(entry.get("status"))
            if status == "in_progress":
                in_progress_count += 1
            existing = seen_titles.get(normalized_title)
            if existing and existing.status != "done" and status != "done":
                raise ValueError(f"Task already exists: {existing.id}")

            provided_id = entry.get("id")
            task_id = str(provided_id).strip() if provided_id is not None else ""
            if task_id:
                if task_id in seen_ids:
                    raise ValueError(f"Duplicate task id '{task_id}'.")
                seen_ids.add(task_id)
                if task_id.startswith("T"):
                    try:
                        numeric = int(task_id[1:])
                    except ValueError:
                        pass
                    else:
                        if numeric > current_max:
                            current_max = numeric
            else:
                current_max += 1
                task_id = f"T{current_max}"
                seen_ids.add(task_id)

            todo_item = TodoItem(
                id=task_id,
                title=title,
                description=description_text,
                status=status,
                normalized_title=normalized_title,
            )
            seen_titles[normalized_title] = todo_item
            new_tasks.append(todo_item)

        if in_progress_count > 1:
            raise ValueError("Provide at most one task with status 'in_progress'.")

        self._tasks = new_tasks
        self._counter = itertools.count(current_max + 1)
        self._normalize_active_state(ensure_active=in_progress_count == 0)
        self._touch()
        return list(self._tasks)

    def clear(self, *, expected_revision: int | None = None) -> None:
        if self._check_revision(expected_revision):
            raise ValueError("TODO list has changed. Refresh tasks and retry.")
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
        """Render TODO list as a Rich-compatible format marker.

        Returns a special marker that tells the renderer to use create_todo_panel().
        """
        # Return a special marker that the app can detect and replace with a Rich panel
        return "[[RENDER_TODO_PANEL]]"

    def render_plain(self, *, empty_message: str = "No open tasks.") -> str:
        """Legacy plain-text rendering for backward compatibility."""
        lines = ["TODO List", "---------"]
        if not self._tasks:
            lines.append(empty_message)
            return "\n".join(lines)
        status_symbols = {
            "todo": "[ ]",
            "in_progress": "[>]",
            "done": "[x]",
        }
        for idx, task in enumerate(self._tasks, start=1):
            marker = status_symbols.get(task.status, "[ ]")
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

    def dump_state(self) -> dict[str, Any]:
        return {
            "tasks": [task.to_dict() for task in self._tasks],
            "revision": self.revision,
            "acknowledged": self._acknowledged,
        }

    def load_state(self, state: dict[str, Any]) -> None:
        tasks_raw = state.get("tasks") or []
        if not isinstance(tasks_raw, list):
            tasks_raw = []
        tasks: list[TodoItem] = []
        max_index = 0
        for entry in tasks_raw:
            if not isinstance(entry, dict):
                continue
            title = str(entry.get("title") or "").strip()
            if not title:
                continue
            normalized = _normalize_title(title)
            if _is_management_task(normalized):
                continue
            task_id = str(entry.get("id") or "")
            if not task_id:
                task_id = f"T{len(tasks) + 1}"
            description = entry.get("description")
            if description is not None:
                description = str(description)
            status = self._normalize_status_value(entry.get("status"))
            todo_item = TodoItem(
                id=task_id,
                title=title,
                description=description,
                status=status,
                normalized_title=normalized,
            )
            tasks.append(todo_item)
            if task_id.startswith("T"):
                try:
                    max_index = max(max_index, int(task_id[1:]))
                except ValueError:
                    continue

        next_index = max(max_index + 1, len(tasks) + 1)
        self._tasks = tasks
        self._counter = itertools.count(next_index)
        self.revision = int(state.get("revision", len(tasks)))
        self._acknowledged = bool(state.get("acknowledged", False))
        self._last_revision_mismatch = False
        ensure_active = not any(task.status == "in_progress" for task in tasks)
        self._normalize_active_state(ensure_active=ensure_active)

    def _apply_status(self, task: TodoItem, status: TaskStatus) -> None:
        if status not in ("todo", "in_progress", "done"):
            raise ValueError("Task status must be 'todo', 'in_progress', or 'done'.")
        if status == task.status:
            return
        if status == "in_progress":
            if task.status == "done":
                raise ValueError("Completed tasks cannot be marked in progress.")
            self._set_active_task(task)
        elif status == "done":
            task.status = "done"
            self._ensure_active_task()
        else:
            task.status = "todo"
            self._ensure_active_task()

    def _set_active_task(self, task: TodoItem) -> None:
        if task.status == "done":
            raise ValueError("Completed tasks cannot be set active.")
        for other in self._tasks:
            if other.id != task.id and other.status == "in_progress":
                other.status = "todo"
        task.status = "in_progress"

    def _ensure_active_task(self) -> None:
        if any(task.status == "in_progress" for task in self._tasks if task.status != "done"):
            return
        for task in self._tasks:
            if task.status == "todo":
                task.status = "in_progress"
                break

    def _normalize_active_state(self, *, ensure_active: bool = True) -> None:
        active_found = False
        for task in self._tasks:
            if task.status == "in_progress":
                if active_found:
                    task.status = "todo"
                else:
                    active_found = True
        if not active_found and ensure_active and self._tasks:
            self._ensure_active_task()

    def active_task(self) -> TodoItem | None:
        for task in self._tasks:
            if task.status == "in_progress":
                return task
        return None

    @property
    def active_task_id(self) -> str | None:
        active = self.active_task()
        return active.id if active else None

    def _max_numeric_id(self) -> int:
        max_index = 0
        for task in self._tasks:
            if task.id.startswith("T"):
                try:
                    numeric = int(task.id[1:])
                except ValueError:
                    continue
                if numeric > max_index:
                    max_index = numeric
        return max_index

    @staticmethod
    def _normalize_status_value(value: Any) -> TaskStatus:
        if value is None:
            return "todo"
        raw = str(value).strip().lower()
        if not raw:
            return "todo"
        if raw in {"todo", "pending", "backlog"}:
            return "todo"
        if raw in {"in_progress", "in progress", "in-progress", "active", "progress"}:
            return "in_progress"
        if raw in {"done", "complete", "completed", "finished"}:
            return "done"
        raise ValueError("Task status must be 'todo', 'in_progress', or 'done'.")

    def clear_if_all_done(self) -> bool:
        """Clear the list when every tracked task is already complete."""
        if not self._tasks:
            return False
        if any(task.status != "done" for task in self._tasks):
            return False
        self.clear()
        return True


def serialize_tasks(tasks: Iterable[TodoItem]) -> list[dict[str, Any]]:
    """Return primitive representation of the provided tasks."""
    return [task.to_dict() for task in tasks]


__all__ = ["TodoManager", "TodoItem", "serialize_tasks"]
