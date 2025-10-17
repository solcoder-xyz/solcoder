# Milestone 6 — Hardening & Demo Polish

## Timeframe
Day 3 of the 72-hour hackathon (48–72h)

## Objective
Stabilize the deploy loop, raise quality bars, and prepare presentation assets so the SolCoder demo feels production-ready and resilient under judge scrutiny.

## Key Deliverables
- UX refinements: human-readable error summaries with “Try:” hints, collapsible build/deploy logs, copyable commands, and `/logs` browser.
- `/review` and `/plan` outputs tuned for clarity, with fallback messaging when LLM service is unavailable.
- Comprehensive test coverage: unit tests for spend policy, RPC failures, and CLI handlers; e2e script walking onboarding → `/new` → `/deploy`.
- Packaging path via `pipx` (or equivalent) validated on clean macOS/Ubuntu hosts, with instructions captured in README.
- NFT-mint template finalized with README/client stub; counter template validated end-to-end.
- Demo collateral: scripted flow, backup project with prebuilt artifacts, failure playbook, and screenshots/terminal captures.

## Success Criteria
- `poetry run pytest` (including `tests/e2e`) passes with ≥80% coverage on `src/solcoder/core` and `src/solcoder/solana`.
- Running `pipx install solcoder` followed by `solcoder` reproduces the golden-path demo.
- `/logs` displays the latest build/deploy/wallet events with redacted secrets.
- Demo script rehearsed: team can complete onboarding, deploy, and review within seven minutes.

## Dependencies
- Milestones 1–5 completed (foundations, conversational core, deploy loop, coding workflow, knowledge/prompts).
- Needs regression bugs triaged in `docs/roadmap/todo/` with owners assigned.

## Owners & Contributors
- CLI engineer: UX polish, logging improvements, offline fallbacks.
- QA/DevOps: automated test harnesses, coverage reporting, packaging validation.
- Solana engineer: template hardening, RPC retry logic, spend policy regression tests.
- Tech Lead: demo narrative, collateral, failure playbook.

## Risks & Mitigations
- **Risk:** Coverage goals slip due to flaky devnet tests. **Mitigation:** Record fixtures, mock RPC responses where feasible, and separate devnet smoke runs.
- **Risk:** Packaging surprises late. **Mitigation:** Test `pipx` install nightly; document manual fallback script.
- **Risk:** Scope creep toward web search or external API integration. **Mitigation:** Keep MVP toolset local/Solana-only; document web search as a post-hackathon stretch goal.

## Hand-off
Milestone completion locks the MVP feature set, enabling focus on judge feedback, stretch goals, or post-hackathon roadmap planning.
