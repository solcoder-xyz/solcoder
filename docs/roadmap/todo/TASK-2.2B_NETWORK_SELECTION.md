# Task 2.2B — Network Selection & Custom RPC Profiles

- Milestone: [MILESTONE-3_SOLANA_DEPLOY_LOOP](../milestones/MILESTONE-3_SOLANA_DEPLOY_LOOP.md)

## Objective
Allow users to choose or define Solana clusters (mainnet-beta, devnet, testnet, custom RPC) during bootstrap and via the `/network` command, with safeguards for airdrops (dev/test only) and persistent session storage.

## Deliverables
- Bootstrap prompt that detects missing network preference and offers mainnet-beta/devnet/testnet plus existing custom profiles.
- `/network select <name>` command with validation and instant reconnection.
- `/network add <name> <rpc_url>` and `/network remove <name>` commands with basic URL checks and duplication guards.
- Config storage (e.g., `.solcoder/config.toml`) persisting selected network and custom entries.
- Agent tool (`NetworkSelect`) mirroring CLI permissions and prompting before switching to mainnet.
- Tests covering selection, add/remove flows, and persistence on restart.

## Key Steps
1. Extend configuration schema to store active network and custom RPC entries.
2. Implement bootstrap wizard that surfaces current selection, default choices, and prevents airdrop shortcuts on unsupported clusters.
3. Build `/network` subcommands (select/add/remove/list) with user feedback and confirmation when switching away from dev/test.
4. Wire Solana RPC client reinitialization on network change and update spend policy limits accordingly.
5. Expose agent-level tool that requires explicit confirmation before moving to mainnet-beta and rejects airdrop requests there.
6. Add tests ensuring custom URLs persist, validation errors surface, and agent + CLI share the same registry.

## Dependencies
- Task 2.2 wallet policy (spend tracking/airdrop) for enforcement across clusters.
- Task 1.1 configuration bootstrap.

## Acceptance Criteria
- On first run, SolCoder offers network selection; choosing dev/test automatically enables airdrop flows, while mainnet disables them.
- `/network select devnet` refreshes the RPC client and `/wallet status` reflects the new cluster immediately.
- `/network add custom https://rpc.example.com` persists after restart and appears in selection menus.
- `/network remove custom` deletes the profile unless it is currently active (prompt required in that case).
- Agent prevents airdrop attempts on mainnet and asks for confirmation before switching from dev/test to mainnet-beta.
- All `/network` commands and agent tool updates are logged, and tests cover happy/error paths.

## Owners
- Networking engineer primary; wallet/CLI engineer reviews integration points.
