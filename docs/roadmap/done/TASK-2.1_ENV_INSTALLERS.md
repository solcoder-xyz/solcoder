# Task 2.1 — Guided Environment Installers

- Milestone: [MILESTONE-3_SOLANA_DEPLOY_LOOP](../milestones/MILESTONE-3_SOLANA_DEPLOY_LOOP.md)

## Objective
Provide automated installers triggered by `/env install` that fetch and configure Solana CLI, Anchor, Rust, and Node while streaming progress inside the REPL, and proactively prompt users during bootstrap when critical Solana tooling is missing.

## Supported Tooling Scope
- **Solana CLI** (`solana`) — install via official script pinned to latest stable release.
- **Anchor CLI** (`anchor`) — install through `cargo install` with locked git tag.
- **Rust toolchain** (`rustup`, `cargo`, `rustc`) — ensure minimal nightly/channel required by Anchor is present.
- **Node.js + npm** — provide an LTS distribution (e.g., Node 20.x) packaged with npm.
- **Yarn** — optional but recommended for template workflows; install via corepack or standalone.
- **Python 3 + pip** — validate system Python meets scripting requirements for tooling helpers.
- **Diagnostics coverage** — enumerate every tool above, listing installed versions and flagging missing items. Anchor is considered blocking; keep prompting until the user installs or explicitly skips.

## Deliverables
- Installer module handling per-tool workflows with consent prompts and retry logic.
- `/env install <tool>` and `/env install all` commands integrated with Rich progress UI.
- Post-install verification reusing diagnostics to confirm tools on PATH.
- Documentation updates detailing installer behavior and manual fallback steps.
- Bootstrap onboarding hook: on first launch, detect missing Solana environment tooling and prompt the user to run the relevant installer(s) before dropping into the REPL.

## Key Steps
1. Extend bootstrap diagnostics to detect missing Solana environment tooling (Solana CLI, Anchor, Rust toolchain, Node/npm, Yarn, Python/pip) and surface an actionable installer prompt before entering the REPL.
2. Define installer interface (download, install, verify) with dry-run capability.
3. Implement tool-specific installers (e.g., Solana official script, `rustup`, npm for Anchor).
4. Add progress spinners/log capture to CLI output; handle cancellation gracefully.
5. Re-run diagnostics post-install and surface success/failure summary.
6. Update `README.md`/`AGENTS.md` with installer usage, bootstrap onboarding flow, and failure recovery.

## Dependencies
- Task 1.8 diagnostics to reuse detection logic.
- Task 1.2 CLI shell for command routing.

## Acceptance Criteria
- On bootstrap, if any supported tool (Solana CLI, Anchor, Rust toolchain, Node/npm, Yarn, Python/pip) is missing, SolCoder surfaces inline prompts offering to run `/env install <tool>` before entering the REPL. Anchor remains blocking unless the user explicitly skips.
- `/env install anchor` installs Anchor CLI on tested macOS/Ubuntu hosts and prints success confirmation.
- `/env install all` sequentially installs the supported tooling (Solana CLI, Anchor, Rust toolchain, Node/npm, Yarn) with progress feedback and post-install verification.
- Installer failures produce actionable messages, offer retry/skip options, and do not leave CLI state inconsistent.
- Documentation reflects prerequisites, bootstrap onboarding behavior, and safe re-run instructions.

## Owners
- Solana/Anchor engineer primary; QA validates installs on clean VMs.
