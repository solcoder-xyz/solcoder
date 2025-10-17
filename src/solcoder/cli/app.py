
"""Interactive CLI shell for SolCoder."""

from __future__ import annotations

import json
import logging
import os
import sys
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from solcoder.core import (
    AgentMessageError,
    AgentToolResult,
    ConfigContext,
    ConfigManager,
    DiagnosticResult,
    RenderOptions,
    TemplateError,
    available_templates,
    build_tool_manifest,
    collect_environment_diagnostics,
    manifest_to_prompt_section,
    parse_agent_directive,
    render_template,
)
from solcoder.core.llm import LLMError, LLMResponse
from solcoder.core.tool_registry import (
    ToolRegistry,
    ToolRegistryError,
    build_default_registry,
)
from solcoder.session import (
    TRANSCRIPT_LIMIT,
    SessionContext,
    SessionLoadError,
    SessionManager,
)
from solcoder.session.manager import MAX_SESSIONS
from solcoder.solana import SolanaRPCClient, WalletError, WalletManager, WalletStatus

logger = logging.getLogger(__name__)


DEFAULT_HISTORY_PATH = Path(os.environ.get("SOLCODER_HOME", Path.home() / ".solcoder")) / "history"
DEFAULT_HISTORY_LIMIT = 20
DEFAULT_SUMMARY_KEEP = 10
DEFAULT_SUMMARY_MAX_WORDS = 200
DEFAULT_AUTO_COMPACT_THRESHOLD = 0.95
DEFAULT_LLM_INPUT_LIMIT = 272_000
DEFAULT_LLM_OUTPUT_LIMIT = 128_000
DEFAULT_COMPACTION_COOLDOWN = 10
DEFAULT_AGENT_MAX_ITERATIONS = 1000
AGENT_PLAN_ACK = json.dumps({"type": "plan_ack", "status": "ready"})


@dataclass
class CommandResponse:
    """Represents the outcome of handling a CLI input."""

    messages: list[tuple[str, str]]
    continue_loop: bool = True
    tool_calls: list[dict[str, Any]] | None = None
    rendered_roles: set[str] | None = None


class LLMBackend(Protocol):
    """Interface for SolCoder LLM adapters."""

    def stream_chat(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        history: Sequence[dict[str, str]] | None = None,
        on_chunk: Callable[[str], None] | None = None,
    ) -> LLMResponse:
        ...


def _parse_template_tokens(
    template_name: str,
    tokens: list[str],
    defaults: dict[str, str],
) -> tuple[RenderOptions | None, str | None]:
    destination: Path | None = None
    program_name = defaults["program_name"]
    author = defaults["author_pubkey"]
    program_id = "replace-with-program-id"
    cluster = "devnet"
    overwrite = False

    idx = 0
    while idx < len(tokens):
        option = tokens[idx]
        if option == "--force":
            overwrite = True
            idx += 1
            continue
        if option == "--program" and idx + 1 < len(tokens):
            program_name = tokens[idx + 1]
            idx += 2
            continue
        if option.startswith("--program="):
            program_name = option.split("=", 1)[1]
            idx += 1
            continue
        if option == "--author" and idx + 1 < len(tokens):
            author = tokens[idx + 1]
            idx += 2
            continue
        if option.startswith("--author="):
            author = option.split("=", 1)[1]
            idx += 1
            continue
        if option == "--program-id" and idx + 1 < len(tokens):
            program_id = tokens[idx + 1]
            idx += 2
            continue
        if option.startswith("--program-id="):
            program_id = option.split("=", 1)[1]
            idx += 1
            continue
        if option == "--cluster" and idx + 1 < len(tokens):
            cluster = tokens[idx + 1]
            idx += 2
            continue
        if option.startswith("--cluster="):
            cluster = option.split("=", 1)[1]
            idx += 1
            continue
        if option.startswith("-"):
            return None, f"Unknown option '{option}'."
        if destination is None:
            destination = Path(option)
            idx += 1
            continue
        return None, "Unexpected extra argument."

    if destination is None:
        return None, "Destination path is required."

    options = RenderOptions(
        template=template_name,
        destination=destination,
        program_name=program_name,
        author_pubkey=author,
        program_id=program_id,
        cluster=cluster,
        overwrite=overwrite,
    )
    return options, None


class SlashCommand:
    """Container for slash command metadata."""

    def __init__(self, name: str, handler: Callable[[CLIApp, list[str]], CommandResponse], help_text: str) -> None:
        self.name = name
        self.handler = handler
        self.help_text = help_text


class CommandRouter:
    """Parses and dispatches slash commands."""

    def __init__(self) -> None:
        self._commands: dict[str, SlashCommand] = {}

    def register(self, command: SlashCommand) -> None:
        logger.debug("Registering command: %s", command.name)
        self._commands[command.name] = command

    def available_commands(self) -> Iterable[SlashCommand]:
        return self._commands.values()

    def dispatch(self, app: CLIApp, raw_line: str) -> CommandResponse:
        parts = raw_line.strip().split()
        if not parts:
            return CommandResponse(messages=[])
        command_name, *args = parts
        command = self._commands.get(command_name)
        if not command:
            logger.info("Unknown command: /%s", command_name)
            return CommandResponse(messages=[("system", f"Unknown command '/{command_name}'. Type /help for a list of commands.")])
        logger.debug("Dispatching command '/%s' with args %s", command_name, args)
        return command.handler(app, args)


