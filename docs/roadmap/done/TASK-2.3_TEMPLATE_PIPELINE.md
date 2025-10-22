# Task 2.3 — `/new` Template Pipeline (Done)

- Milestone: [MILESTONE-3_SOLANA_DEPLOY_LOOP](../milestones/MILESTONE-3_SOLANA_DEPLOY_LOOP.md)

## Objective
Connect templates to user prompts so `/new "<prompt>"` selects an Anchor blueprint, renders it, and registers the workspace for subsequent build/deploy commands.

Status: Completed

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
- Store all blueprint bundles under `src/solcoder/anchor/blueprints/<key>/`, including:
  - `wizard.json` (questions/validation)
  - `template/` (scaffoldable file content copied on render)
- Maintain a blueprint registry (`src/solcoder/anchor/blueprints/registry.json`) with:
  - `key`, `name`, `description`, `template_path`, `tags`, and `required_tools` fields.
  - Used by `/new` to list available options and by the LLM selection prompt.
- Keep `RenderOptions` compatible and map registry entries to renderer inputs.

### Wizard Mode (Interactive Config)
- If the user invokes `/new <key>` directly (e.g., `/new token`), start a per‑blueprint wizard that asks the minimum set of config questions and then renders.
- All wizard questions and defaults are stored in src under `src/solcoder/anchor/blueprints/<key>/wizard.json` so the CLI does not hardcode content.
- The wizard engine:
  - Loads the question list + validation from the blueprint bundle.
  - Prompts in the CLI with sane defaults; supports `--no-wizard` to skip and use flags/defaults.
  - Persists answers into the rendered project config (e.g., Anchor `.toml`, `scripts/`, or a generated README section) and into the session notes for traceability.

### End-of-Flow Handoff to Agent
- After a blueprint is selected and the wizard collects answers, the CLI compiles a structured payload containing:
  - `blueprint_key` (one of: counter, token, nft, registry, escrow)
  - `answers` (key/value map from the wizard, validated against the blueprint schema)
  - `target_dir` (the destination directory for generated files)
- Default `target_dir` is the workspace root; the user can override via `--dir <path>` or a wizard prompt.
- The CLI then asks the agent to create the blueprint files according to this payload and waits for completion.
- Upon success, the CLI registers the created path as the active project and prints a summary plus next steps (e.g., `/deploy`, `/program inspect`).

### Acceptance Criteria
- `/new "create a counter app"` generates counter template and registers workspace.
- CLI outputs follow-up commands (`/deploy`, `/code`) and handles existing directories gracefully.
- Tests cover mapping, overrides, and repeated execution scenarios.

