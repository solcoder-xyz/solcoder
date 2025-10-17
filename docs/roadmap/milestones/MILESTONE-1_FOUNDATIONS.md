# Milestone 1 — Foundations & Onboarding

## Timeframe
Day 1 of the 72-hour hackathon (0–24h)

## Objective
Establish the project scaffolding, interactive CLI shell, and wallet/config primitives so contributors can iterate inside a functioning SolCoder session.

## Key Deliverables
- Repository tooling in place (`poetry`, `ruff`, `black`, pre-commit) with clean installs on macOS/Linux.
- Prompt Toolkit REPL with slash-command parser and `/help` routing to verify the interactive loop.
- Config + session services writing defaults to `~/.solcoder/config.toml`, supporting project-level overrides, generating unique session IDs, and tracking active project metadata.
- Wallet core that creates/locks/unlocks encrypted keypairs and exposes `/wallet` status.
- Environment diagnostics covering `solana`, `anchor`, `rust`, `cargo`, `node`, `npm`.
- Counter Anchor template scaffolded and building locally as the reference project.
- Session utilities for exporting transcripts and rotating stored history under `~/.solcoder/sessions/`.

## Suggested Task Order
1. Task 1.1 — Repo Tooling & Pre-Commit
2. Task 1.2 — CLI Shell & Slash Parser
3. Task 1.3 — Config & Session Services
4. Task 1.4 — Session Lifecycle & History
5. Task 1.5 — Global & Project Config Overrides
6. Task 1.6 — Session Transcript Export
7. Task 1.7 — Wallet Core & Encryption
8. Task 1.8 — Environment Diagnostics
9. Task 1.9 — Counter Template Scaffold

## Success Criteria
- `poetry install` followed by `poetry run solcoder` drops users into the command panel without errors and prints the generated session ID.
- Project-local `.solcoder/config.toml` overrides merge cleanly with the global config; conflicts surface actionable errors.
- First-run wizard captures LLM base URL/model/API key, stores credentials securely, and exposes rotation via `/config` commands without re-prompting each launch.
- Creating and unlocking a wallet stores encrypted keys and logs sanitized telemetry.
- Running `/env diag` surfaces missing toolchains with actionable guidance; counter template builds manually.
- Session export commands (`--dump-session`) produce redacted transcripts for debugging.
- Documentation updates: README quickstart, AGENTS contributor guide, and milestone tracker committed (including session lifecycle, config layering, and export expectations).

## Dependencies
None; this milestone bootstraps the codebase and infrastructure required for later work.

## Owners & Contributors
- Tech Lead / CLI engineer: REPL, command router, config/session layer.
- Wallet/Security engineer: key management, encryption, basic `/wallet` handler.
- QA/DevOps: environment sanity checks, tooling verification.

## Risks & Mitigations
- **Risk:** Prompt Toolkit UX stalls on Windows. **Mitigation:** Limit scope to macOS/Ubuntu; document WSL fallback.
- **Risk:** Encryption workflow blocks onboarding. **Mitigation:** Provide clear passphrase prompts and debug logging.

## Hand-off
With the CLI shell, wallet, and diagnostics live, Milestone 2 can focus on build/deploy automation and wallet policy enforcement.
