# Task 2.4 — Build & Deploy Adapters

- Milestone: [MILESTONE-3_SOLANA_DEPLOY_LOOP](../milestones/MILESTONE-3_SOLANA_DEPLOY_LOOP.md)
- Completed: Oct 18, 2025

## Summary
Implemented an Anchor-focused deploy pipeline that wraps `anchor build`/`anchor deploy`, manages program keypairs, and streams structured logs into the SolCoder CLI. The new `/deploy` command performs verification, auto-funds Bundlr (if needed via existing wallet hooks), patches `declare_id!` and `Anchor.toml`, copies generated IDLs into `.solcoder/idl/`, and surfaces explorer links alongside spend tracking updates.

## Key Deliverables
- `solcoder/solana/deploy.py` with reusable helpers for:
  - Program keypair generation + base58 handling.
  - Anchor config parsing and mapping updates.
  - Subprocess wrappers returning typed `CommandResult`/`AnchorDeployResult` objects.
  - Workspace verification (tooling, wallet, file checks).
- `/deploy` CLI command supporting:
  - `verify` mode for pre-flight checks with actionable diagnostics.
  - Build/deploy orchestration, wallet export via temp keyfile, log buffer integration, explorer URL display.
  - Automatic IDL copy to `.solcoder/idl/<program>.json`.
- Tool registry update so agents can trigger `/deploy` directly.
- Tests covering helpers and CLI flow: `tests/solana/test_deploy.py`, `tests/cli/test_deploy_command.py`.

## Acceptance Evidence
- `poetry run pytest tests/solana/test_deploy.py tests/cli/test_deploy_command.py -vv`
- Manual smoke:
  ```bash
  poetry run solcoder
  /new counter
  /deploy verify
  /deploy
  /logs deploy
  ```
  Output shows build/deploy timing, explorer link, spend delta, and `.solcoder/idl/counter.json` populated.

## Follow-ups
- Enhance `/deploy verify` to surface balance thresholds (post wallet policy tuning).
- Stream build/deploy stdout incrementally into the CLI rather than post-run.
- Capture and persist the IDL hash in session metadata for quick diffing across deployments.
