# Task 2.3b — Unified Metadata Pipeline (/metadata)

- Milestone: [MILESTONE-3_SOLANA_DEPLOY_LOOP](../milestones/MILESTONE-3_SOLANA_DEPLOY_LOOP.md)

## Objective
Provide a single, generic metadata workflow for both fungible tokens (SPL Token) and NFTs, so users can create and attach name/symbol/URI (and NFT images/attributes) without installing extra CLIs or configuring complex storage. The flow should “just work” on devnet/testnet with sensible defaults.

## User Story
As a user, when I mint a token or NFT, I want to attach human‑readable metadata (name, symbol, image/description/attributes) and have it hosted on decentralized storage automatically, without extra setup. I expect the CLI to guide me and complete the process with confirmations.

## Command Surface
- `/metadata wizard --mint <MINT> [--type token|nft]`
  - Guided flow: collects name, symbol, description, image(s) path, attributes (NFT), royalties/creators, and storage preference.
  - Uploads assets + metadata JSON to decentralized storage, then writes on‑chain metadata via Metaplex.

- `/metadata upload --file <path>|--dir <dir> [--storage <bundlr|ipfs>]`
  - Returns content URIs for assets and (optionally) a generated metadata.json.

- `/metadata set --mint <MINT> --name <N> --symbol <S> --uri <URI> [--royalty-bps <n>] [--creators <PK:BPS,...>] [--collection <PK>]`
  - Creates/updates the Metaplex Token Metadata account for the mint.

Notes:
- Single generic namespace `/metadata` replaces specialized `/token metadata …` or `/nft …` commands.
- The “type” is inferred when possible (decimals==0 → NFT‑like), but can be forced with `--type`.

## Storage Provider (default + fallback)
- Default: Bundlr/Irys on Solana devnet/testnet, paid via the user’s SolCoder wallet (auto‑airdrop assists). Rationale: decentralized, no separate API key, predictable for tests.
- Fallback (optional, if configured): IPFS via nft.storage/web3.storage using API key stored in `.solcoder/config.toml`.
- Provider is abstracted behind a small uploader lib; selection is automatic with `bundlr` preferred when the wallet has SOL and network is dev/test.

## Implementation Plan
1) CLI commands (+ help): `/metadata wizard|upload|set`
2) Wizard engine
   - Reuse prompt utilities; per‑type questions (token vs nft) with shared core: name, symbol, image/dir, description, attributes, royalty_bps.
   - Save answers to `blueprint.answers.json` when invoked from `/new` flows.
3) Storage adapter
   - Bundlr (Irys) devnet uploader using wallet key (reuse WalletManager export).
   - Optional IPFS uploader via configured API key.
4) Metaplex integration
   - Preferred: built‑in Node runner (`scripts/metadata.ts`) using Umi + mpl-token-metadata to create/update metadata for a given mint.
   - Avoid hard dependency on external CLIs like `metaboss`; provide installer + diag as optional path.
5) Agent tools
   - `solcoder.metadata.upload` and `solcoder.metadata.set` mirroring the CLI.
   - Allow agent to stage `/metadata set …` with a confirmation summary.
6) UX hooks
   - After `/new token` or `/new nft`, prompt: “Create metadata now?” → launch `/metadata wizard` prefilled with answers.
7) Logs + status
   - Show spinner during upload + set; write concise success summaries with minted URIs and transaction signatures.

## Diagnostics & Installers
- Extend `/env diag` (done: SPL Token CLI) with optional entries:
  - “Metaplex Umi runtime” (implicit via Node; no CLI).
  - “metaboss” (optional): `cargo install metaboss`.
  - “sugar” (optional, for Candy Machine): `cargo install sugar`.
- Extend `/env install` with keys: `metaboss`, `sugar` (optional; only if we expose wrappers).

## Wizard UX
- Shared core (token + nft):
  - name, symbol, description
  - image file (single) or directory (batch NFTs later)
  - storage provider (auto: bundlr; fallback if configured)
- NFT extras:
  - royalty_bps, creators (pk:share), collection (optional), attributes input

## Acceptance Criteria
- `/metadata wizard` completes end‑to‑end on devnet: uploads image + JSON to Bundlr and writes on‑chain metadata using the SolCoder wallet.
- `/metadata set` updates an existing mint’s metadata on devnet (idempotent run produces no error).
- `/new token` and `/new nft` offer to run the metadata wizard; skipping does not block the flow.
- Tests cover: storage selection, happy paths with mocked upload + on‑chain set, and CLI summaries.

## Out of Scope (for 2.3b)
- Candy Machine batch drops (will be a follow‑up subtask).
- Mainnet uploads without configured payment.

## Notes
- Devnet costs for Bundlr are covered by faucet airdrops; we should surface retry/backoff and insufficient balance hints.
- If the wallet is locked, prompt to unlock before running the wizard or set command.

