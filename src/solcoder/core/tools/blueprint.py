"""Blueprint scaffolding tool to hand off file creation to the CLI via dispatch."""

from __future__ import annotations

from typing import Any
from pathlib import Path
import json
import shlex

from solcoder.core.tools.base import Tool, ToolInvocationError, Toolkit, ToolResult


def _scaffold_handler(payload: dict[str, Any]) -> ToolResult:
    key = payload.get("blueprint_key")
    target_dir = payload.get("target_dir")
    workspace_root = payload.get("workspace_root")
    answers = payload.get("answers") or {}
    if not isinstance(key, str) or not key:
        raise ToolInvocationError("'blueprint_key' is required")
    if not isinstance(target_dir, str) or not target_dir:
        raise ToolInvocationError("'target_dir' is required")
    if not isinstance(answers, (dict, list)):
        raise ToolInvocationError("'answers' must be an object or array")
    parts = ["/blueprint", "scaffold", "--key", key, "--target", target_dir]
    if isinstance(workspace_root, str) and workspace_root:
        parts += ["--workspace", workspace_root]
    try:
        answers_json = json.dumps(answers, separators=(",", ":"))
    except Exception as exc:  # noqa: BLE001
        raise ToolInvocationError(f"Unable to serialize answers: {exc}") from exc
    parts += ["--answers-json", answers_json]
    cmd = " ".join(shlex.quote(p) for p in parts)
    return ToolResult(
        content=f"Scaffolding blueprint via: {cmd}",
        summary="Scaffold blueprint",
        data={"dispatch_command": cmd, "suppress_preview": True},
    )


def _create_program_handler(payload: dict[str, Any]) -> ToolResult:
    key = payload.get("blueprint_key")
    program_name = payload.get("program_name")
    answers = payload.get("answers") or {}
    if not isinstance(key, str) or not key:
        raise ToolInvocationError("'blueprint_key' is required")
    if not isinstance(program_name, str) or not program_name:
        raise ToolInvocationError("'program_name' is required")
    if not isinstance(answers, dict):
        raise ToolInvocationError("'answers' must be an object")
    # Merge essential answers
    merged = dict(answers)
    merged.setdefault("program_name", program_name)
    parts = [
        "/blueprint",
        "scaffold",
        "--key",
        key,
        "--target",
        ".",
        "--workspace",
        "auto",
    ]
    try:
        answers_json = json.dumps(merged, separators=(",", ":"))
    except Exception as exc:  # noqa: BLE001
        raise ToolInvocationError(f"Unable to serialize answers: {exc}") from exc
    parts += ["--answers-json", answers_json]
    cmd = " ".join(shlex.quote(p) for p in parts)
    return ToolResult(
        content=f"Create program blueprint via: {cmd}",
        summary="Create program blueprint in active workspace",
        data={"dispatch_command": cmd, "suppress_preview": True},
    )


def _get_wizard_questions_handler(payload: dict[str, Any]) -> ToolResult:
    key = payload.get("blueprint_key")
    if not isinstance(key, str) or not key:
        raise ToolInvocationError("'blueprint_key' is required")
    try:
        from solcoder.cli.blueprints import load_wizard_schema  # lazy import to avoid cycles

        questions = load_wizard_schema(key)
    except Exception as exc:  # noqa: BLE001
        raise ToolInvocationError(f"Unable to load wizard schema for '{key}': {exc}") from exc
    return ToolResult(
        content=f"Wizard questions for '{key}' loaded ({len(questions)} items).",
        summary="Loaded wizard questions",
        data={"questions": questions},
    )


def _find_anchor_root(start: Path) -> Path | None:
    try:
        cur = start.resolve()
    except Exception:
        cur = start.expanduser()
    for parent in [cur, *cur.parents]:
        if (parent / "Anchor.toml").exists():
            return parent
    return None


