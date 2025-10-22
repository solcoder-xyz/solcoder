# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

SolCoder is a CLI-first AI coding agent that scaffolds, deploys, and funds Solana dApps through natural language prompts. It operates as an interactive REPL backed by an agent loop that orchestrates deterministic tools while maintaining conversational state.

**Key Architectural Principle**: SolCoder separates concerns into layers—CLI presentation, core orchestration, and domain-specific integrations—enabling flexible tool composition and testability without tight coupling.

---

## Development Commands

### Setup
```bash
poetry install                                    # Install dependencies
poetry run solcoder                               # Launch the agent REPL
poetry run solcoder --session <id>                # Resume previous session
poetry run solcoder --new-session                 # Force fresh context
poetry run solcoder --template counter ./my-counter --program my_counter  # Scaffold from template
```

### Testing & Quality
```bash
poetry run pytest                                 # Full test suite
poetry run pytest -m "not slow"                   # Fast feedback loop (skip slow tests)
poetry run pytest --maxfail=1                     # Stop at first failure
poetry run pytest --cov=solcoder                  # Coverage report (target ≥80% in core/solana)
poetry run ruff check src tests                   # Lint Python sources
poetry run black src tests                        # Format code
poetry run black src tests --check               # Check formatting (CI mode)
```

### LLM & Configuration
```bash
poetry run solcoder --dry-run-llm                 # Test LLM connectivity once
poetry run solcoder --offline-mode                # Use stub responses (no network)
poetry run solcoder --llm-provider openai         # Override provider
poetry run solcoder --llm-model gpt-5-codex       # Override model
poetry run solcoder --llm-reasoning <low|medium|high>  # Set reasoning effort
poetry run solcoder --dump-session <id>           # Export session transcript
```

### Knowledge Base
```bash
poetry run python scripts/build_kb_index.py       # Rebuild embeddings after editing knowledge files
# In REPL: /kb search <query>                     # Search knowledge base
```

### Project Layout
- `src/solcoder/cli/` — Prompt Toolkit REPL, command router, UI widgets
- `src/solcoder/core/` — Orchestration (agent loop, tool registry, config, session, LLM client)
- `src/solcoder/solana/` — Wallet, RPC adapters, build/deploy flows
- `src/solcoder/anchor/blueprints/` — Reusable Anchor blueprints (counter, token, nft, registry, escrow)
- `tests/` — Mirrors package layout; includes e2e fixtures
- `docs/` — PRD, roadmap (milestones, todo, in_progress, done), WBS
- `knowledge/` — Curated Solana docs for semantic search

---

## Core Architecture Patterns

### 1. The Agent Loop Pattern (LLM + Tool Orchestration)

**Location**: `src/solcoder/core/agent_loop.py`, `src/solcoder/core/agent.py`

The heart of SolCoder is a structured agent loop that:

1. **Plan Phase**: LLM receives user prompt and emits a `plan` directive with steps
2. **Tool Execution**: Agent requests tools with `tool_request` directives; tools execute synchronously
3. **Result Feedback**: LLM receives structured `tool_result` JSON for context
4. **Completion**: LLM emits `reply` directive (or `cancel` on failure)
5. **State Compaction**: Transcript is summarized if it exceeds token limits

**Key Insight**: The loop enforces a **JSON schema contract** between LLM and orchestrator:
- LLM always responds with single JSON object matching `AgentDirective` schema
- Orchestrator validates, retries on parse errors, then invokes tools or transitions state
- This prevents free-form text confusion and ensures deterministic execution

**Code Flow**:
```
CLIApp.handle_line(user_input)
  → routes to CLIApp._chat_with_llm()
  → creates AgentLoopContext with tool registry + config
  → calls run_agent_loop()
    ┌─ iteration loop (max 1000 iterations)
    ├─ calls llm.stream_chat() with system_prompt + manifest + history
    ├─ parses JSON reply as AgentDirective
    ├─ if "plan": stores steps in TODO manager, awaits plan_ack
    ├─ if "tool_request": invokes tool via registry, feeds result back
    ├─ if "reply" or "cancel": breaks loop and returns CommandResponse
    └─ accumulates token usage + latency metrics
```

