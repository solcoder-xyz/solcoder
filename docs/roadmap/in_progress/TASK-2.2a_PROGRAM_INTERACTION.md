# Task 2.2a — Program Interaction (Anchor‑First)

- Milestone: [MILESTONE-3_SOLANA_DEPLOY_LOOP](../milestones/MILESTONE-3_SOLANA_DEPLOY_LOOP.md)

## Objective
Add a CLI command and agent tool to interact with on-chain programs by program ID: inspect instructions, prompt for args/accounts, and build + send transactions with explicit user confirmation.

## Deliverables
- New CLI command `/program` (aliases: `/dapp`, `/interact`).
  - `inspect <program_id>` — fetch IDL (Anchor) or use SPL catalog; list instructions with args and required accounts (signer/writable flags).
  - `call <program_id> [--method <name>] [--args-json <json>] [--accounts-json <json>] [--confirm]` — fast-path call; prompts for any missing values; shows summary; requires confirmation.
  - `wizard <program_id>` — interactive flow to select instruction, fill args/accounts, preview, and submit.
  - `idl import <path|url>` — attach user-provided IDL to the session for future calls.
- Agent toolkit `solcoder.program` with tools:
  - `inspect_program { program_id }` — returns instruction list + arg/account schema (no side effects).
  - `prepare_program_call { program_id, method, args?, accounts? }` — returns `dispatch_command` to `/program call …` for CLI confirmation (passphrase + explicit "send").
- Built-in SPL fallback catalog (Token, Token‑2022, Associated Token, Memo, Metaplex Metadata) with minimal instruction and account schemas.
- IDL persistence per session and a "raw mode" that allows manual Borsh schema input if no IDL/catalog match.

## Resolution Strategy
1. Try Anchor first: use `anchorpy` dynamic client (e.g., `Program.at(program_id, provider)`) to fetch on-chain IDL and enumerate instructions.
2. Known SPL fallback: if no IDL, check against built‑in catalog and expose common instructions.
3. Last resort: prompt to paste/import an IDL JSON or operate in raw mode with user-provided Borsh schemas.

## Key Steps
1. Add CLI command module at `src/solcoder/cli/commands/program.py` with subcommands and rich tables for instructions/args/accounts.
2. Add agent toolkit at `src/solcoder/core/tools/program.py` with `inspect_program` and `prepare_program_call` returning `dispatch_command` and `suppress_preview`.
3. Implement SPL catalog under `src/solcoder/solana/catalog/` with compact JSON schemas; loader that matches well-known program IDs.
4. Detect optional `anchorpy`; if missing, prompt to install or continue with fallback modes. Respect configured `rpc_url` and active wallet.
5. Transaction flow: build instruction, assemble accounts (support IDL seeds where available), show summary (method, args, accounts, estimated fee), require explicit confirmation, then sign + send.
6. Update status bar after submission; log signature with redaction policy.
7. Tests: mock RPC/IDL fetch for `inspect`, catalog fallback, and a `wizard` happy path that submits a transaction on devnet.

## Dependencies
- Task 2.2 Wallet policy and airdrop (RPC wiring, spend meter, confirmations).
- Milestone 2 conversational loop (agent tool dispatch) and status bar updates.

## Acceptance Criteria
- `inspect` lists instructions from an on-chain IDL on devnet.
- SPL fallback recognizes Token program and displays common instructions.
- `wizard` builds and submits a transaction after user confirmation; prints signature and updates balance.
- Agent can pre-stage a call that opens the CLI confirmation step without executing until the user confirms.

## Owners
- Solana engineer (Anchor/IDL client, SPL catalog).
- CLI engineer (command UX, summary/confirmation).
- QA (mocked RPC/IDL tests, devnet smoke test).