def _check_program_exists_handler(payload: dict[str, Any]) -> ToolResult:
    program_name = payload.get("program_name")
    workspace_root_val = payload.get("workspace_root")
    if not isinstance(program_name, str) or not program_name.strip():
        raise ToolInvocationError("'program_name' is required")
    workspace_root: Path | None = None
    if isinstance(workspace_root_val, str) and workspace_root_val.strip():
        workspace_root = Path(workspace_root_val).expanduser()
    if workspace_root is None:
        # Try to detect from a persisted active workspace file in project .solcoder
        def _find_active_workspace_file(start: Path) -> Path | None:
            try:
                cur = start.resolve()
            except Exception:
                cur = start.expanduser()
            for parent in [cur, *cur.parents]:
                candidate = parent / ".solcoder" / "active_workspace"
                if candidate.exists():
                    return candidate
            return None

        aw_file = _find_active_workspace_file(Path.cwd())
        if aw_file is not None:
            try:
                text = (aw_file.read_text() or "").strip()
                if text:
                    p = Path(text).expanduser()
                    if (p / "Anchor.toml").exists():
                        workspace_root = p
            except Exception:
                workspace_root = None
    if workspace_root is None:
        workspace_root = _find_anchor_root(Path.cwd())
    if workspace_root is None:
        return ToolResult(
            content="No Anchor workspace detected from current directory.",
            summary="Workspace not found",
            data={"exists": False, "workspace_root": None, "path": None},
        )
    candidate = workspace_root / "programs" / program_name
    exists = candidate.exists()
    return ToolResult(
        content=(
            f"Workspace: {workspace_root}\n"
            + (f"Program exists: {candidate}" if exists else f"Program not found: {candidate}")
        ),
        summary="Program existence checked",
        data={"exists": exists, "workspace_root": str(workspace_root), "path": str(candidate)},
    )


def blueprint_toolkit() -> Toolkit:
    return Toolkit(
        name="solcoder.blueprint",
        version="1.0.0",
        description="Agent handoff for blueprint scaffolding.",
        tools=[
            Tool(
                name="scaffold_blueprint",
                description=(
                    "Scaffold files for a blueprint by dispatching a CLI command. "
                    "Args: blueprint_key, target_dir, workspace_root?, answers (object)."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "blueprint_key": {"type": "string"},
                        "target_dir": {"type": "string"},
                        "workspace_root": {"type": "string"},
                        "answers": {"type": "object"}
                    },
                    "required": ["blueprint_key", "target_dir", "answers"],
                },
                output_schema={"type": "object"},
                handler=_scaffold_handler,
            ),
            Tool(
                name="create_program_blueprint",
                description=(
                    "Create a blueprint program under the active Anchor workspace's programs/. "
                    "Args: blueprint_key, program_name, answers (object)."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "blueprint_key": {"type": "string"},
                        "program_name": {"type": "string"},
                        "answers": {"type": "object"},
                    },
                    "required": ["blueprint_key", "program_name"],
                },
                output_schema={"type": "object"},
                handler=_create_program_handler,
            ),
            Tool(
                name="get_wizard_questions",
                description=(
                    "Load the interactive wizard questions for a blueprint key so the agent can collect required params."
                ),
                input_schema={
                    "type": "object",
                    "properties": {"blueprint_key": {"type": "string"}},
                    "required": ["blueprint_key"],
                },
                output_schema={"type": "object"},
                handler=_get_wizard_questions_handler,
            ),
            Tool(
                name="check_program_exists",
                description=(
                    "Check if a program folder already exists under the active Anchor workspace's programs/. "
                    "Args: program_name, workspace_root?"
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "program_name": {"type": "string"},
                        "workspace_root": {"type": "string"},
                    },
                    "required": ["program_name"],
                },
                output_schema={"type": "object"},
                handler=_check_program_exists_handler,
            ),
        ],
    )


__all__ = ["blueprint_toolkit"]
