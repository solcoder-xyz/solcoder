"""Agent loop orchestration for the SolCoder CLI."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from rich.console import Console

from solcoder.core import (
    AgentMessageError,
    AgentToolResult,
    ConfigContext,
    build_tool_manifest,
    manifest_to_prompt_section,
    parse_agent_directive,
)
from solcoder.core.todo import TodoManager, _normalize_title as _todo_normalize_title
from solcoder.core.tool_registry import ToolRegistry, ToolRegistryError
from solcoder.session import SessionMetadata

DEFAULT_AGENT_MAX_ITERATIONS = 1000
AGENT_PLAN_ACK = json.dumps({"type": "plan_ack", "status": "ready"})

if TYPE_CHECKING:  # pragma: no cover
    from solcoder.cli.types import CommandResponse, LLMBackend


@dataclass
class AgentLoopContext:
    """Encapsulates shared state required by the agent loop."""

    prompt: str
    history: Sequence[dict[str, str]]
    llm: "LLMBackend"
    tool_registry: ToolRegistry
    console: Console
    config_context: ConfigContext | None
    session_metadata: SessionMetadata
    render_message: Callable[[str, str], None]
    todo_manager: TodoManager | None = None
    initial_todo_message: str | None = None
    max_iterations: int = DEFAULT_AGENT_MAX_ITERATIONS


def run_agent_loop(ctx: AgentLoopContext) -> "CommandResponse":
    """Execute the agent loop using the provided context."""
    from solcoder.cli.types import CommandResponse  # Local import to avoid circular dependency

    manifest = build_tool_manifest(ctx.tool_registry)
    manifest_json = manifest_to_prompt_section(manifest)
    system_prompt = _agent_system_prompt(ctx.config_context, manifest_json)

    loop_history = list(ctx.history)
    if ctx.initial_todo_message:
        loop_history.append({"role": "system", "content": ctx.initial_todo_message})
    pending_prompt = ctx.prompt
    plan_received = False
    rendered_roles: set[str] = set()
    display_messages: list[tuple[str, str]] = []
    tool_summaries: list[dict[str, Any]] = []
    total_latency = 0.0
    total_input_tokens = 0
    total_output_tokens = 0
    last_finish_reason: str | None = None
    all_cached = True
    retry_payload: str | None = None

    provider_name, model_name, reasoning_effort = _active_model_details(ctx.config_context)

    def _accumulate_usage(result: Any) -> None:
        nonlocal total_latency, total_input_tokens, total_output_tokens, last_finish_reason, all_cached
        total_latency += getattr(result, "latency_seconds", 0.0)
        finish = getattr(result, "finish_reason", None)
        if finish:
            last_finish_reason = finish
        if not getattr(result, "cached", False):
            all_cached = False
        token_usage = getattr(result, "token_usage", None)
        if not token_usage:
            return
        input_tokens = int(
            token_usage.get("input_tokens")
            or token_usage.get("prompt_tokens")
            or 0
        )
        output_tokens = int(
            token_usage.get("output_tokens")
            or token_usage.get("completion_tokens")
            or 0
        )
        input_tokens = max(input_tokens, 0)
        output_tokens = max(output_tokens, 0)
        total_input_tokens += input_tokens
        total_output_tokens += output_tokens
        metadata = ctx.session_metadata
        metadata.llm_input_tokens += input_tokens
        metadata.llm_output_tokens += output_tokens
        metadata.llm_last_input_tokens = input_tokens
        metadata.llm_last_output_tokens = output_tokens

    iteration = 0
    cancelled = False
    status_message = "[cyan]Thinking…[/cyan]"

    def _maybe_render_todo(payload: Any) -> None:
        if not isinstance(payload, dict):
            return
        if not payload.get("show_todo_list"):
            return
        todo_render = payload.get("todo_render")
        if not isinstance(todo_render, str) or not todo_render.strip():
            return
        display_messages.append(("agent", todo_render))
        ctx.render_message("agent", todo_render)
        rendered_roles.add("agent")

    def _complete_todo(step_title: str | None) -> bool:
        if ctx.todo_manager is None:
            return False
        tasks = ctx.todo_manager.tasks()
        if not tasks:
            return False
        open_tasks = [task for task in tasks if task.status != "done"]
        if not open_tasks:
            return False
        if not step_title:
            return False
        needle = step_title.strip().lower()
        contains = [task for task in open_tasks if needle in task.title.lower()]
        equals = [task for task in open_tasks if task.title.strip().lower() == needle]
        if len(equals) == 1:
            target = equals[0]
        elif len(contains) == 1:
            target = contains[0]
        else:
            target = open_tasks[0]
        try:
            ctx.todo_manager.mark_complete(target.id, expected_revision=ctx.todo_manager.revision)
        except ValueError:
            return False
        message = f"Marked TODO '{target.title}' complete."
        display_messages.append(("system", message))
        ctx.render_message("system", message)
        rendered_roles.add("system")
        todo_render = ctx.todo_manager.render()
        display_messages.append(("agent", todo_render))
        ctx.render_message("agent", todo_render)
        rendered_roles.add("agent")
        return True

    def _bootstrap_plan_into_todo(steps: list[str] | None) -> bool:
        if ctx.todo_manager is None or not steps:
            return False
        existing_tasks = ctx.todo_manager.tasks()
        existing_titles = {_todo_normalize_title(task.title) for task in existing_tasks}
        added = False
        for step in steps:
            if not step or not step.strip():
                continue
            normalized_title = _todo_normalize_title(step)
            if normalized_title in existing_titles:
                continue
            try:
                ctx.todo_manager.create_task(
                    step.strip(),
                    expected_revision=ctx.todo_manager.revision,
                )
            except ValueError:
                continue
            existing_titles.add(normalized_title)
            added = True
        if not existing_tasks and not added:
            return False
        todo_render = ctx.todo_manager.render()
        display_messages.append(("agent", todo_render))
        ctx.render_message("agent", todo_render)
        rendered_roles.add("agent")
        return True

    def _handle_completion_todo() -> None:
        if ctx.todo_manager is None:
            return
        tasks = ctx.todo_manager.tasks()
        if not tasks:
            ctx.todo_manager.acknowledge()
            return
        remaining = [task for task in tasks if task.status != "done"]
        if remaining:
            if ctx.todo_manager.acknowledged:
                return
            reminder = (
                "TODO list still has unfinished items.\n"
                f"{ctx.todo_manager.render()}\n"
                "Use `/todo done <id>` to complete items or `/todo clear` to remove them."
            )
            display_messages.append(("system", reminder))
            ctx.render_message("system", reminder)
            rendered_roles.add("system")
            ctx.todo_manager.acknowledge()
        else:
            render_before = ctx.todo_manager.render()
            summary: str
            try:
                ctx.todo_manager.clear(expected_revision=ctx.todo_manager.revision)
            except ValueError:
                summary = (
                    "All TODO items are complete, but the list changed before it could be cleared.\n"
                    f"{render_before}\n"
                    "Review the remaining items with `/todo list`."
                )
            else:
                summary = (
                    "All TODO items are complete. 🎉\n"
                    f"{render_before}\n"
                    "TODO list cleared for the next run."
                )
            display_messages.append(("system", summary))
            ctx.render_message("system", summary)
            rendered_roles.add("system")

    with ctx.console.status(status_message, spinner="dots") as status_indicator:
        try:
            while iteration < ctx.max_iterations:
                iteration += 1
                status_indicator.update(status_message)
                tokens: list[str] = []
                try:
                    result = ctx.llm.stream_chat(
                        pending_prompt,
                        history=loop_history,
                        system_prompt=system_prompt,
                        on_chunk=tokens.append,
                    )
                except Exception as exc:  # noqa: BLE001
                    if isinstance(exc, ToolRegistryError):
                        raise
                    error_message = f"LLM error: {exc}"
                    display_messages.append(("system", error_message))
                    ctx.render_message("system", error_message)
                    rendered_roles.add("system")
                    break

                reply_text = "".join(tokens) or getattr(result, "text", "")
                loop_history.append({"role": "user", "content": pending_prompt})
                loop_history.append({"role": "assistant", "content": reply_text})

                if not reply_text:
                    error_message = "LLM returned an empty directive."
                    display_messages.append(("system", error_message))
                    ctx.render_message("system", error_message)
                    rendered_roles.add("system")
                    break

                try:
                    directive = parse_agent_directive(reply_text)
                except AgentMessageError as exc:
                    if retry_payload is not None:
                        error_message = (
                            "LLM failed to provide a valid directive after a retry. "
                            f"Error: {exc}"
                        )
                        display_messages.append(("system", error_message))
                        ctx.render_message("system", error_message)
                        rendered_roles.add("system")
                        break
                    retry_payload = json.dumps(
                        {
                            "type": "error",
                            "message": (
                                "Invalid directive received. Respond with a valid JSON "
                                "object that matches the declared schema."
                            ),
                            "details": str(exc),
                        }
                    )
                    pending_prompt = retry_payload
                    continue

                retry_payload = None
                _accumulate_usage(result)

                if not plan_received:
                    if directive.type == "plan":
                        plan_received = True
                        auto_rendered = _bootstrap_plan_into_todo(directive.steps)
                        if not auto_rendered:
                            plan_text = _format_plan_message(directive.steps or [], directive.message)
                            display_messages.append(("agent", plan_text))
                            ctx.render_message("agent", plan_text)
                            rendered_roles.add("agent")
                        if directive.steps:
                            status_message = f"[cyan]{directive.steps[0]}[/cyan]"
                        pending_prompt = AGENT_PLAN_ACK
                        continue
                    if directive.type == "reply":
                        has_tasks = bool(ctx.todo_manager and ctx.todo_manager.tasks())
                        if has_tasks:
                            pending_prompt = json.dumps(
                                {
                                    "type": "error",
                                    "message": (
                                        "Active TODO items detected. Provide a plan or use the TODO tools to mark steps complete before replying."
                                    ),
                                }
                            )
                            continue
                        final_message = directive.message or ""
                        if directive.step_title:
                            final_message = f"{directive.step_title}\n{final_message}"
                        display_messages.append(("agent", final_message))
                        ctx.render_message("agent", final_message)
                        rendered_roles.add("agent")
                        status_message = "[cyan]Thinking…[/cyan]"
                        _handle_completion_todo()
                        break
                    if directive.type == "cancel":
                        cancel_message = directive.message or "Agent cancelled the request."
                        display_messages.append(("system", cancel_message))
                        ctx.render_message("system", cancel_message)
                        rendered_roles.add("system")
                        status_message = "[cyan]Thinking…[/cyan]"
                        _handle_completion_todo()
                        break
                    pending_prompt = json.dumps(
                        {
                            "type": "error",
                            "message": (
                                "First response must be a plan for multi-step work or a direct reply when a single answer suffices."
                            ),
                        }
                    )
                    continue

                if directive.type == "plan":
                    if not _bootstrap_plan_into_todo(directive.steps):
                        plan_text = _format_plan_message(directive.steps or [], directive.message)
                        display_messages.append(("agent", plan_text))
                        ctx.render_message("agent", plan_text)
                        rendered_roles.add("agent")
                    if directive.steps:
                        status_message = f"[cyan]{directive.steps[0]}[/cyan]"
                    pending_prompt = AGENT_PLAN_ACK
                    continue

                if directive.type == "tool_request":
                    tool_name = directive.tool.name
                    step_title = directive.step_title or tool_name
                    tool_args = directive.tool.args
                    status_message = f"[cyan]{step_title}[/cyan]"
                    status_indicator.update(status_message)
                    try:
                        tool_result = ctx.tool_registry.invoke(tool_name, tool_args)
                        status: Literal["success", "error"] = "success"
                        output = tool_result.content
                        payload_data = tool_result.data
                    except ToolRegistryError as exc:
                        status = "error"
                        output = str(exc)
                        payload_data = None

                    preview = _format_tool_preview(step_title, output)
                    display_messages.append(("agent", preview))
                    ctx.render_message("agent", preview)
                    rendered_roles.add("agent")
                    completed = False
                    if status == "success":
                        completed = _complete_todo(step_title)
                    if not completed:
                        _maybe_render_todo(payload_data)

                    summary_entry: dict[str, Any] = {
                        "type": "tool",
                        "name": tool_name,
                        "status": status,
                        "summary": step_title,
                    }
                    if payload_data is not None:
                        summary_entry["data"] = payload_data
                    tool_summaries.append(summary_entry)

                    tool_payload = AgentToolResult(
                        tool_name=tool_name,
                        step_title=step_title,
                        status=status,
                        output=output,
                        data=payload_data,
                    )
                    pending_prompt = json.dumps(
                        tool_payload.model_dump(mode="json", exclude_none=True),
                        ensure_ascii=False,
                        default=str,
                    )
                    continue

                if directive.type == "reply":
                    final_message = directive.message or ""
                    if directive.step_title:
                        final_message = f"{directive.step_title}\n{final_message}"
                    display_messages.append(("agent", final_message))
                    ctx.render_message("agent", final_message)
                    rendered_roles.add("agent")
                    status_message = "[cyan]Thinking…[/cyan]"
                    _handle_completion_todo()
                    break

                if directive.type == "cancel":
                    cancel_message = directive.message or "Agent cancelled the request."
                    display_messages.append(("system", cancel_message))
                    ctx.render_message("system", cancel_message)
                    rendered_roles.add("system")
                    status_message = "[cyan]Thinking…[/cyan]"
                    _handle_completion_todo()
                    break
        except KeyboardInterrupt:
            cancelled = True
            cancel_message = "Interrupted by user."
            display_messages.append(("system", cancel_message))
            ctx.render_message("system", cancel_message)
            rendered_roles.add("system")
            status_message = "[cyan]Thinking…[/cyan]"

    if not display_messages:
        if cancelled:
            display_messages.append(("system", "Agent loop cancelled."))
        else:
            display_messages.append(("system", "No response generated from the agent loop."))

    if iteration >= ctx.max_iterations and not cancelled and display_messages[-1][0] != "system":
        timeout_message = "Agent loop stopped after reaching the iteration limit."
        display_messages.append(("system", timeout_message))
        ctx.render_message("system", timeout_message)
        rendered_roles.add("system")

    total_tokens = total_input_tokens + total_output_tokens
    llm_summary: dict[str, Any] = {
        "type": "llm",
        "name": f"{provider_name}:{model_name}",
        "status": "cached" if all_cached else "success",
        "latency": round(total_latency, 3),
    }
    if last_finish_reason:
        llm_summary["summary"] = f"finish={last_finish_reason}"
    if total_tokens:
        llm_summary["token_usage"] = {
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "total_tokens": total_tokens,
        }
    if reasoning_effort:
        llm_summary["reasoning_effort"] = reasoning_effort

    tool_calls = [llm_summary, *tool_summaries]
    return CommandResponse(
        messages=display_messages,
        tool_calls=tool_calls,
        rendered_roles=rendered_roles or None,
    )


def _active_model_details(config_context: ConfigContext | None) -> tuple[str, str, str]:
    provider_name = "unknown"
    model_name = "unknown"
    reasoning_effort = "medium"
    if config_context:
        provider_name = config_context.config.llm_provider
        model_name = config_context.config.llm_model
        reasoning_effort = getattr(
            config_context.config,
            "llm_reasoning_effort",
            "medium",
        )
    return provider_name, model_name, reasoning_effort


def _agent_system_prompt(config_context: ConfigContext | None, manifest_json: str) -> str:
    provider_name, model_name, reasoning_effort = _active_model_details(config_context)
    schema_description = (
        "Schema:\n"
        '{ "type": "plan|tool_request|reply|cancel",\n'
        '  "message": string?,\n'
        '  "step_title": string?,\n'
        '  "tool": {"name": string, "args": object}?,\n'
        '  "steps": string[]? }\n'
    )
    return (
        "You are SolCoder, an on-device coding assistant. Always respond with a single "
        "JSON object that matches the schema below. Do not include Markdown or prose "
        "outside the JSON value. Use compact JSON without extra commentary.\n\n"
        f"{schema_description}"
        "Rules:\n"
        "1. If a prompt can be satisfied immediately without tools or multi-step work, respond "
        '   directly with {"type":"reply","message":...}. Otherwise begin with '
        '{"type":"plan","steps":[...]} describing the intended workflow.\n'
        "2. When you need to run a tool, reply with "
        '{"type":"tool_request","step_title":...,"tool":{"name":...,"args":{...}}}. '
        "Keep arguments strictly within the declared schema.\n"
        "3. Once work is complete, respond with "
        '{"type":"reply","message":...}. Include any final user-facing summary there.\n'
        "4. You may send {'type':'cancel','message':...} if the request cannot be "
        "completed safely.\n"
        "5. After your plan is acknowledged the orchestrator will send "
        '{"type":"plan_ack","status":"ready"}; treat it as confirmation to continue.\n'
        "6. After the orchestrator sends you tool results, continue the loop using the "
        "latest context until you can emit a final reply.\n"
        "7. Do not invent tools. Only use the manifest provided below.\n"
        "8. Reach for the TODO tools (todo_add_task, todo_update_task, etc.) when you need to track "
        "multi-step work. Skip them entirely for quick answers. Reserve generate_plan for long-term "
        "strategy. When you want the CLI to show the checklist, set show_todo_list=true; otherwise "
        "leave it out to keep the list hidden.\n\n"
        f"Current configuration: provider={provider_name}, model={model_name}, "
        f"reasoning_effort={reasoning_effort}.\n"
        f"Available tools: {manifest_json}\n"
        "During the conversation you may also receive JSON objects with "
        '{"type":"tool_result",...}. Use them to inform the next action.'
    )


def _format_plan_message(steps: list[str], preamble: str | None) -> str:
    heading = preamble or "Agent plan:"
    bullet_lines = "\n".join(f"- {step}" for step in steps)
    return f"{heading}\n{bullet_lines}"


def _format_tool_preview(step_title: str, content: str) -> str:
    return f"{step_title}\n{content}"


__all__ = ["AgentLoopContext", "AGENT_PLAN_ACK", "DEFAULT_AGENT_MAX_ITERATIONS", "run_agent_loop"]