### 2. Tool Registry + Toolkit Pattern

**Location**: `src/solcoder/core/tool_registry.py`, `src/solcoder/core/tools/`

Tools are organized in **toolkits** (logical groups) and registered centrally:

```python
# Tool structure
Tool(
    name="generate_plan",
    description="...",
    input_schema={...},  # JSON schema
    output_schema={...},
    handler=callable  # (payload: dict) -> ToolResult
)

# Toolkit groups tools
Toolkit(name="solcoder.planning", version="1.0.0", tools=[...])

# Registry stores and invokes
registry = ToolRegistry([toolkit1, toolkit2, ...])
registry.invoke("generate_plan", {"goal": "..."})
```

**Key Design**:
- **Manifest Generation**: `build_tool_manifest()` serializes registry to compact JSON for LLM context
- **Policy Enforcement**: Future expansion for tool policies (allow/confirm/deny)
- **Loose Coupling**: Tools don't know about CLI; they accept dict payloads and return ToolResult
- **Built-in Toolkits**: `plan_toolkit`, `code_toolkit`, `deploy_toolkit`, `diagnostics_toolkit`, `knowledge_toolkit`, `review_toolkit`, `command_toolkit`

### 3. Configuration Layering

**Location**: `src/solcoder/core/config.py`

SolCoder uses **three-tier configuration**:

1. **Global** (`~/.solcoder/config.toml`): User defaults, network, LLM provider
2. **Project** (`<workspace>/.solcoder/config.toml`): Project-specific overrides
3. **CLI Flags**: Runtime overrides (highest priority)

**Encryption Model**:
- LLM API key stored in `~/.solcoder/credentials.json` encrypted with PBKDF2 + Fernet
- User enters passphrase once per session; decrypted key held in `ConfigContext`
- Config validated via Pydantic; missing values use SolCoderConfig defaults

**Config Structure**:
```python
SolCoderConfig(
    llm_provider="openai",  # or "anthropic"
    llm_model="gpt-5-codex",
    llm_base_url="https://api.openai.com/v1",
    llm_reasoning_effort="medium",  # or "low"/"high"
    max_session_spend=0.2,  # SOL budget
    network="devnet",
    rpc_url="https://api.devnet.solana.com",
    history_max_messages=20,
    history_auto_compact_threshold=0.95,
    # ... more fields for token limits, compaction cooldown, etc.
)
```

### 4. LLM Integration Pattern

**Location**: `src/solcoder/core/llm/`

LLM abstraction supports multiple providers via a pluggable **transport layer**:

**Interface** (`LLMBackend` Protocol):
```python
stream_chat(
    prompt: str,
    system_prompt: str | None,
    history: Sequence[dict[str, str]] | None,
    on_chunk: Callable[[str], None] | None
) -> LLMResponse
```

**Implementations**:
- `LLMClient`: Live HTTP streaming with retry logic (exponential backoff)
- `StubLLM`: Offline fallback with scripted responses (for demos)

**Provider Support**:
- OpenAI Responses API → endpoint: `/responses`, payload uses `"input": messages`, reasoning effort
- Anthropic → endpoint: `/messages`, headers: `x-api-key` + `anthropic-version`
- Generic OpenAI-compatible → `/chat/completions` (fallback)

**Streaming**:
- Consumes SSE stream, extracts chunks per provider format
- `on_chunk` callback fires incrementally (for rendering progress)
- Returns `LLMResponse` with text, latency, token usage, finish reason

**Offline Mode**: `--offline-mode` flag replaces live calls with `offline_response()` stubs

### 5. Session & State Management

**Location**: `src/solcoder/session/`, `src/solcoder/core/context.py`

Each SolCoder run is a **session** with isolated state:

