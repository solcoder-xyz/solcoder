"""Slash command interface for the shared TODO manager."""

from __future__ import annotations

from typing import TYPE_CHECKING

from solcoder.cli.types import CommandResponse, CommandRouter, SlashCommand

if TYPE_CHECKING:  # pragma: no cover
    from solcoder.cli.app import CLIApp


USAGE = (
    "Usage: /todo <add|update|start|done|remove|list|clear|confirm> [...options]\n"
    "Examples:\n"
    "  /todo add Fix bug --desc 'repro steps'\n"
    "  /todo update T1 --title 'Refactor' --status in_progress\n"
    "  /todo start T2\n"
    "  /todo done T2\n"
    "  /todo confirm"
)

ALLOWED_STATUS = {"pending", "in_progress", "done"}


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
        if action in {"start", "activate", "focus"}:
            return _handle_start(app, remainder)
        if action == "list":
            render = app.todo_manager.render()
            return CommandResponse(messages=[("system", render)])
        if action == "clear":
            app.todo_manager.clear(expected_revision=app.todo_manager.revision)
            return CommandResponse(messages=[("system", "TODO list cleared.\n" + app.todo_manager.render())])
        if action in {"confirm", "confirm-remaining"}:
            return _handle_confirm(app)

        return CommandResponse(messages=[("system", USAGE)])

    router.register(SlashCommand("todo", handle, "Manage the shared TODO list"))


def _handle_add(app: "CLIApp", args: list[str]) -> CommandResponse:
    try:
        title, description = _parse_title_and_description(args)
    except ValueError as exc:
        return CommandResponse(messages=[("system", str(exc))])
    if not title:
        return CommandResponse(messages=[("system", "TODO add requires a non-empty title. Try `/todo add Fix bug --desc 'details'`.")])
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
        return CommandResponse(messages=[("system", "TODO update requires a task id.")])
    task_id = args[0]
    try:
        updates = _extract_updates(args[1:])
    except ValueError as exc:
        return CommandResponse(messages=[("system", str(exc))])
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


def _handle_start(app: "CLIApp", args: list[str]) -> CommandResponse:
    if not args:
        return CommandResponse(messages=[("system", "TODO start requires a task id.")])
    task_id = args[0]
    try:
        app.todo_manager.set_active(task_id, expected_revision=app.todo_manager.revision)
    except ValueError as exc:
        return CommandResponse(messages=[("system", str(exc))])
    message = [f"Task {task_id} is now in progress.", "", app.todo_manager.render()]
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
        if token in {"--desc", "--description"}:
            value = next(it, None)
            if value is None or value.startswith("--"):
                raise ValueError("Missing value for --desc.")
            description = value
        elif token.startswith("--desc=") or token.startswith("--description="):
            description = token.split("=", 1)[1]
        else:
            title_parts.append(token)
    title = " ".join(title_parts).strip()
    if description is not None:
        description = description.strip()
    return title, (description if description else None)


def _extract_updates(args: list[str]) -> dict[str, str | None]:
    updates: dict[str, str | None] = {}
    it = iter(args)
    for token in it:
        if token in {"--title", "-t"}:
            value = next(it, None)
            if value is None or value.startswith("--"):
                raise ValueError("Missing value for --title.")
            updates["title"] = value
        elif token.startswith("--title="):
            updates["title"] = token.split("=", 1)[1]
        elif token in {"--desc", "--description", "-d"}:
            value = next(it, None)
            if value is None or value.startswith("--"):
                raise ValueError("Missing value for --desc.")
            updates["description"] = value
        elif token.startswith("--desc=") or token.startswith("--description="):
            updates["description"] = token.split("=", 1)[1]
        elif token == "--status":
            value = next(it, None)
            if value is None or value.startswith("--"):
                raise ValueError("Missing value for --status.")
            updates["status"] = value
        elif token.startswith("--status="):
            updates["status"] = token.split("=", 1)[1]
    if updates.get("title") is not None:
        updates["title"] = updates["title"].strip() or None
    if updates.get("description") is not None:
        updates["description"] = updates["description"].strip()
    if updates.get("status") is not None:
        status = updates["status"].strip().lower()
        if status not in ALLOWED_STATUS:
            raise ValueError(f"Invalid status '{status}'. Allowed values: {', '.join(sorted(ALLOWED_STATUS))}.")
        updates["status"] = status
    return {key: value for key, value in updates.items() if value is not None}


__all__ = ["register"]
def _handle_confirm(app: "CLIApp") -> CommandResponse:
    if not app.todo_manager.tasks():
        return CommandResponse(messages=[("system", "TODO list already empty.")])
    app.todo_manager.acknowledge()
    message = ["Unfinished tasks acknowledged.", "", app.todo_manager.render()]
    return CommandResponse(messages=[("system", "\n".join(message))])
