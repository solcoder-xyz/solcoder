# Task 2.3b — Unified Metadata Pipeline (/metadata)

- Milestone: [MILESTONE-3_SOLANA_DEPLOY_LOOP](../milestones/MILESTONE-3_SOLANA_DEPLOY_LOOP.md)
- Completed: Oct 18, 2025

## Summary
The `/metadata` command family now delivers a complete token/NFT metadata flow with Bundlr as the default storage backend and IPFS as a configurable fallback. Users can upload assets, capture metadata through the wizard, persist staged JSON locally, and optionally dispatch an on-chain write via a bundled Umi runner. The Bundlr uploader auto-funds using the SolCoder wallet and enforces install checks for Node tooling, while tests exercise both storage paths and runner invocation.

## Key Deliverables
- CLI surface (`/metadata upload|wizard|set`) with guided prompts and automatic hand-off between subcommands.
- Bundlr (Irys) uploader that:
  - Uses the user’s SolCoder wallet key (temporary export) to authenticate.
  - Auto-funds the Bundlr balance with a 10% buffer based on file size.
  - Tags uploads with accurate MIME types and returns permanent `https://arweave.net/...` URIs.
- IPFS helpers targeting nft.storage and web3.storage for environments with API keys.
- Staged metadata writer storing JSON under `.solcoder/metadata/<mint>.json`, plus Umi/Metaplex runner scaffolding for `/metadata set --run`.
- Unit tests covering IPFS uploads, Bundlr uploads, and CLI integration.

## Acceptance Evidence
- `poetry run pytest tests/cli/test_metadata.py` (all 4 tests passing).
- Manual CLI run:
  ```bash
  poetry run solcoder
  /metadata upload --file ./metadata.json --storage bundlr
  /metadata set --mint <MINT> --name Demo --symbol DEMO --uri <returned_uri> --run
  ```
  Output shows Bundlr funding, upload URL, and successful Umi runner execution (or actionable warnings if deps missing).

## Follow-ups
- Expand `/metadata wizard` to capture image directories for batch NFT drops.
- Integrate metadata prompts directly into blueprint scaffolds (auto-trigger after `/new token|nft`).
- Harden on-chain runner with retries and richer error surfacing once deploy adapters land.