```python
SessionContext(
    metadata=SessionMetadata(
        session_id="abc123def456",  # 12-char UUID hex
        created_at=datetime,
        active_project="/path/to/project",
        wallet_status="Unlocked",
        wallet_balance=1.5,
        llm_input_tokens=5000,
        llm_output_tokens=2000,
        compression_cooldown=0,  # for history compaction
    ),
    transcript=[  # list of dicts
        {"role": "user", "message": "...", "timestamp": "..."},
        {"role": "agent", "message": "...", "timestamp": "...", "tool_calls": [...]},
        {"role": "system", "message": "...", "summary": True},  # compacted
    ]
)
```

**Persistence**:
- Sessions stored in `~/.solcoder/sessions/<session_id>/state.json`
- TODO list in separate `todo.json`
- Maximum 20 sessions retained (rotation by mtime)

**Resumption**:
- `solcoder --session <id>` loads from disk; history reconstructed
- Fresh context built on next LLM turn (no background indexing)

**History Compaction** (`RollingHistoryStrategy`):
- Monitors transcript length and input token estimates
- Summarizes older entries via LLM when threshold hit (e.g., 95% of token limit)
- Replaces old turns with single system message containing summary
- Cooldown prevents thrashing compaction

### 6. Conversation Context Manager

**Location**: `src/solcoder/core/context.py` (`ContextManager` class)

Bridges session state and LLM:

```python
ContextManager(
    session_context=session,
    llm=llm_backend,
    config_context=config,
    strategy=RollingHistoryStrategy()  # pluggable
)

# Converts transcript to LLM format
history = context_manager.conversation_history()
# Handles recording new messages
context_manager.record("agent", message, tool_calls=[...])
# Manages compaction
context_manager.compact_history_if_needed()
```

**Design**:
- Transcript stored as raw dicts (flexible schema); `conversation_history()` normalizes to `[{"role": ..., "content": ...}]` for LLM
- System entries (summaries) mapped to `role="system"` in LLM history
- Token estimation is word-count based (conservative)
- Compaction cooldown prevents excessive summarization

---

## Module Interactions

### 1. CLI Layer → Core Orchestration

```
src/solcoder/cli/
├── app.py (CLIApp)
│   ├─ Uses PromptSession (prompt_toolkit) for REPL
│   ├─ Registers slash commands via CommandRouter
│   ├─ Calls run_agent_loop() for non-slash input
│   └─ Manages StatusBar for rendering wallet + logs
│
├── commands/
│   ├─ env.py, wallet.py, template.py, etc.
│   └─ Each registers SlashCommand(name, handler, help_text)
│
└── types.py
    ├─ CommandResponse (messages, tool_calls, rendered_roles)
    ├─ CommandRouter (dispatches by name)
    └─ LLMBackend protocol
```

**Flow**: User input → `CLIApp.handle_line()` → slash command routing or agent loop

### 2. Core Orchestration ↔ Tools

```
src/solcoder/core/
├── agent_loop.py
│   └─ run_agent_loop(context) iterates, invokes tools via registry
│
├── tool_registry.py
│   └─ Registry.invoke(name, payload) → tool.handler(payload) → ToolResult
│
└── tools/
    ├─ base.py (Tool, Toolkit, ToolResult dataclasses)
    └─ *.py (plan, code, deploy, etc.)
```

**Key Insight**: Agent loop knows nothing about tool implementations; it only knows:
- Invoke by name
- Get ToolResult back with content + optional data payload
- Catch ToolInvocationError

### 3. Configuration ↔ CLI & Core

```
ConfigManager (config.py)
├─ Handles bootstrap (first-time setup wizard)
├─ Manages credential encryption/decryption
├─ Loads config.toml from global/project/override paths
└─ Returns ConfigContext (config + decrypted API key)

CLIApp instantiation:
├─ Calls ConfigManager.ensure() at startup
├─ Injects ConfigContext into AgentLoopContext
└─ Config used for LLM settings, history limits, tool policies
```

### 4. Wallet Integration

