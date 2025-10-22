# Task 2.4 — Build & Deploy Adapters

- Milestone: [MILESTONE-3_SOLANA_DEPLOY_LOOP](../milestones/MILESTONE-3_SOLANA_DEPLOY_LOOP.md)

## Objective
Wrap `anchor build` and `anchor deploy` with structured logging, error handling, and explorer link generation to complete the prompt-to-deploy loop.

## Deliverables
- Adapter functions invoking Anchor CLI commands, capturing stdout/stderr, and returning typed results.
- `/deploy` command orchestrating build, deploy, spend checks, and explorer link output.
- Structured logs stored for `/logs deploy` viewing, including timestamps and sanitized signatures.
- Integration tests using fixtures to simulate successful/failed builds without hitting devnet.
- Re-run `anchor build` on the counter template once the installer task provisions Anchor, capturing logs for milestone notes.

## Key Steps
1. Implement subprocess wrappers with timeout and retry configuration.
2. Parse command output to extract program ID; format devnet explorer URL.
3. Integrate adapters with session spend meter and auto-airdrop warnings.
4. Add log persistence (file or in-memory buffer) for later inspection.
5. Write tests in `tests/solana/test_deploy.py` and `tests/cli/test_deploy_command.py`.
6. Record manual `anchor build`/`anchor deploy` runs after the installers land to close Task 1.9 verification.

### Program ID management (new)
- Auto-generate a program keypair (if missing) at deploy time and patch sources before invoking Anchor:
  - Generate and persist under `.solcoder/keys/programs/<program_name>.json`.
  - Patch `declare_id!` in `programs/<name>/src/lib.rs` and the `[programs.<cluster>]` mapping in `Anchor.toml`.
  - Pass `--program-keypair` to `anchor deploy` so the deploy targets the generated address.
- After successful deploy, copy the built IDL to `.solcoder/idl/<program_name>.json` for later `/program inspect` usage.

### Verify (new)
- Add `/deploy verify` to validate environment and configuration prior to running build/deploy:
  - Tooling present (anchor, rust/cargo, solana) and correct cluster configured.
  - Wallet unlocked and funded per spend policy; network matches `Anchor.toml` provider.
  - Program ID consistency: `declare_id!`, `Anchor.toml` mapping, and (if already deployed) on-chain program address match.
  - Emit actionable guidance to fix each failed check.

## Dependencies
- Tasks 2.2 wallet policy and 2.3 template pipeline.
- Task 1.8 diagnostics for verifying tools pre-run.

## Acceptance Criteria
- Running `/deploy` after `/new` builds and deploys the counter template on devnet within 60 seconds on reference hardware.
- Failures (e.g., anchor error) produce actionable messages and stored logs viewable via `/logs`.
- Tests cover success, failure, timeout, and log creation; manual deploy recorded.
- `/deploy verify` flags missing/invalid Program ID mappings, missing tools, wrong cluster, or locked/empty wallet with clear remediations.
- Deploy flow patches Program ID (when not already set) and copies IDL to `.solcoder/idl/` on success.

## Owners
- Solana/Anchor engineer primary; CLI engineer integrates output handling.
