# Task 2.2 — Wallet Balance, Airdrop & Spend Policy

- Milestone: [MILESTONE-3_SOLANA_DEPLOY_LOOP](../milestones/MILESTONE-3_SOLANA_DEPLOY_LOOP.md)

## Objective
Extend wallet services to manage balances, request devnet airdrops, and enforce session spend caps through CLI commands and automated triggers.

## Deliverables
- Balance polling utility hitting Solana RPC with graceful degradation.
- `/wallet airdrop`, `/wallet status`, and `/wallet policy` subcommands exposing current limits.
- Spend meter tracking lamports spent per session and blocking deploys beyond cap.
- Auto-airdrop mechanism that runs when balance falls below configured threshold.
- Unit tests and integration tests mocking RPC responses and spend cap violations.

## Key Steps
1. Implement RPC client (using `solana-py` or CLI wrapper) for balance checks and airdrops.
2. Extend session manager to track spend totals and timestamp airdrops.
3. Hook spend checks into deploy/build commands, returning descriptive errors on cap breach.
4. Add logging and redaction for transaction signatures.
5. Write tests covering successful airdrop, RPC failure retry, and overspend blocking.

## Dependencies
- Task 1.7 wallet core and Task 1.3 session services.

## Acceptance Criteria
- `/wallet status` shows live balance and spend meter updates after deploys.
- Auto-airdrop triggers below threshold and respects cooldown to avoid rate limits.
- Tests pass reliably with mocked RPC endpoints; manual test recorded in milestone notes.

## Owners
- Wallet/Security engineer primary, Solana engineer reviews RPC interactions.