```
WalletManager (solana/wallet.py)
├─ Secure keypair storage with PBKDF2 + AESGCM
├─ Mnemonic generation/validation (BIP39)
├─ Lock/unlock semantics

CLIApp.session_context.metadata.wallet_*
├─ Reflects wallet status for status bar

SolanaRPCClient (solana/rpc.py)
├─ Thin HTTP wrapper for JSON-RPC calls
└─ Used to fetch balance for status display
```

### 5. Session Persistence

```
SessionManager (session/manager.py)
├─ start(session_id=None, active_project=None)
├─ save(context) writes state.json + enforces rotation
├─ export_session(session_id, redact=True) for debugging
└─ load_todo(session_id) for TODO recovery

CLIApp._persist()
├─ Called after each handle_line()
├─ Saves to SessionManager
└─ Also saves TODO state separately
```

---

## Critical Implementation Details

### 1. Agent Directive Parsing & Validation

**Location**: `src/solcoder/core/agent.py` (`AgentDirective`, `parse_agent_directive()`)

LLM output must be **single JSON object** (no Markdown):

```python
# Valid directives
{"type": "plan", "steps": ["Step 1", "Step 2"], "message": "Intro text"}
{"type": "tool_request", "step_title": "Running build", "tool": {"name": "deploy_anchor", "args": {...}}}
{"type": "reply", "message": "Here's the result..."}
{"type": "cancel", "message": "Cannot proceed because..."}

# Validation happens here:
try:
    directive = parse_agent_directive(llm_response_text)
except AgentMessageError:
    # Retry with error JSON in loop
    pending_prompt = {"type": "error", "message": "...", "details": "..."}
```

**System Prompt Injection**: Manifest JSON is embedded in system prompt:

```python
system_prompt = (
    "You are SolCoder. Always respond with single JSON matching schema.\n"
    "Schema: {...}\n"
    "Rules: ...\n"
    f"Available tools: {manifest_json}\n"
)
```

### 2. TODO Tracking Integration

**Location**: `src/solcoder/core/todo.py`, `src/solcoder/core/tools/todo.py`

TODO manager coordinates with agent loop:

```python
# Agent generates plan with steps
{"type": "plan", "steps": ["Build contract", "Deploy", "Test"]}

# Agent loop calls _bootstrap_plan_into_todo()
# → Creates TODO tasks from steps
# → Displays TODO list to user
# → Sets show_todo_list=true in tool result payloads

# Agent updates entire checklist in one call
todo_update_list(tasks=[
    {"name": "Write tests", "status": "in_progress"},
    {"name": "Ship docs", "status": "todo"}
], override=True)

# Loop enforces: if TODO items exist and not acknowledged, 
# agent must reply with "complete" or use tools first
```

### 3. Status Bar & Live Updates

**Location**: `src/solcoder/cli/status_bar.py`

Uses prompt_toolkit's bottom toolbar for real-time display:

```
Session: abc123 | Workspace: ~/my-dapp | Wallet: Unlocked (5.2 SOL) | Mode: assistive | Logs: 3
```

**Updates**:
- `_refresh_status_bar()` invalidates prompt_toolkit app on log changes
- Renders live during agent loop via `console.status()` spinner
- LogBuffer subscribers notify StatusBar of new events

### 4. Tool Manifest Serialization

**Location**: `src/solcoder/core/agent.py` (`build_tool_manifest()`, `manifest_to_prompt_section()`)

Generates compact JSON for LLM:

```python
manifest = [
    {
        "toolkit": "solcoder.planning",
        "version": "1.0.0",
        "description": "...",
        "tools": [
            {
                "name": "generate_plan",
                "description": "...",
                "input_schema": {...},  # Full JSON schema
                "required": ["goal"]
            }
        ]
    },
    {...more toolkits...}
]

manifest_json = json.dumps(manifest, separators=(",", ":"))  # Compact
```

### 5. Streaming Response Handling

**Location**: `src/solcoder/core/llm/transport.py` (`consume_stream()`)

Handles provider-specific SSE formats:

