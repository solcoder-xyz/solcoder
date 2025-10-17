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

## Dependencies
- Tasks 2.2 wallet policy and 2.3 template pipeline.
- Task 1.8 diagnostics for verifying tools pre-run.

## Acceptance Criteria
- Running `/deploy` after `/new` builds and deploys the counter template on devnet within 60 seconds on reference hardware.
- Failures (e.g., anchor error) produce actionable messages and stored logs viewable via `/logs`.
- Tests cover success, failure, timeout, and log creation; manual deploy recorded.

## Owners
- Solana/Anchor engineer primary; CLI engineer integrates output handling.
