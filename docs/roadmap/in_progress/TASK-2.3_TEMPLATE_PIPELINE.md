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
- Store all blueprints under `solaba/blueprints/` (top-level folder), one subfolder per key.
- Maintain a simple blueprint registry (e.g., `solaba/blueprints/registry.json`) with:
  - `key`, `name`, `description`, `path`, `tags`, and `required_tools` fields.
  - Used by `/new` to list available options and by the LLM selection prompt.
- Keep `RenderOptions` compatible and map registry entries to renderer inputs.

### Wizard Mode (Interactive Config)
- If the user invokes `/new <key>` directly (e.g., `/new token`), start a per‑blueprint wizard that asks the minimum set of config questions and then renders.
- All wizard questions and defaults must be stored with the blueprint under `solaba/blueprints/<key>/` (e.g., `wizard.json` or `options.schema.json`) so the CLI does not hardcode content.
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