```python
# OpenAI Responses API
data: {"type": "response.output_text", "text": "chunk"}
data: {"type": "response.completed", "response": {"usage": {...}}}

# Anthropic
data: {"type": "content_block_delta", "delta": {"text": "chunk"}}

# Generic /chat/completions
data: {"choices": [{"delta": {"content": "chunk"}}]}

# consume_stream() handles all, yields text chunks + finish_reason + usage
```

### 6. Wallet Encryption

**Location**: `src/solcoder/solana/wallet.py`

Multi-layered security:

```
User Passphrase
    ↓ (PBKDF2 390k iterations)
AES Key (256-bit)
    ↓ (AES-GCM with random nonce)
Encrypted Payload
    ├─ private_key (base64 of 64 bytes: 32-byte secret + 32-byte public)
    ├─ mnemonic (optional)
    └─ metadata

On disk: JSON with salt, nonce, ciphertext (all base64)
In memory: DecryptedPayload (private_key bytes, mnemonic string)
```

**Usage**:
```python
status, mnemonic = wallet.create_wallet(passphrase)
wallet.unlock_wallet(passphrase)  # Decrypts and caches Ed25519PrivateKey
private_key = wallet.get_private_key()  # Returns cached key (must be unlocked)
wallet.lock_wallet()  # Clears cached key
```

### 7. Error Handling in Agent Loop

**Location**: `src/solcoder/core/agent_loop.py`

Three types of errors:

1. **Parse Error** → Retry with error JSON
   ```python
   pending_prompt = json.dumps({"type": "error", "message": "...", "details": "..."})
   # Loop continues with error as next input
   ```

2. **Tool Error** → Tool fails, result fed back
   ```python
   status = "error"
   output = str(exc)
   # LLM receives tool_result with error status
   ```

3. **Fatal Error** (LLM unreachable, invalid config) → Break and return error message

---

## Testing Patterns & Structure

**Location**: `tests/` (mirrors `src/solcoder/` layout)

### Test Organization
```
tests/
├─ cli/
│  ├─ test_shell.py (ScriptedLLM fixture for deterministic agent loops)
│  ├─ test_tool_commands.py
│  └─ test_branding.py
├─ core/
│  ├─ test_tool_registry.py
│  ├─ test_llm_client.py
│  ├─ test_config.py
│  ├─ test_todo_toolkit.py
│  └─ test_templates.py
├─ solana/
│  ├─ test_wallet.py
│  └─ test_rpc.py
├─ session/
│  └─ test_manager.py
└─ e2e/ (integration tests)
```

### Key Fixtures

**`ScriptedLLM`** (`tests/cli/test_shell.py`):
```python
# Pre-canned responses for deterministic testing
scripted_llm = ScriptedLLM([
    {"type": "plan", "steps": ["step1", "step2"]},
    {"type": "tool_request", "tool": {"name": "generate_plan", "args": {...}}},
    {"type": "reply", "message": "Done!"}
])

# Each call to stream_chat() replays next item from script
# Allows testing agent loop state machine without network
```

**`RPCStub`** (`tests/cli/test_shell.py`):
```python
# Mocks Solana RPC responses
rpc_stub = RPCStub(balances=[1.0, 0.5])  # Queue of balance responses
```

### Coverage Goals
- Target ≥80% in `src/solcoder/core` and `src/solcoder/solana`
- Mock all external I/O (HTTP, RPC, file system where possible)
- Use pytest with `asyncio_mode = strict` for async tests

### Running Tests
```bash
poetry run pytest                       # Full suite
poetry run pytest -m "not slow"         # Fast feedback loop
poetry run pytest --cov=solcoder        # Coverage report
poetry run ruff check src tests          # Linting
poetry run black src tests --check       # Format check
```

---

## Configuration System Deep Dive

### Configuration Resolution Order
1. CLI flags (highest priority)
2. Environment variables (e.g., `SOLCODER_LLM_MODEL`)
3. Override config file (if specified)
4. Project config (`.solcoder/config.toml`)
5. Global config (`~/.solcoder/config.toml`)
6. Pydantic defaults (lowest priority)

