# Task 2.5b — Agentic Tool Loop

- Milestone: [MILESTONE-2_CONVERSATIONAL_CORE](../milestones/MILESTONE-2_CONVERSATIONAL_CORE.md)
- Status: Proposed (next up after 2.5)

## Objective
Teach the SolCoder LLM bridge to operate in an agentic loop: every LLM turn should receive the active toolkit/tool manifest, decide whether to respond directly or invoke a registry tool, and exchange structured JSON describing the chosen action. Responses can take three shapes: (1) a final reply for the user, (2) a tool request with a short “step title” describing the action, or (3) a mixed response that emits a user-facing message while requesting another tool. The CLI becomes the orchestrator that parses LLM decisions, runs tools, streams the step titles and tool outputs back to the user, and feeds those results into the conversation until the LLM returns a final answer.

## Deliverables
- JSON schema for LLM⇄orchestrator messages (fields for `type: reply|tool_request|tool_result|plan|cancel`, optional `message` when the LLM wants to address the user, step title, tool name, arguments, etc.).
- First-turn plan phase: the LLM should begin with `{type: "plan", steps: [...]}` so we can render a checklist (reusing the planning tool for default content) before executing any tools.
- Conversation driver that wraps `_chat_with_llm` in a loop: send system prompt + manifest, receive JSON, branch on action, execute tool via registry when requested, append tool output, repeat until `reply`.
- Tool manifest generator that enumerates toolkits/tools (name, description, args schema) and injects it into the system prompt each turn, so the LLM has the latest capability map.
- Safety checks: unknown tool -> error response, schema validation, argument validation before execution.
- UI preview of agent progress: show the step titles and tool call results inline so the user can track what the agent is doing in real time.
- Tests covering direct reply, single tool call, multi-step tool loop, malformed payload fallback, and UI preview rendering.

## Key Steps
1. **Schema design** – Draft a JSON schema (or Pydantic model) describing LLM directives, including `type`, `step_title`, optional `message`, optional `tool` object with `name`, `args` dict, and a flag for whether the LLM expects more tool iterations.
2. **Manifest injection** – Build a serialiser that walks `ToolRegistry.available_toolkits()` to produce a compact manifest (toolkit name/version/description, tool list with names/descriptions/args schema) for the system prompt.
3. **Loop controller** – Replace the one-shot `_chat_with_llm` call with a controller that:
   - Sends user message + manifest to LLM.
   - Parses JSON response (with validation).
   - Displays any `message` field returned by the LLM to the user immediately.
   - Executes tool when requested (including accumulating tool outputs into the transcript and returning the tool result to the LLM as context).
   - Iterates until LLM returns `type="reply"`.
   - Supports Ctrl+C cancellation by propagating a `{type:"cancel"}` directive to the loop and enforcing tool timeouts.
4. **Error handling** – Define fallback responses when the LLM returns invalid JSON, unknown tool, or tool execution raises `ToolInvocationError`; ensure the loop breaks gracefully.
5. **Transcript & UI updates** – Record each tool request/result pair (with the provided step title), display the step title and tool output as a progress preview to the user, and surface the final reply only once the loop concludes.
6. **Schema repair path** – Implement one automated retry when the LLM emits invalid JSON (return a structured error describing the issue), then fall back to a user-facing error message if the second attempt fails.

## Dependencies
- Task 2.5 (tool registry + CLI hooks)
- Task 2.5a (LLM streaming client) for retries and token accounting

## Acceptance Criteria
- System prompt contains toolkit/tool manifest every turn.
- LLM response is parsed as JSON; invalid payloads trigger a retry/fallback with explanatory message.
- Tool invocations happen only through the registry, include a human-readable step title, and are logged in the transcript/preview.
- Multiple sequential tool calls are supported before final reply.
- UI preview shows the step titles and tool results while work is in progress.
- Users can interrupt the loop (Ctrl+C), causing a cancel directive and graceful tool termination.
- The first turn always returns a plan checklist before tool execution.
- One automatic JSON repair pass is attempted; subsequent failures produce a clear error message for the user.
- Unit/integration tests cover success, failure, cancellation, plan rendering, JSON repair, and preview rendering flows of the agentic loop.

## Notes
- Start with a deterministic JSON contract (no Markdown) to keep parsing simple.
- Consider adding a `max_iterations` guard (configurable) to prevent infinite tool loops.
