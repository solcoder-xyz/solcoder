# Task 2.2 — Wallet Balance, Airdrop & Spend Policy

- Milestone: [MILESTONE-3_SOLANA_DEPLOY_LOOP](../milestones/MILESTONE-3_SOLANA_DEPLOY_LOOP.md)

## Objective
Extend wallet services to manage balances, request devnet airdrops, and enforce session spend caps through CLI commands and automated triggers.

## Deliverables
- Balance polling utility hitting Solana RPC with graceful degradation.
- `/wallet airdrop`, `/wallet status`, and `/wallet policy` subcommands exposing current limits.
- `/wallet send <address> <amount>` subcommand with confirmation flow and QR rendering for destination review.
- Spend meter tracking lamports spent per session and blocking deploys beyond cap.
- Auto-airdrop mechanism that runs when balance falls below configured threshold.
- Inline wallet address display that outputs both base58 text and an ASCII QR code, reusable by CLI commands and agent tools.
- Agent-accessible WalletSend tool mirroring CLI validations (caps, confirmations, QR/text echo).
- Unit tests and integration tests mocking RPC responses and spend cap violations.

## Key Steps
1. Implement RPC client (using `solana-py` or CLI wrapper) for balance checks and airdrops.
2. Extend session manager to track spend totals and timestamp airdrops.
3. Add transaction submission pipeline (CLI + agent tool) that validates destination, amount, spend cap, and requires explicit confirmation plus wallet passphrase re-entry before signing.
4. Render wallet addresses/targets as both text and QR (e.g., using `qrcode` or svg-to-terminal) in shared utility for reuse.
5. Hook spend checks into deploy/build commands and `/wallet send`, returning descriptive errors on cap breach.
6. Add logging and redaction for transaction signatures.
7. Write tests covering successful airdrop, RPC failure retry, overspend blocking, transaction send success/failure, and QR rendering guards.

## Dependencies
- Task 1.7 wallet core and Task 1.3 session services.

## Acceptance Criteria
- `/wallet status` shows live balance and spend meter updates after deploys.
- Auto-airdrop triggers below threshold and respects cooldown to avoid rate limits.
- `/wallet send` and the WalletSend agent tool can dispatch devnet/testnet transfers with confirmation prompts, passphrase re-entry before signing, adherence to spend caps, and destination displayed as text + QR before approval.
- Address/QR display helper used consistently by CLI status, `/wallet address`, and agent responses.
- Tests pass reliably with mocked RPC endpoints; manual test recorded in milestone notes.

## Owners
- Wallet/Security engineer primary, Solana engineer reviews RPC interactions.