### Credential Encryption Flow

**Setup** (`ConfigManager._bootstrap_config()`):
1. User enters LLM base URL, model, reasoning effort
2. User enters API key (hidden input)
3. User creates passphrase (with confirmation)
4. `CredentialStore.save(passphrase, api_key)` encrypts and writes
5. Config (minus API key) saved to TOML

**Load** (`ConfigManager._load_api_key()`):
1. User provides passphrase
2. `CredentialStore.load(passphrase)` decrypts
3. On failure, retry up to 3 times
4. Returns `(api_key, passphrase)` tuple for ConfigContext

### History Compaction Strategy

**When triggered**:
- Transcript exceeds `history_max_messages` (default 20)
- OR LLM input tokens exceed `history_auto_compact_threshold * llm_input_token_limit` (default 95% of 272k tokens)

**Mechanism**:
```python
RollingHistoryStrategy.compact(manager):
    if len(transcript) > limit and cooldown <= 0:
        # Keep last N entries (history_summary_keep, default 10)
        # Summarize older entries via LLM
        # Replace with single system message: "Summary: ..."
        # Set cooldown to history_compaction_cooldown (default 10 turns)
```

---

## Data Flow Example: User Request

```
User: "Build a counter program"
  ↓
CLIApp.handle_line("Build a counter program")
  ├─ ContextManager.record("user", "Build a counter program")
  └─ CLIApp._chat_with_llm("Build a counter program")
     ├─ Creates AgentLoopContext with:
     │  ├─ prompt = "Build a counter program"
     │  ├─ history = ContextManager.conversation_history()  (normalized for LLM)
     │  ├─ tool_registry = default registry (7 toolkits)
     │  ├─ llm = LLMClient (live or stub)
     │  └─ config_context = global + project config merged
     │
     └─ run_agent_loop(context)
        ├─ Iteration 1:
        │  ├─ manifest_json = build_tool_manifest(registry)
        │  ├─ system_prompt = _agent_system_prompt() with manifest + config details
        │  ├─ llm.stream_chat(prompt, history, system_prompt, on_chunk)
        │  │  ├─ HTTP POST to LLM endpoint (OpenAI /responses, Anthropic /messages, etc.)
        │  │  └─ Returns LLMResponse(text='{"type":"plan","steps":[...]}', ...)
        │  ├─ parse_agent_directive(text) → AgentDirective(type="plan", steps=[...])
        │  ├─ _bootstrap_plan_into_todo(steps) → Creates TODO tasks, renders
        │  └─ pending_prompt = AGENT_PLAN_ACK (JSON: {"type":"plan_ack"})
        │
        ├─ Iteration 2:
        │  ├─ llm.stream_chat(AGENT_PLAN_ACK, updated_history, system_prompt)
        │  ├─ Receives tool_request for "deploy_anchor"
        │  ├─ registry.invoke("deploy_anchor", {"program_name": "counter", ...})
        │  │  └─ Tool handler returns ToolResult(content="...", data={...})
        │  ├─ Renders tool preview to user
        │  └─ pending_prompt = AgentToolResult JSON
        │
        ├─ Iteration 3+: (similar tool invocations)
        │
        └─ Final:
           ├─ llm.stream_chat() returns reply directive
           ├─ Renders final message to user
           ├─ ContextManager.compact_history_if_needed()
           └─ Returns CommandResponse(messages=[(role, msg), ...], tool_calls=[...])

CLIApp.handle_line() returns CommandResponse
  ├─ Displays messages to user
  ├─ Records tool_calls in transcript
  └─ Calls CLIApp._persist() → saves to SessionManager

User sees completed response + status bar updated
```

---

## Key Design Principles

### 1. **Separation of Concerns**
- **CLI** handles only rendering, input, command dispatch
- **Core** owns orchestration, state, tool invocation logic
- **Solana** handles wallet, RPC, deployment-specific logic
- **Tools** are stateless handlers; registry decouples invocation from definition

