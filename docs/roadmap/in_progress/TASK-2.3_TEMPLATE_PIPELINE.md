# Task 2.3 — `/new` Template Pipeline

- Milestone: [MILESTONE-3_SOLANA_DEPLOY_LOOP](../milestones/MILESTONE-3_SOLANA_DEPLOY_LOOP.md)

## Objective
Connect templates to user prompts so `/new "<prompt>"` selects an Anchor blueprint, renders it, and registers the workspace for subsequent build/deploy commands.

## Deliverables
- Prompt classification logic mapping requests to available templates (counter, NFT mint).
- Template renderer integrated with session state, storing project path and metadata.
- CLI feedback summarizing generated files and next-step hints.
- Tests validating template selection and idempotent re-generation safeguards.

### Required Blueprints (Tier 1)
- Counter (Hello, Anchor)
  - Instructions: init, increment, decrement, reset
  - PDAs: counter by authority
  - Extras: minimal TS test and example client scripts

- Simple Token Mint (SPL)
  - Flow: create mint, create ATAs, mint_to, transfer
  - Options: toggle Token-2022 features (optional)
  - Extras: CLI snippets for `spl-token` where applicable

- NFT Mint (fixed metadata)
  - Flow: create mint, set metadata (Metaplex), mint 1, update_uri
  - PDAs: metadata/edition accounts
  - Extras: JSON metadata example and devnet demo script

- PDA Registry (key-value store)
  - Instructions: upsert, get, delete
  - PDAs: seeds = ["registry", authority, key]
  - Extras: script to read/write entries and quick tests

- Escrow (basic)
  - Flow: init_escrow, deposit, withdraw, cancel
  - PDAs: escrow by initializer (and optional vault ATA)
  - Notes: highlight authority checks and cancel path

### Blueprint Keys and Selection
- Introduce canonical blueprint keys: `counter`, `token`, `nft`, `registry`, `escrow`.
- `/new <key>` must directly select the matching blueprint without heuristics.
- If the user runs `/new <free-form text>` that is not an exact key:
  - Do not run local heuristics.
  - Ask the LLM to choose a blueprint with a minimal system prompt, no transcript/history, and provide the list of available keys and short descriptions.
  - If the LLM cannot decide (or returns invalid), prompt the user interactively to choose.
  - After selection, proceed with normal rendering flow and show the confirmation/summary.

### Layout & Registry
- Store all blueprints under `src/solcoder/anchor/blueprints/`, one subfolder per key.
- Maintain a simple blueprint registry (e.g., `src/solcoder/anchor/blueprints/registry.json`) with:
  - `key`, `name`, `description`, `path`, `tags`, and `required_tools` fields.
  - Used by `/new` to list available options and by the LLM selection prompt.
- Keep `RenderOptions` compatible and map registry entries to renderer inputs.

### Wizard Mode (Interactive Config)
- If the user invokes `/new <key>` directly (e.g., `/new token`), start a per‑blueprint wizard that asks the minimum set of config questions and then renders.
- All wizard questions and defaults must be stored with the blueprint under `src/solcoder/anchor/blueprints/<key>/` (e.g., `wizard.json` or `options.schema.json`) so the CLI does not hardcode content.
- The wizard engine:
  - Loads the question list + validation from the blueprint bundle.
  - Prompts in the CLI with sane defaults; supports `--no-wizard` to skip and use flags/defaults.
  - Persists answers into the rendered project config (e.g., Anchor `.toml`, `scripts/`, or a generated README section) and into the session notes for traceability.

- Token wizard (example prompts):
  - Token name (e.g., "SolCoder Token")
  - Symbol (e.g., "SCT")
  - Decimals (e.g., 9)
  - Initial supply (amount + recipient; default to creator ATA)
  - Authorities: mint authority, freeze authority (default to creator; allow none for freeze)
  - Token-2022 features (optional toggles): transfer fee, interest-bearing, metadata pointer

