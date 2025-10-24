# Milestone 3 — Solana Deploy Loop

## Timeframe
Day 1 (evening) – Day 2 (morning)

> **Status:** Completed — Oct 24, 2025

## Objective
Deliver the end-to-end Solana deploy experience so users can scaffold a template and ship it to devnet from inside the conversational CLI.

## Key Deliverables
- `/env install` guided installers for Solana CLI, Anchor, Rust, Node with progress output.
- Wallet policy enforcement: balance polling, auto-airdrop, spend-cap checks, and logging.
- `/new` template pipeline rendering Anchor workspaces and updating session metadata.
- Build/deploy adapters wrapping `anchor build`/`anchor deploy` with structured logs, explorer link parsing, and error surfacing.

## Suggested Task Order
1. Task 2.1 — Guided Environment Installers
2. Task 2.2 — Wallet Balance, Airdrop & Spend Policy
   - Task 2.2a — Program Interaction (Anchor‑First)
3. Task 2.3a — `/init` Anchor Workspace Initializer
4. Task 2.3 — `/new` Template Pipeline
4. Task 2.4 — Build & Deploy Adapters

## Success Criteria
- Running `/env diag` followed by `/env install anchor` resolves missing tooling with clear feedback.
- `/wallet status` reports live balance and spend meter; auto-airdrop triggers under threshold and logs actions.
- `/new "counter demo"` creates a workspace, registers it in session state, and suggests next steps.
- `/deploy` builds the project, deploys to devnet, and prints Program ID + explorer URL within target time on reference hardware.
- `/logs deploy` shows recent build/deploy events with timestamps and redacted secrets.

## Dependencies
- Milestone 2 conversational loop (LLM client, tool registry, status bar).
- Milestone 1 wallet/config/session services and counter template scaffold.

## Owners & Contributors
- Solana/Anchor engineer: installers, build/deploy adapters.
- Wallet/Security engineer: balance/airdrop policy and logging.
- CLI engineer: `/new` pipeline and command wiring.
- QA: smoke tests on macOS/Ubuntu verifying deploy flow.

## Risks & Mitigations
- **Risk:** Installer failures or long download times. **Mitigation:** Provide manual fallback instructions and caching.
- **Risk:** Devnet instability or deployment failures. **Mitigation:** Implement retries, configurable RPC endpoints, and provide backup Program IDs for demo.
- **Risk:** Spend-cap false positives. **Mitigation:** Surface detailed error messages and allow override via `/wallet policy` with confirmation.

## Hand-off
With the deploy loop working, proceed to Milestone 4 to enable the coding/edit/test workflow on top of the same session.