### 2. **Determinism & Auditability**
- Agent loop is fully deterministic (same LLM output → same actions)
- All tool calls logged to transcript with metadata
- Sessions can be exported/inspected; sensitive data redacted
- No background services or async state; everything runs inline in REPL

### 3. **Graceful Degradation**
- Offline mode with stub LLM for demos
- Configurable tool policies for future sandboxing
- History compaction prevents token limit crashes
- Retry logic in LLM client with exponential backoff

### 4. **User Control**
- Three-tier config allows both global defaults and project-specific overrides
- CLI flags override everything
- Tool visibility via `/toolkits list` and `/toolkits <name> tools`
- TODO manager accessible via CLI and tool interface

### 5. **Minimal External Dependencies**
- No background services (embeddings are local FAISS files, optional)
- No persistent vector DB; context lives in memory
- Sessions are just JSON files on disk
- Can work offline with `--offline-mode`

---

## Common Extension Points

### Adding a New Tool
1. Create handler function: `(payload: dict) -> ToolResult`
2. Wrap in `Tool` dataclass with schema + description
3. Group in `Toolkit` with related tools
4. Implement factory function: `def my_toolkit() -> Toolkit: ...`
5. Add to `DEFAULT_TOOLKIT_FACTORIES` in `src/solcoder/core/tools/__init__.py`

### Adding a New Slash Command
1. Create module in `src/solcoder/cli/commands/my_command.py`
2. Implement handler: `def handle_my_command(app: CLIApp, args: list[str]) -> CommandResponse: ...`
3. Call `router.register(SlashCommand("my_command", handle_my_command, help_text))`
4. Add registration call to `register_builtin_commands()`

### Customizing History Compaction
1. Subclass `HistoryCompactionStrategy`
2. Implement `compact()` and `force_compact()` methods
3. Inject custom strategy into `ContextManager` constructor

### Supporting New LLM Provider
1. Add provider-specific logic to `build_endpoint()`, `build_headers()`, `build_payload()` in `llm/transport.py`
2. Add parsing logic to `_handle_response_event()` for provider's stream format
3. Update system prompt generator if needed for model-specific instructions

---

## Performance & Scalability Notes

### Token Management
- History compaction prevents runaway context growth
- Configurable token limits per provider (OpenAI 272k input, 128k output)
- Word-based estimation is conservative; actual tokens may vary
- Compression cooldown prevents rapid compaction cycles

### Session Rotation
- Maximum 20 sessions kept in `~/.solcoder/sessions/`
- Older sessions deleted on rotation (mtime-based)
- Each session's state.json is ~10-50 KB

### Network Resilience
- LLM client has configurable retry (default 2 max retries)
- Exponential backoff: 1.5^attempt seconds
- Timeout configurable (default 30s for LLM, 10s for RPC)

---

## Debugging & Development Tips

### Dry-Run LLM Connectivity
```bash
poetry run solcoder --dry-run-llm
# Hits live LLM once to verify config + API key before launching REPL
```

### Offline Mode (Demos)
```bash
poetry run solcoder --offline-mode
# Uses stub responses; no network calls
```

### Session Export & Inspection
```bash
poetry run solcoder --dump-session <session_id>
# Exports transcript as JSON (with secrets redacted by default)
```

### Environment Variables
- `SOLCODER_HOME`: Config/session/wallet directory (default `~/.solcoder`)
- `SOLCODER_LLM_MODEL`, `SOLCODER_LLM_BASE_URL`, `SOLCODER_LLM_API_KEY`: Credentials (for scripting)
- `SOLCODER_AGENT_MODE`: Agent mode (default "assistive")
- `SOLCODER_FORCE_COLOR`, `SOLCODER_NO_COLOR`: Terminal color control

### Logging
- Python logging via `structlog`; configure with `getLogger(__name__)`
- File logs in `<project>/.solcoder/logs/`
- Structured entries for audit trail