- NFT wizard (example prompts):
  - Name, symbol
  - URI/metadata JSON (provide devnet sample)
  - Seller fee basis points
  - Creators (addresses + shares)
  - Optional collection address

- Registry wizard:
  - Key type (string | bytes | u64)
  - Value type (string | bytes | u64)
  - Access policy (owner‑only CRUD vs public read)

- Escrow wizard:
  - Token mint
  - Counterparty address (optional at init)
  - Expiry/cancel rules

- Counter wizard:
  - Optional initial value; otherwise accept defaults

### End-of-Flow Handoff to Agent
- After a blueprint is selected and the wizard collects answers, the CLI compiles a structured payload containing:
  - `blueprint_key` (one of: counter, token, nft, registry, escrow)
  - `answers` (key/value map from the wizard, validated against the blueprint schema)
  - `target_dir` (the destination directory for generated files)
- Default `target_dir` is the workspace root; the user can override via `--dir <path>` or a wizard prompt.
- The CLI then asks the agent to create the blueprint files according to this payload (concise system prompt without full history), and waits for completion.
- Upon success, the CLI registers the created path as the active project and prints a summary plus next steps (e.g., `/deploy`, `/program inspect`).

## Key Steps
1. Design mapping heuristics and optional `--template` override flags.
2. Implement rendering pipeline with conflict detection (prompt user before overwriting).
3. Update session to persist active project directory and Anchor workspace config.
4. Write tests in `tests/cli/test_new_command.py` covering selection, overrides, and error paths.
5. Document usage examples in README and milestone notes.

## Dependencies
- Task 1.9 counter template and upcoming NFT template assets.
- Task 1.3 session services.

## Acceptance Criteria
- `/new "create a counter app"` generates counter template and registers workspace.
- CLI outputs follow-up commands (`/deploy`, `/code`) and handles existing directories gracefully.
- Tests cover mapping, overrides, and repeated execution scenarios.

## Owners
- CLI engineer primary; Solana engineer validates template wiring.

## Anchor Workspace Integration
- Workspace detection:
  - Detect an Anchor workspace by searching for `Anchor.toml` from the target directory upward.
  - If found, treat as existing Anchor project; if not found, treat as non‑Anchor directory.

- Default placement:
  - When an Anchor project is detected, `/new <key>` must add a new program under `programs/<program_name>/` and update `Anchor.toml` and Cargo workspace members.
  - When no Anchor project is detected, prompt to initialize one here first. If the user agrees, initialize the workspace, then add the program. If declined, allow a `--standalone` scaffold that includes a minimal workspace structure.

- Initialization flow (non‑Anchor):
  - Validate prerequisites (e.g., `anchor` availability). If missing, suggest `/env install anchor`.
  - Offer two paths:
    - Preferred: run `anchor init <workspace_name>` and then apply the blueprint.
    - Offline: scaffold minimal workspace files (Anchor.toml, Cargo.toml, programs/) without executing `anchor init`; document that `anchor build` is required later.

- Flags and overrides:
  - `--dir <path>` sets the destination (defaults to current root).
  - `--workspace <path>` explicitly targets an Anchor workspace root for program insertion.
  - `--standalone` forces a full workspace scaffold even if a workspace is detected.
  - `--no-wizard` skips Q&A and uses defaults/flags only.

- Session integration:
  - After scaffold, set `active_project` to the workspace root; status bar shows the path.
  - Print next steps (`/deploy`, `/program inspect`, `/program wizard`).

- Agent handoff:
  - The payload sent to the agent must include `blueprint_key`, validated `answers`, `target_dir`, and `workspace_root` (if applicable) so files are created under `programs/` when appropriate.

- Acceptance:
  - In an existing Anchor project, `/new token` places a new program under `programs/` and patches `Anchor.toml` and Cargo workspace.
  - In a non‑Anchor directory, `/new counter` prompts for workspace initialization and proceeds accordingly.
