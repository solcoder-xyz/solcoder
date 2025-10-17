# Task 2.1 — Guided Environment Installers

- Milestone: [MILESTONE-3_SOLANA_DEPLOY_LOOP](../milestones/MILESTONE-3_SOLANA_DEPLOY_LOOP.md)

## Objective
Provide automated installers triggered by `/env install` that fetch and configure Solana CLI, Anchor, Rust, and Node while streaming progress inside the REPL.

## Deliverables
- Installer module handling per-tool workflows with consent prompts and retry logic.
- `/env install <tool>` and `/env install all` commands integrated with Rich progress UI.
- Post-install verification reusing diagnostics to confirm tools on PATH.
- Documentation updates detailing installer behavior and manual fallback steps.

## Key Steps
1. Define installer interface (download, install, verify) with dry-run capability.
2. Implement tool-specific installers (e.g., Solana official script, `rustup`, npm for Anchor).
3. Add progress spinners/log capture to CLI output; handle cancellation gracefully.
4. Re-run diagnostics post-install and surface success/failure summary.
5. Update `README.md`/`AGENTS.md` with installer usage and failure recovery.

## Dependencies
- Task 1.8 diagnostics to reuse detection logic.
- Task 1.2 CLI shell for command routing.

## Acceptance Criteria
- `/env install anchor` installs Anchor CLI on tested macOS/Ubuntu hosts and prints success confirmation.
- Installer failures produce actionable messages and do not leave CLI in inconsistent state.
- Documentation reflects prerequisites and safe re-run instructions.

## Owners
- Solana/Anchor engineer primary; QA validates installs on clean VMs.
