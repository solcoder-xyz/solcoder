"""Slash command interface for the shared TODO manager."""

from __future__ import annotations

from typing import TYPE_CHECKING

from solcoder.cli.types import CommandResponse, CommandRouter, SlashCommand

if TYPE_CHECKING:  # pragma: no cover
    from solcoder.cli.app import CLIApp


USAGE = "Usage: /todo <add|update|done|remove|list|clear> [...options]"


def register(app: CLIApp, router: CommandRouter) -> None:
    """Register the `/todo` command group."""

    def handle(app: CLIApp, args: list[str]) -> CommandResponse:
        if not args:
            return CommandResponse(messages=[("system", USAGE)])

        action = args[0].lower()
        remainder = args[1:]

        if action == "add":
            return _handle_add(app, remainder)
        if action == "update":
            return _handle_update(app, remainder)
        if action in {"done", "complete"}:
            return _handle_done(app, remainder)
        if action in {"remove", "delete"}:
            return _handle_remove(app, remainder)
        if action == "list":
            return CommandResponse(messages=[("system", app.todo_manager.render())])
        if action == "clear":
            app.todo_manager.clear(expected_revision=app.todo_manager.revision)
            return CommandResponse(messages=[("system", "TODO list cleared.\n" + app.todo_manager.render())])
        if action in {"confirm", "confirm-remaining"}:
            return _handle_confirm(app)

        return CommandResponse(messages=[("system", USAGE)])

    router.register(SlashCommand("todo", handle, "Manage the shared TODO list"))


def _handle_add(app: "CLIApp", args: list[str]) -> CommandResponse:
    title, description = _parse_title_and_description(args)
    if not title:
        return CommandResponse(messages=[("system", "TODO add requires a title. Try `/todo add Fix bug --desc='details'`.")])
    try:
        task = app.todo_manager.create_task(
            title,
            description=description,
            expected_revision=app.todo_manager.revision,
        )
    except ValueError as exc:
        return CommandResponse(messages=[("system", str(exc))])
    message = [f"Task {task.id} added.", "", app.todo_manager.render()]
    return CommandResponse(messages=[("system", "\n".join(message))])


def _handle_update(app: "CLIApp", args: list[str]) -> CommandResponse:
    if not args:
        return CommandResponse(messages=[("system", "TODO update requires a task id." )])
    task_id = args[0]
    updates = _extract_updates(args[1:])
    if not updates:
        return CommandResponse(messages=[("system", "Provide at least one field to update (title, --desc, --status).")])
    try:
        app.todo_manager.update_task(
            task_id,
            title=updates.get("title"),
            description=updates.get("description"),
            status=updates.get("status"),
            expected_revision=app.todo_manager.revision,
        )
    except ValueError as exc:
        return CommandResponse(messages=[("system", str(exc))])
    message = [f"Task {task_id} updated.", "", app.todo_manager.render()]
    return CommandResponse(messages=[("system", "\n".join(message))])


def _handle_done(app: "CLIApp", args: list[str]) -> CommandResponse:
    if not args:
        return CommandResponse(messages=[("system", "TODO done requires a task id.")])
    task_id = args[0]
    try:
        app.todo_manager.mark_complete(task_id, expected_revision=app.todo_manager.revision)
    except ValueError as exc:
        return CommandResponse(messages=[("system", str(exc))])
    message = [f"Task {task_id} marked complete.", "", app.todo_manager.render()]
    return CommandResponse(messages=[("system", "\n".join(message))])


def _handle_remove(app: "CLIApp", args: list[str]) -> CommandResponse:
    if not args:
        return CommandResponse(messages=[("system", "TODO remove requires a task id.")])
    task_id = args[0]
    try:
        app.todo_manager.remove_task(task_id, expected_revision=app.todo_manager.revision)
    except ValueError as exc:
        return CommandResponse(messages=[("system", str(exc))])
    message = [f"Task {task_id} removed.", "", app.todo_manager.render()]
    return CommandResponse(messages=[("system", "\n".join(message))])


def _parse_title_and_description(args: list[str]) -> tuple[str, str | None]:
    title_parts: list[str] = []
    description: str | None = None
    it = iter(args)
    for token in it:
        if token.startswith("--desc="):
            description = token.split("=", 1)[1]
        elif token == "--desc":
            description = next(it, "")
        else:
            title_parts.append(token)
    title = " ".join(title_parts).strip()
    return title, (description.strip() if description else None)


def _extract_updates(args: list[str]) -> dict[str, str | None]:
    updates: dict[str, str | None] = {}
    it = iter(args)
    for token in it:
        if token.startswith("--title="):
            updates["title"] = token.split("=", 1)[1]
        elif token == "--title":
            updates["title"] = next(it, "")
        elif token.startswith("--desc="):
            updates["description"] = token.split("=", 1)[1]
        elif token == "--desc":
            updates["description"] = next(it, "")
        elif token.startswith("--status="):
            updates["status"] = token.split("=", 1)[1]
        elif token == "--status":
            updates["status"] = next(it, "")
    if "status" in updates and updates["status"] is not None:
        updates["status"] = updates["status"].strip().lower()
    return updates


__all__ = ["register"]
def _handle_confirm(app: "CLIApp") -> CommandResponse:
    if not app.todo_manager.tasks():
        return CommandResponse(messages=[("system", "TODO list already empty.")])
    app.todo_manager.acknowledge()
    message = ["Unfinished tasks acknowledged.", "", app.todo_manager.render()]
    return CommandResponse(messages=[("system", "\n".join(message))])
