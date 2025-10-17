# Task 2.6 — Live Status Bar & Logs

- Milestone: [MILESTONE-2_CONVERSATIONAL_CORE](../milestones/MILESTONE-2_CONVERSATIONAL_CORE.md)

## Objective
Enhance the CLI UX with a Rich-powered status bar showing wallet, network, spend, and project state plus a `/logs` viewer for recent operations.

## Deliverables
- Status bar component updating reactively during long-running commands.
- Centralized log buffer capturing build/deploy/wallet events with severity tags.
- `/logs [build|deploy|wallet]` command dumping recent entries with timestamps.
- Manual UX review verifying responsiveness and readability during installs/deploys.

## Key Steps
1. Design status bar layout (wallet addr, balance, spend meter, network, project).
2. Integrate asynchronous updates triggered by session changes and command hooks.
3. Implement in-memory log store with rotation policy and secret redaction.
4. Wire `/logs` command to formatted output and optional filtering.
5. Add unit tests for log storage plus snapshot tests for status bar rendering (if feasible).

## Dependencies
- Task 1.2 CLI shell/layout.
- Tasks 2.2 wallet policy and 2.4 deploy adapters for data sources.

## Acceptance Criteria
- Status bar updates in near real-time during installs/deploys without flicker.
- `/logs deploy` returns latest events with sanitized values; redaction verified.
- Tests cover log storage and CLI output; manual UX review signed off in milestone notes.

## Owners
- CLI engineer primary; Wallet/Solana engineers provide data hooks.