### Pydantic Validation
- Config and Wallet payloads validated at load time
- Errors raise `ConfigurationError` or `WalletError` with user-friendly messages
- Catch validation failures early to guide users through fixes

---

## Future Expansion Hooks

The architecture enables these planned features (per roadmap):

1. **Web Search** (TASK-3.7): Add tool that calls external search API, inject results into context
2. **KB Embeddings** (TASK-2.15): FAISS index for semantic search; load at startup if present
3. **Tool Policies** (roadmap phase 4): Check `tool_controls` config dict on invoke; prompt user if "confirm"
4. **Context Builder** (TASK-2.11): Extract relevant files from workspace; `@filename` mentions in prompts
5. **Build/Deploy Adapters** (TASK-2.4): Standardized interface for build systems (anchor, hardhat, etc.)
6. **Command Runner** (TASK-2.9): Safe subprocess wrapper for tests, builds, deployments

---

## Summary

SolCoder's architecture is built on **structured orchestration**: a synchronous agent loop that plans work, invokes deterministic tools, feeds results back, and maintains conversational context with intelligent compression. The layered design keeps concerns isolated (CLI, core, domain), making the system testable, extensible, and auditable. Configuration uses industry-standard layering (global/project/CLI), and cryptographic security protects user credentials at rest and in transit.

The core insight is **JSON contract enforcement**: by requiring the LLM to respond with schema-compliant JSON, the orchestrator achieves deterministic tool routing without ambiguity or free-form parsing. Combined with aggressive history compaction and session persistence, this enables multi-turn conversations with LLMs over long workflows without memory leaks or context overflow.

---

## Coding Guidelines & Best Practices

### Style & Formatting
- **Format**: Black with 88-character lines, 4-space indents
- **Linting**: Satisfy Ruff before committing (`poetry run ruff check src tests`)
- **Type Hints**: Required for all public APIs
- **Naming**:
  - `snake_case` for functions/variables
  - `CamelCase` for classes
  - `UPPER_SNAKE_CASE` for constants
- **Module Names**: Mirror command names (e.g., `deploy.py`, `wallet.py`)
- **Comments**: Brief, purposeful comments ahead of complex logic; keep documentation in Markdown under `docs/`

### Testing Requirements
- Use `pytest` with fixtures that mock Solana RPC interactions
- Maintain **≥80% coverage** in `src/solcoder/core` and `src/solcoder/solana`
- Add regression tests for every fix or feature
- Structure tests alongside modules (e.g., `tests/solana/test_wallet.py`)
- Run `poetry run pytest --maxfail=1` before merging
- Use `ScriptedLLM` fixture for deterministic agent loop testing
- Use `RPCStub` for mocking Solana RPC

### Commit & PR Guidelines
- **Commit Format**: Conventional Commits (`feat:`, `fix:`, `chore:`) in present tense, <60 chars
- **PR Requirements**:
  - Link relevant roadmap task
  - Note test and lint runs
  - Include CLI output for UX changes
- **Pre-commit**: Ensure `ruff`, `black --check`, `pytest` pass locally

### Security & Configuration
- **Global config**: `~/.solcoder/config.toml`
- **Project config**: `<workspace>/.solcoder/config.toml` (overrides global)
- **CLI flags**: Highest priority (override everything)
- **Solana keys**: Store under `~/.solcoder/keys/`
- **Tool policies**: Respect `allow`, `deny`, `confirm` through registry
- **Wallet flows**: Complete `/wallet create`, `/wallet restore`, `/wallet unlock` before REPL
- **Logs**: Stored in `<workspace>/.solcoder/logs/`; sessions in `.solcoder/sessions/`
- **Secrets**: Wallet exports must redact secrets unless user explicitly requests output

### Tool Development
Tools are registered through the toolkit system and invoked by the agent loop:
- Tools are stateless handlers exposed via registry
- Use `/toolkits list` and `/toolkits <toolkit> tools` to inspect available tools
- Direct user invocation of individual tools is intentionally disabled
- All tool calls are logged to transcript with metadata for auditability