class StubLLM:
    """Placeholder LLM adapter used until the real integration is wired in."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.model = "gpt-5-codex"
        self.reasoning_effort = "medium"
        self._awaiting_ack = False
        self._last_user_prompt = ""

    def respond(self, prompt: str) -> str:
        self.calls.append(prompt)
        if not self._awaiting_ack:
            self._awaiting_ack = True
            self._last_user_prompt = prompt
            payload = {
                "type": "plan",
                "message": "Stub plan for the request.",
                "steps": [
                    f"Consider the request: {prompt[:80]}",
                    "Outline the response.",
                ],
            }
        else:
            self._awaiting_ack = False
            payload = {
                "type": "reply",
                "message": f"[stub] Completed request: {self._last_user_prompt[:80]}",
            }
        return json.dumps(payload)

    def stream_chat(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        history: Sequence[dict[str, str]] | None = None,
        on_chunk: Callable[[str], None] | None = None,
    ) -> LLMResponse:
        reply = self.respond(prompt)
        if on_chunk:
            on_chunk(reply)
        words_in = max(len(prompt.split()), 1)
        words_out = max(len(reply.split()), 1)
        return LLMResponse(
            text=reply,
            latency_seconds=0.0,
            cached=True,
            token_usage={
                "input_tokens": words_in,
                "output_tokens": words_out,
                "total_tokens": words_in + words_out,
            },
        )

    def update_settings(self, *, model: str | None = None, reasoning_effort: str | None = None) -> None:
        if model:
            self.model = model
        if reasoning_effort:
            self.reasoning_effort = reasoning_effort


class CLIApp:
    """Interactive shell orchestrating slash commands and chat flow."""

    def __init__(
        self,
        console: Console | None = None,
        history_path: Path | None = None,
        llm: LLMBackend | None = None,
        config_context: ConfigContext | None = None,
        config_manager: ConfigManager | None = None,
        session_context: SessionContext | None = None,
        session_manager: SessionManager | None = None,
        wallet_manager: WalletManager | None = None,
        rpc_client: SolanaRPCClient | None = None,
        tool_registry: ToolRegistry | None = None,
    ) -> None:
        self.console = console or CLIApp._default_console()
        self.config_context = config_context
        self.config_manager = config_manager
        self.session_manager = session_manager or SessionManager()
        self.session_context = session_context or self.session_manager.start()
        self.wallet_manager = wallet_manager or WalletManager()
        self.rpc_client = rpc_client
        self._master_passphrase = getattr(config_context, "passphrase", None)
        history_path = history_path or (
            self.session_manager.root / self.session_context.metadata.session_id / "history"
        )
        history_path.parent.mkdir(parents=True, exist_ok=True)
        self.session = PromptSession(history=FileHistory(str(history_path)))
        self.command_router = CommandRouter()
        self._register_builtin_commands()
        self._llm: LLMBackend = llm or StubLLM()
        self.tool_registry = tool_registry or build_default_registry()
        self._transcript = self.session_context.transcript
        initial_status = self.wallet_manager.status()
        initial_balance = self._fetch_balance(initial_status.public_key)
        self._update_wallet_metadata(initial_status, balance=initial_balance)
        logger.debug(
            "CLIApp initialized with history file %s for session %s",
            history_path,
            self.session_context.metadata.session_id,
        )

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    def _register_builtin_commands(self) -> None:
        self.command_router.register(
            SlashCommand("help", CLIApp._handle_help, "Show available commands"),
        )
        self.command_router.register(
            SlashCommand("quit", CLIApp._handle_quit, "Exit SolCoder"),
        )
        self.command_router.register(
            SlashCommand("settings", CLIApp._handle_settings, "View or update session settings"),
        )
        self.command_router.register(
            SlashCommand("wallet", CLIApp._handle_wallet, "Wallet management commands"),
        )
        self.command_router.register(
            SlashCommand("session", CLIApp._handle_session, "Session utilities"),
        )
        self.command_router.register(
            SlashCommand("env", CLIApp._handle_env, "Environment diagnostics"),
        )
        self.command_router.register(
            SlashCommand("template", CLIApp._handle_template, "Template scaffolding commands"),
        )
        self.command_router.register(
            SlashCommand("toolkits", CLIApp._handle_toolkits, "List toolkits and tools"),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(self) -> None:
        """Start the interactive REPL."""
        welcome = (
            "Welcome to SolCoder! Type plain text to chat or `/help` for commands."
            f"\n\nSession ID: {self.session_context.metadata.session_id}"
        )
        self.console.print(Panel(welcome, title="SolCoder"))
        with patch_stdout():
            while True:
                try:
                    user_input = self.session.prompt(self._prompt_message())
                except KeyboardInterrupt:
                    # User pressed Ctrl-C; ignore and prompt again.
                    logger.debug("KeyboardInterrupt detected; ignoring")
                    continue
                except EOFError:
                    self.console.print("Exiting SolCoder. Bye!")
                    break

                response = self.handle_line(user_input)
                for role, message in response.messages:
                    if response.rendered_roles and role in response.rendered_roles:
                        continue
                    self._render_message(role, message)

                if not response.continue_loop:
                    break
                self._render_status()

        self._persist()

    def handle_line(self, raw_line: str) -> CommandResponse:
        """Handle a single line of user input (used by tests and run loop)."""
        raw_line = raw_line.rstrip()
        if not raw_line:
            return CommandResponse(messages=[])

        self._record("user", raw_line)
        self._render_message("user", raw_line)

        if raw_line.startswith("/"):
            logger.debug("Processing slash command: %s", raw_line)
            response = self.command_router.dispatch(self, raw_line[1:])
        else:
            logger.debug("Routing chat message to LLM backend")
            response = self._chat_with_llm(raw_line)

        for idx, (role, message) in enumerate(response.messages):
            tool_calls = response.tool_calls if idx == 0 else None
            self._record(role, message, tool_calls=tool_calls)
        self._compress_history_if_needed()
        self._persist()
        return response

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------
    def _max_agent_iterations(self) -> int:
        return DEFAULT_AGENT_MAX_ITERATIONS

    def _agent_system_prompt(self, manifest_json: str) -> str:
        provider_name = "unknown"
        model_name = "unknown"
        reasoning_effort = "medium"
        if self.config_context:
            provider_name = self.config_context.config.llm_provider
            model_name = self.config_context.config.llm_model
            reasoning_effort = getattr(
                self.config_context.config,
                "llm_reasoning_effort",
                "medium",
            )

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
            "1. The very first response for each new user message MUST be a plan directive "
            '   with {"type":"plan","steps":[...]} describing the intended workflow.\n'
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
            "7. Do not invent tools. Only use the manifest provided below.\n\n"
            f"Current configuration: provider={provider_name}, model={model_name}, "
            f"reasoning_effort={reasoning_effort}.\n"
            f"Available tools: {manifest_json}\n"
            "During the conversation you may also receive JSON objects with "
            '{"type":"tool_result",...}. Use them to inform the next action.'
        )

    @staticmethod
    def _format_plan_message(steps: list[str], preamble: str | None) -> str:
        heading = preamble or "Agent plan:"
        bullet_lines = "\n".join(f"- {step}" for step in steps)
        return f"{heading}\n{bullet_lines}"

    @staticmethod
    def _format_tool_preview(step_title: str, content: str) -> str:
        return f"{step_title}\n{content}"

    def _chat_with_llm(self, prompt: str) -> CommandResponse:
        history = self._conversation_history()
        manifest = build_tool_manifest(self.tool_registry)
        manifest_json = manifest_to_prompt_section(manifest)
        system_prompt = self._agent_system_prompt(manifest_json)

        loop_history = list(history)
        pending_prompt = prompt
        plan_received = False
        max_iterations = self._max_agent_iterations()
        rendered_roles: set[str] = set()
        display_messages: list[tuple[str, str]] = []
        tool_summaries: list[dict[str, Any]] = []
        total_latency = 0.0
        total_input_tokens = 0
        total_output_tokens = 0
        last_finish_reason: str | None = None
        all_cached = True
        retry_payload: str | None = None

        provider_name = "unknown"
        model_name = "unknown"
        reasoning_effort = "medium"
        if self.config_context:
            provider_name = self.config_context.config.llm_provider
            model_name = self.config_context.config.llm_model
            reasoning_effort = getattr(
                self.config_context.config,
                "llm_reasoning_effort",
                "medium",
            )

        def _accumulate_usage(result: LLMResponse) -> None:
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
            metadata = self.session_context.metadata
            metadata.llm_input_tokens += input_tokens
            metadata.llm_output_tokens += output_tokens
            metadata.llm_last_input_tokens = input_tokens
            metadata.llm_last_output_tokens = output_tokens

        iteration = 0
        cancelled = False
        status_message = "[cyan]Thinking…[/cyan]"
        with self.console.status(status_message, spinner="dots") as status_indicator:
            try:
                while iteration < max_iterations:
                    iteration += 1
                    status_indicator.update(status_message)
                    tokens: list[str] = []
                    try:
                        result = self._llm.stream_chat(
                            pending_prompt,
                            history=loop_history,
                            system_prompt=system_prompt,
                            on_chunk=tokens.append,
                        )
                    except LLMError as exc:
                        logger.error("LLM error: %s", exc)
                        error_message = f"LLM error: {exc}"
                        display_messages.append(("system", error_message))
                        self._render_message("system", error_message)
                        rendered_roles.add("system")
                        break

                    reply_text = "".join(tokens) or getattr(result, "text", "")
                    loop_history.append({"role": "user", "content": pending_prompt})
                    loop_history.append({"role": "assistant", "content": reply_text})

                    if not reply_text:
                        error_message = "LLM returned an empty directive."
                        display_messages.append(("system", error_message))
                        self._render_message("system", error_message)
                        rendered_roles.add("system")
                        break

                    try:
                        directive = parse_agent_directive(reply_text)
                    except AgentMessageError as exc:
                        logger.debug("Directive parse error: %s", exc)
                        if retry_payload is not None:
                            error_message = (
                                "LLM failed to provide a valid directive after a retry. "
                                f"Error: {exc}"
                            )
                            display_messages.append(("system", error_message))
                            self._render_message("system", error_message)
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
                        if directive.type != "plan":
                            pending_prompt = json.dumps(
                                {
                                    "type": "error",
                                    "message": "First response must use type='plan' with steps.",
                                }
                            )
                            continue
                        plan_received = True
                        plan_text = self._format_plan_message(directive.steps or [], directive.message)
                        display_messages.append(("agent", plan_text))
                        self._render_message("agent", plan_text)
                        rendered_roles.add("agent")
                        if directive.steps:
                            status_message = f"[cyan]{directive.steps[0]}[/cyan]"
                        pending_prompt = AGENT_PLAN_ACK
                        continue

                    if directive.type == "plan":
                        plan_text = self._format_plan_message(directive.steps or [], directive.message)
                        display_messages.append(("agent", plan_text))
                        self._render_message("agent", plan_text)
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
                            tool_result = self.tool_registry.invoke(tool_name, tool_args)
                            status: Literal["success", "error"] = "success"
                            output = tool_result.content
                            payload_data = tool_result.data
                        except ToolRegistryError as exc:
                            status = "error"
                            output = str(exc)
                            payload_data = None
                            logger.warning("Tool '%s' failed: %s", tool_name, exc)

                        preview = self._format_tool_preview(step_title, output)
                        display_messages.append(("agent", preview))
                        self._render_message("agent", preview)
                        rendered_roles.add("agent")

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
                        self._render_message("agent", final_message)
                        rendered_roles.add("agent")
                        status_message = "[cyan]Thinking…[/cyan]"
                        break

                    if directive.type == "cancel":
                        cancel_message = directive.message or "Agent cancelled the request."
                        display_messages.append(("system", cancel_message))
                        self._render_message("system", cancel_message)
                        rendered_roles.add("system")
                        status_message = "[cyan]Thinking…[/cyan]"
                        break
            except KeyboardInterrupt:
                cancelled = True
                cancel_message = "Interrupted by user."
                display_messages.append(("system", cancel_message))
                self._render_message("system", cancel_message)
                rendered_roles.add("system")
                status_message = "[cyan]Thinking…[/cyan]"

        if not display_messages:
            if cancelled:
                display_messages.append(("system", "Agent loop cancelled."))
            else:
                display_messages.append(
                    ("system", "No response generated from the agent loop.")
                )

        if iteration >= max_iterations and not cancelled and display_messages[-1][0] != "system":
            timeout_message = "Agent loop stopped after reaching the iteration limit."
            display_messages.append(("system", timeout_message))
            self._render_message("system", timeout_message)
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

    def _conversation_history(self) -> list[dict[str, str]]:
        history: list[dict[str, str]] = []
        # Exclude the most recent entry (current user prompt) because it is passed separately.
        transcript = self._transcript[:-1]
        for entry in transcript:
            message = entry.get("message")
            if not isinstance(message, str) or not message:
                continue
            if entry.get("summary"):
                history.append({"role": "system", "content": message})
                continue
            role = entry.get("role")
            if role == "user":
                history.append({"role": "user", "content": message})
            elif role == "agent":
                history.append({"role": "assistant", "content": message})
            else:
                history.append({"role": "system", "content": message})
        return history

    def _update_llm_settings(self, *, model: str | None = None, reasoning: str | None = None) -> None:
        if self.config_context is None:
            return
        if model:
            self.config_context.config.llm_model = model
        if reasoning:
            self.config_context.config.llm_reasoning_effort = reasoning
        update_kwargs: dict[str, str] = {}
        if model:
            update_kwargs["model"] = model
        if reasoning:
            update_kwargs["reasoning_effort"] = reasoning
        if update_kwargs and hasattr(self._llm, "update_settings"):
            try:
                self._llm.update_settings(**update_kwargs)  # type: ignore[misc]
            except Exception:  # noqa: BLE001
                logger.warning("LLM backend does not support runtime setting updates.")
        if self.config_manager is not None:
            try:
                self.config_manager.update_llm_preferences(
                    llm_model=model if model else None,
                    llm_reasoning_effort=reasoning if reasoning else None,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to persist LLM settings: %s", exc)

    def _invoke_tool(self, tool_name: str, payload: dict[str, Any]) -> CommandResponse:
        try:
            result = self.tool_registry.invoke(tool_name, payload)
        except ToolRegistryError as exc:
            tool_calls = [
                {
                    "type": "tool",
                    "name": tool_name,
                    "status": "error",
                    "summary": str(exc),
                }
            ]
            return CommandResponse(messages=[("system", f"Tool error: {exc}")], tool_calls=tool_calls)

        summary_text = result.summary or result.content.splitlines()[0][:120] if result.content else ""
        tool_calls = [
            {
                "type": "tool",
                "name": tool_name,
                "status": "success",
                "summary": summary_text,
            }
        ]
        return CommandResponse(messages=[("system", result.content)], tool_calls=tool_calls)

    def _compress_history_if_needed(self) -> None:
        transcript = self.session_context.transcript
        history_limit = self._config_int("history_max_messages", DEFAULT_HISTORY_LIMIT)
        cooldown = self.session_context.metadata.compression_cooldown
        if len(transcript) > history_limit and cooldown <= 0:
            self._summarize_older_history()
        metadata = self.session_context.metadata
        input_limit = self._config_int("llm_input_token_limit", DEFAULT_LLM_INPUT_LIMIT)
        threshold = self._config_float("history_auto_compact_threshold", DEFAULT_AUTO_COMPACT_THRESHOLD)
        if metadata.llm_last_input_tokens >= int(input_limit * threshold) and cooldown <= 0:
            self._compress_full_history()
        metadata.compression_cooldown = max(metadata.compression_cooldown - 1, 0)

    def _summarize_older_history(self) -> None:
        transcript = self.session_context.transcript
        history_limit = self._config_int("history_max_messages", DEFAULT_HISTORY_LIMIT)
        keep_count = self._config_int("history_summary_keep", DEFAULT_SUMMARY_KEEP)
        if keep_count >= history_limit:
            keep_count = max(history_limit - 2, 1)
        if len(transcript) <= keep_count:
            return
        older = transcript[:-keep_count]
        if not older:
            return
        summary_text = self._generate_summary(older)
        summary_entry = {
            "role": "system",
            "message": summary_text,
            "timestamp": datetime.now(UTC).isoformat(),
            "summary": True,
        }
        self.session_context.transcript = [summary_entry, *transcript[-keep_count:]]
        self._transcript = self.session_context.transcript
        input_limit = self._config_int("llm_input_token_limit", DEFAULT_LLM_INPUT_LIMIT)
        self.session_context.metadata.llm_last_input_tokens = min(
            self._estimate_context_tokens(),
            input_limit,
        )
        self.session_context.metadata.compression_cooldown = self._config_int(
            "history_compaction_cooldown",
            DEFAULT_COMPACTION_COOLDOWN,
        )

    def _compress_full_history(self) -> None:
        transcript = self.session_context.transcript
        keep_count = self._config_int("history_summary_keep", DEFAULT_SUMMARY_KEEP)
        keep_count = max(min(keep_count, len(transcript)), 1)
        if len(transcript) <= keep_count:
            return
        keep = transcript[-keep_count:]
        summary_text = self._generate_summary(transcript[:-keep_count])
        summary_entry = {
            "role": "system",
            "message": summary_text,
            "timestamp": datetime.now(UTC).isoformat(),
            "summary": True,
        }
        self.session_context.transcript = [summary_entry, *keep]
        self._transcript = self.session_context.transcript
        estimated = self._estimate_context_tokens()
        metadata = self.session_context.metadata
        input_limit = self._config_int("llm_input_token_limit", DEFAULT_LLM_INPUT_LIMIT)
        metadata.llm_last_input_tokens = min(estimated, input_limit)
        metadata.compression_cooldown = self._config_int(
            "history_compaction_cooldown",
            DEFAULT_COMPACTION_COOLDOWN,
        )

    def _generate_summary(self, entries: list[dict[str, Any]]) -> str:
        if not entries:
            return "(history empty)"
        conversation_lines: list[str] = []
        for entry in entries:
            role = entry.get("role", "unknown")
            message = entry.get("message", "")
            conversation_lines.append(f"{role}: {message}")
        transcript_text = "\n".join(conversation_lines)
        base_words = self._config_int("history_summary_max_words", DEFAULT_SUMMARY_MAX_WORDS)
        keep_count = self._config_int("history_summary_keep", DEFAULT_SUMMARY_KEEP)
        multiplier = max(1, len(entries) // max(1, keep_count))
        max_words = base_words * multiplier
        prompt = (
            f"Summarize the following SolCoder chat history in no more than {max_words} words. "
            "Highlight user goals, decisions, constraints, and any open questions.\n"
            f"Conversation:\n{transcript_text}\n"
            "Return plain text without bullet characters unless required."
        )
        tokens: list[str] = []
        try:
            result = self._llm.stream_chat(
                prompt,
                history=(),
                system_prompt="You are a concise summarization engine for coding assistant transcripts.",
                on_chunk=tokens.append,
            )
            summary_text = "".join(tokens).strip() or result.text.strip()
        except LLMError as exc:
            logger.warning("LLM summarization failed: %s", exc)
            summary_text = "Summary unavailable. Recent highlights:\n" + "\n".join(conversation_lines[-3:])
        if not summary_text:
            summary_text = "Summary not available."
        return summary_text

    def _estimate_context_tokens(self) -> int:
        total = 0
        for entry in self.session_context.transcript:
            message = entry.get("message")
            if isinstance(message, str):
                total += len(message.split())
        return total

    def _config_int(self, attr: str, default: int) -> int:
        if self.config_context is None:
            return default
        return int(getattr(self.config_context.config, attr, default) or default)

    def _config_float(self, attr: str, default: float) -> float:
        if self.config_context is None:
            return default
        return float(getattr(self.config_context.config, attr, default) or default)

    def _force_compact_history(self) -> str:
        before = len(self.session_context.transcript)
        self._compress_full_history()
        after = len(self.session_context.transcript)
        return f"Compacted history from {before} entries to {after}."

    @staticmethod
    def _handle_help(app: CLIApp, _args: list[str]) -> CommandResponse:
        lines = [f"/{cmd.name}	{cmd.help_text}" for cmd in app.command_router.available_commands()]
        content = "\n".join(sorted(lines))
        return CommandResponse(messages=[("system", content)])

    @staticmethod
    def _handle_quit(_app: CLIApp, _args: list[str]) -> CommandResponse:
        return CommandResponse(messages=[("system", "Exiting SolCoder. Bye!")], continue_loop=False)

    @staticmethod
    def _handle_settings(app: CLIApp, args: list[str]) -> CommandResponse:
        metadata = app.session_context.metadata
        if not args:
            project_display = metadata.active_project or "unknown"
            wallet_display = metadata.wallet_status or "---"
            spend_display = f"{metadata.spend_amount:.2f} SOL"
            lines = [
                f"Active project:\t{project_display}",
                f"Wallet:\t\t{wallet_display}",
                f"Session spend:\t{spend_display}",
            ]
            return CommandResponse(messages=[("system", "\n".join(lines))])

        subcommand, *values = args
        if subcommand.lower() == "wallet":
            if not values:
                return CommandResponse(
                    messages=[("system", "Usage: /settings wallet <label-or-address>")],
                )
            metadata.wallet_status = " ".join(values)
            return CommandResponse(messages=[("system", f"Wallet updated to '{metadata.wallet_status}'.")])

        if subcommand.lower() == "spend":
            if not values:
                return CommandResponse(messages=[("system", "Usage: /settings spend <amount-sol>")])
            try:
                amount = float(values[0])
            except ValueError:
                return CommandResponse(messages=[("system", "Spend amount must be a number (SOL).")])
            if amount < 0:
                return CommandResponse(messages=[("system", "Spend amount cannot be negative.")])
            metadata.spend_amount = amount
            return CommandResponse(messages=[("system", f"Session spend set to {metadata.spend_amount:.2f} SOL.")])

        if subcommand.lower() == "model":
            if not values:
                return CommandResponse(
                    messages=[("system", "Usage: /settings model <gpt-5|gpt-5-codex>")],
                )
            choice = values[0].strip().lower()
            allowed_models = {"gpt-5", "gpt-5-codex"}
            if choice not in allowed_models:
                return CommandResponse(
                    messages=[(
                        "system",
                        "Supported models: gpt-5, gpt-5-codex.",
                    )]
                )
            canonical_choice = "gpt-5-codex" if choice == "gpt-5-codex" else "gpt-5"
            app._update_llm_settings(model=canonical_choice)
            return CommandResponse(messages=[("system", f"LLM model updated to {canonical_choice}.")])

        if subcommand.lower() in {"reasoning", "effort"}:
            if not values:
                return CommandResponse(
                    messages=[("system", "Usage: /settings reasoning <low|medium|high>")],
                )
            choice = values[0].strip().lower()
            allowed_efforts = {"low", "medium", "high"}
            if choice not in allowed_efforts:
                return CommandResponse(
                    messages=[("system", "Reasoning effort must be one of: low, medium, high.")]
                )
            app._update_llm_settings(reasoning=choice)
            return CommandResponse(messages=[("system", f"Reasoning effort set to {choice}.")])

        return CommandResponse(
            messages=[
                (
                    "system",
                    "Unknown settings option. Use `/settings`, `/settings wallet <value>`, `/settings spend <amount>`, `/settings model <gpt-5|gpt-5-codex>`, or `/settings reasoning <low|medium|high>`.",
                )
            ]
        )

    @staticmethod
    def _handle_toolkits(app: CLIApp, args: list[str]) -> CommandResponse:
        toolkits = app.tool_registry.available_toolkits()
        if not args or args[0].lower() == "list":
            if not toolkits:
                return CommandResponse(messages=[("system", "No toolkits registered.")])
            lines = [
                f"{name}\t{toolkit.description} (v{toolkit.version})"
                for name, toolkit in sorted(toolkits.items())
            ]
            return CommandResponse(messages=[("system", "\n".join(lines))])

        toolkit_name = args[0]
        toolkit = toolkits.get(toolkit_name)
        if not toolkit:
            return CommandResponse(messages=[("system", f"Toolkit '{toolkit_name}' not found.")])

        if len(args) == 1 or (len(args) >= 2 and args[1].lower() == "tools"):
            lines = [f"{tool.name}\t{tool.description}" for tool in toolkit.tools]
            header = f"Tools in toolkit '{toolkit.name}' (v{toolkit.version}):"
            return CommandResponse(messages=[("system", "\n".join([header, *lines]))])

        return CommandResponse(messages=[("system", "Usage: /toolkits list | /toolkits <toolkit> tools")])

    @staticmethod
    def _handle_session(app: CLIApp, args: list[str]) -> CommandResponse:
        if not args:
            return CommandResponse(messages=[("system", "Usage: /session export <id>")])

        command, *rest = args
        if command.lower() == "export":
            if not rest:
                return CommandResponse(messages=[("system", "Usage: /session export <id>")])

            session_id = rest[0]
            tool_summary = [
                {
                    "type": "command",
                    "name": "/session export",
                    "status": "success",
                    "summary": f"Exported session {session_id}",
                }
            ]
            try:
                export_data = app.session_manager.export_session(session_id, redact=True)
            except FileNotFoundError:
                message = (
                    f"Session '{session_id}' not found. Only the most recent {MAX_SESSIONS} sessions are retained."
                )
                tool_summary[0]["status"] = "not_found"
                tool_summary[0]["summary"] = f"Session {session_id} missing"
                return CommandResponse(messages=[("system", message)], tool_calls=tool_summary)
            except SessionLoadError as exc:
                tool_summary[0]["status"] = "error"
                tool_summary[0]["summary"] = str(exc)
                return CommandResponse(messages=[("system", f"Failed to load session: {exc}")], tool_calls=tool_summary)

            content = CLIApp._format_export_text(export_data)
            return CommandResponse(messages=[("system", content)], tool_calls=tool_summary)
        if command.lower() == "compact":
            summary = app._force_compact_history()
            return CommandResponse(messages=[("system", summary)])

        return CommandResponse(messages=[("system", "Unknown session command. Try `/session export <id>`.")])

    @staticmethod
    def _handle_env(_app: CLIApp, args: list[str]) -> CommandResponse:
        if not args or args[0].lower() not in {"diag", "diagnostics"}:
            return CommandResponse(messages=[("system", "Usage: /env diag")])

        results = collect_environment_diagnostics()
        content = CLIApp._format_env_diag(results)
        total = len(results)
        missing = sum(not item.found for item in results)
        degraded = sum(item.status in {"warn", "error"} for item in results)
        if missing:
            tool_status = "missing"
        elif degraded:
            tool_status = "warn"
        else:
            tool_status = "ok"
        summary = f"{total - missing} of {total} tools detected"
        if missing or degraded:
            summary += f"; {missing} missing, {degraded} warnings"
        tool_calls = [
            {
                "type": "command",
                "name": "/env diag",
                "status": tool_status,
                "summary": summary,
            }
        ]
        return CommandResponse(messages=[("system", content)], tool_calls=tool_calls)

    @staticmethod
    def _handle_template(app: CLIApp, args: list[str]) -> CommandResponse:
        if not args:
            templates = ", ".join(available_templates()) or "(none)"
            return CommandResponse(
                messages=[
                    (
                        "system",
                        "Usage: /template <name> <destination> [--program <name>] [--author <pubkey>] [--program-id <id>] [--cluster <cluster>] [--force]\n"
                        f"Available templates: {templates}",
                    )
                ]
            )

        template_name = args[0].lower()
        if template_name not in available_templates():
            return CommandResponse(
                messages=[(
                    "system",
                    f"Unknown template '{template_name}'. Available: {', '.join(available_templates()) or '(none)'}"
                )]
            )

        defaults = app._default_template_metadata()
        options, error = _parse_template_tokens(template_name, args[1:], defaults)
        if error:
            return CommandResponse(messages=[("system", error)])
        if options is None:
            return CommandResponse(messages=[("system", "Unable to parse template options.")])
        try:
            output = render_template(options)
        except TemplateError as exc:
            return CommandResponse(messages=[("system", f"Template error: {exc}")])

        message = f"Template '{template_name}' rendered to {output}"
        tool_calls = [
            {
                "type": "command",
                "name": "/template",
                "status": "success",
                "summary": f"{template_name} → {output}",
            }
        ]
        return CommandResponse(messages=[("system", message)], tool_calls=tool_calls)

    @staticmethod
    def _handle_wallet(app: CLIApp, args: list[str]) -> CommandResponse:
        manager = app.wallet_manager
        if manager is None:
            return CommandResponse(messages=[("system", "Wallet manager unavailable in this session.")])

        if not args or args[0].lower() == "status":
            status = manager.status()
            balance = app._fetch_balance(status.public_key)
            app._update_wallet_metadata(status, balance=balance)
            if not status.exists:
                return CommandResponse(messages=[("system", "No wallet found. Run `/wallet create` to set one up.")])
            lock_state = "Unlocked" if status.is_unlocked else "Locked"
            balance_line = f"Balance: {balance:.3f} SOL" if balance is not None else "Balance: unavailable"
            message = "\n".join(
                [
                    f"Wallet {lock_state}",
                    f"Address: {status.public_key} ({status.masked_address})",
                    balance_line,
                ]
            )
            return CommandResponse(messages=[("system", message)])

        command, *rest = args
        command = command.lower()

        if command == "create":
            if manager.wallet_exists():
                return CommandResponse(
                    messages=[("system", "Wallet already exists. Delete the file manually or use `/wallet restore` with overwrite.")],
                )
            passphrase = app._prompt_secret("Create wallet passphrase", confirmation=True)
            status, mnemonic = manager.create_wallet(passphrase, force=True)
            balance = app._fetch_balance(status.public_key)
            app._update_wallet_metadata(status, balance=balance)
            balance_line = f" Balance {balance:.3f} SOL." if balance is not None else "."
            message = "\n".join(
                [
                    f"Created wallet {status.public_key} and unlocked it.{balance_line}",
                    "Recovery phrase (store securely):",
                    mnemonic,
                ]
            )
            return CommandResponse(messages=[("system", message)])

        if command == "restore":
            if not rest:
                secret = app._prompt_text("Paste secret key (JSON array, base58, or recovery phrase)")
            else:
                # allow `/wallet restore path/to/file`
                candidate = Path(rest[0]).expanduser()
                secret = candidate.read_text().strip() if candidate.exists() else " ".join(rest)
            passphrase = app._prompt_secret("Wallet passphrase", confirmation=True)
            try:
                status, mnemonic = manager.restore_wallet(secret, passphrase, overwrite=True)
            except WalletError as exc:
                app.console.print(f"[red]{exc}")
                return CommandResponse(messages=[("system", str(exc))])
            try:
                status = manager.unlock_wallet(passphrase)
            except WalletError:
                status = manager.status()
            balance = app._fetch_balance(status.public_key)
            app._update_wallet_metadata(status, balance=balance)
            restored_lines = [f"Wallet restored for {status.public_key}."]
            if status.is_unlocked:
                restored_lines.append("Wallet unlocked.")
            else:
                restored_lines.append("Use `/wallet unlock` to access.")
            if mnemonic:
                restored_lines.append("Recovery phrase saved from the provided words.")
            return CommandResponse(messages=[("system", " ".join(restored_lines))])

        if command == "unlock":
            initial_pass = app._prompt_secret("Wallet passphrase")
            try:
                status = manager.unlock_wallet(initial_pass)
            except WalletError:
                app.console.print("[yellow]Stored passphrase failed; please re-enter.[/yellow]")
                retry_pass = app._prompt_secret("Wallet passphrase", allow_master=False)
                try:
                    status = manager.unlock_wallet(retry_pass)
                except WalletError as exc:
                    return CommandResponse(messages=[("system", str(exc))])
            balance = app._fetch_balance(status.public_key)
            app._update_wallet_metadata(status, balance=balance)
            balance_line = f" Current balance {balance:.3f} SOL." if balance is not None else "."
            return CommandResponse(messages=[("system", f"Wallet unlocked for {status.public_key}.{balance_line}")])

        if command == "lock":
            status = manager.lock_wallet()
            app._update_wallet_metadata(status, balance=None)
            return CommandResponse(messages=[("system", "Wallet locked.")])

        if command == "export":
            passphrase = app._prompt_secret("Wallet passphrase")
            try:
                secret = manager.export_wallet(passphrase)
            except WalletError as exc:
                return CommandResponse(messages=[("system", str(exc))])
            if rest:
                target_path = Path(rest[0]).expanduser()
                app._write_secret_file(target_path, secret)
                return CommandResponse(messages=[("system", f"Exported secret to {target_path}")])
            return CommandResponse(messages=[("system", f"Exported secret: {secret}")])

        if command in {"phrase", "mnemonic"}:
            passphrase = app._prompt_secret("Wallet passphrase", allow_master=False)
            try:
                mnemonic = manager.get_mnemonic(passphrase)
            except WalletError as exc:
                return CommandResponse(messages=[("system", str(exc))])
            return CommandResponse(messages=[("system", f"Recovery phrase:\n{mnemonic}")])

        return CommandResponse(
            messages=[
                (
                    "system",
                    "Unknown wallet command. Available: `/wallet status`, `/wallet create`, `/wallet restore`, `/wallet unlock`, `/wallet lock`, `/wallet export`, `/wallet phrase`.",
                )
            ]
        )

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------
    def _render_message(self, role: str, message: str) -> None:
        if role == "user":
            panel_title = "You"
            style = "bold cyan"
        elif role == "agent":
            panel_title = "SolCoder"
            style = "green"
        else:
            panel_title = role.title()
            style = "magenta"
        text = Text(message, style=style)
        self.console.print(Panel(text, title=panel_title, expand=False))

    def _render_status(self) -> None:
        session_id = self.session_context.metadata.session_id
        metadata = self.session_context.metadata
        project_display = metadata.active_project or "unknown"
        wallet_display = metadata.wallet_status or "---"
        balance_display = (
            f"{metadata.wallet_balance:.3f} SOL" if metadata.wallet_balance is not None else "--"
        )
        spend_display = f"{metadata.spend_amount:.2f} SOL"
        input_limit = self._config_int("llm_input_token_limit", DEFAULT_LLM_INPUT_LIMIT)
        recent_input = metadata.llm_last_input_tokens or 0
        percent_input = min((recent_input / input_limit * 100) if input_limit else 0.0, 100.0)
        output_total = metadata.llm_output_tokens or 0
        tokens_display = (
            f"ctx in last {recent_input:,}/{input_limit:,} ({percent_input:.1f}%) • "
            f"out total {output_total:,}"
        )
        status = Text(
            f"Session: {session_id} • Project: {project_display} • Wallet: {wallet_display} • "
            f"Balance: {balance_display} • Spend: {spend_display} • Tokens: {tokens_display}",
            style="dim",
        )
        self.console.print(status)

    def _prompt_message(self) -> str:
        return "❯ "

    def _record(self, role: str, message: str, *, tool_calls: list[dict[str, Any]] | None = None) -> None:
        entry: dict[str, Any] = {
            "role": role,
            "message": message,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        if tool_calls:
            entry["tool_calls"] = tool_calls
        self.session_context.transcript.append(entry)
        if len(self.session_context.transcript) > TRANSCRIPT_LIMIT:
            del self.session_context.transcript[:-TRANSCRIPT_LIMIT]

    def _default_template_metadata(self) -> dict[str, str]:
        program_name = "counter"
        author_pubkey = "CHANGEME"
        if self.wallet_manager is not None:
            try:
                status = self.wallet_manager.status()
                if status.public_key:
                    author_pubkey = status.public_key
            except WalletError:
                pass
        return {"program_name": program_name, "author_pubkey": author_pubkey}

    def _prompt_secret(self, message: str, *, confirmation: bool = False, allow_master: bool = True) -> str:
        if allow_master and self._master_passphrase is not None:
            return self._master_passphrase
        while True:
            value = self.session.prompt(f"{message}: ", is_password=True)
            if not confirmation:
                return value
            confirm = self.session.prompt("Confirm passphrase: ", is_password=True)
            if value == confirm:
                return value
            self.console.print("[red]Passphrases do not match. Try again.[/red]")

    def _prompt_text(self, message: str) -> str:
        return self.session.prompt(f"{message}: ")

    def _update_wallet_metadata(self, status: WalletStatus, *, balance: float | None) -> None:
        metadata = self.session_context.metadata
        if not status.exists:
            metadata.wallet_status = "missing"
            metadata.wallet_balance = None
            return
        lock_state = "Unlocked" if status.is_unlocked else "Locked"
        address = status.masked_address if status.public_key else "---"
        metadata.wallet_status = f"{lock_state} ({address})"
        metadata.wallet_balance = balance

    def _fetch_balance(self, public_key: str | None) -> float | None:
        if not public_key or self.rpc_client is None:
            return None
        try:
            return self.rpc_client.get_balance(public_key)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Unable to fetch balance for %s: %s", public_key, exc)
            return None

    @staticmethod
    def _format_export_text(export_data: dict[str, object]) -> str:
        metadata = export_data.get("metadata", {})
        transcript = export_data.get("transcript", [])
        lines = ["Session Export", "=============="]
        if isinstance(metadata, dict):
            for key in (
                "session_id",
                "created_at",
                "updated_at",
                "active_project",
                "wallet_status",
                "wallet_balance",
                "spend_amount",
            ):
                if key in metadata and metadata[key] is not None:
                    lines.append(f"{key.replace('_', ' ').title()}: {metadata[key]}")
        lines.append("")
        lines.append("Transcript (most recent first):")
        if isinstance(transcript, list) and transcript:
            for entry in transcript:
                if isinstance(entry, dict):
                    role = entry.get("role", "?")
                    message = entry.get("message", "")
                    timestamp = entry.get("timestamp")
                    prefix = f"{timestamp} " if timestamp else ""
                    lines.append(f"{prefix}[{role}] {message}")
                    tool_calls = entry.get("tool_calls")
                    if isinstance(tool_calls, list):
                        for tool_call in tool_calls:
                            if not isinstance(tool_call, dict):
                                continue
                            call_type = tool_call.get("type", "tool")
                            name = tool_call.get("name") or ""
                            status = tool_call.get("status") or ""
                            summary = tool_call.get("summary") or ""
                            details = " • ".join(
                                part for part in (name, status, summary) if part
                            )
                            lines.append(f"    ↳ {call_type}: {details}")
                else:
                    lines.append(str(entry))
        else:
            lines.append("(no transcript available)")
        return "\n".join(lines)

    @staticmethod
    def _format_env_diag(results: list[DiagnosticResult]) -> str:
        lines = ["Environment Diagnostics", "======================"]
        header = f"{'Tool':<22} {'Status':<8} Details"
        lines.append(header)
        lines.append("-" * len(header))
        for item in results:
            status_label = {
                "ok": "OK",
                "warn": "WARN",
                "missing": "MISSING",
                "error": "ERROR",
            }.get(item.status, item.status.upper())
            if item.found and item.version:
                detail = item.version
            elif item.found:
                detail = "Detected (version unavailable)"
            else:
                detail = "Not found in PATH"
            if item.details:
                detail = f"{detail} ({item.details})"
            lines.append(f"{item.name:<22} {status_label:<8} {detail}")
            if item.remediation and status_label != "OK":
                lines.append(f"    ↳ {item.remediation}")
        return "\n".join(lines)

    def _write_secret_file(self, target: Path, secret: str) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(secret)
        try:
            os.chmod(target, 0o600)
        except PermissionError:
            pass

    def _persist(self) -> None:
        if self.session_manager is not None:
            self.session_manager.save(self.session_context)

    @staticmethod
    def _default_console() -> Console:
        force_style = os.environ.get("SOLCODER_FORCE_COLOR")
        no_color = os.environ.get("SOLCODER_NO_COLOR") is not None or os.environ.get("NO_COLOR") is not None
        if force_style:
            return Console(force_terminal=True)
        if no_color or not sys.stdout.isatty():
            return Console(no_color=True, force_terminal=False, color_system=None)
        return Console()
