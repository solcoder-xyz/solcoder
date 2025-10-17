# Task 1.7 — Wallet Core & Encryption

- Milestone: [MILESTONE-1_FOUNDATIONS](../milestones/MILESTONE-1_FOUNDATIONS.md)

## Objective
Create secure wallet management that generates, encrypts, unlocks, and exports Solana keypairs for use by the agent.

_In progress — 2025-10-16 (CLI agent)_ 

## Deliverables
- `src/solcoder/solana/wallet.py` implementing create, restore, unlock, and export flows.
- AES-GCM encryption helper using passphrase-derived keys (via `cryptography`).
- CLI prompts guiding users through wallet onboarding within `poetry run solcoder`.
- `/wallet status` command showing masked address, balance placeholder, and lock state.
- Unit tests covering key generation, encryption/decryption, and failure modes.

## Key Steps
1. Decide storage format (JSON with public key, encrypted secret, metadata) under `~/.solcoder/keys/`.
2. Implement create/restore flows with passphrase confirmation and secure file permissions.
3. Add unlock flow caching decrypted key in memory with timeout hook for Milestone 2 policy work.
4. Wire wallet status into session manager and CLI router.
5. Write tests using temp directories to validate secure file creation and unlock errors.

_Notes_
- 2025-10-16: Bootstrap wizard now enforces create/restore + unlock before the REPL, stores encrypted recovery phrases, and fetches live balances via RPC. `/wallet phrase` and `/wallet export [path]` surface recovery data securely.

## Dependencies
- Task 1.1 and Task 1.3 for configuration paths and session integration.

## Acceptance Criteria
- Wallet creation stores encrypted secret seeds, and unlocking returns a usable keypair object.
- `/wallet status` prints masked address and indicates lock/unlock state without leaking secrets.
- Tests pass on CI; manual smoke on macOS confirms file permissions (0600).

## Owners
- Wallet/Security engineer primary; Tech Lead reviews cryptography approach.
