# SolCoder

SolCoder is a CLI-first AI coding agent that scaffolds, deploys, and funds Solana dApps directly from natural-language prompts. It blends LLM-assisted planning, automated environment setup, and wallet-aware deployment so builders can demo a working program on devnet in under a minute.

## Key Capabilities
- **Conversational Control**: Drive workflows in natural language while keeping `/commands` available for deterministic actions.
- **Prompt-to-Deployment**: Generate an Anchor workspace, build it, deploy to devnet, and surface the program ID with explorer links.
- **Wallet Autonomy**: Manage a dedicated Solana wallet, track live balances from your configured RPC, request devnet airdrops, and enforce session spend caps.
- **Hands-Free Setup**: Detect missing toolchains (solana-cli, anchor, rust, node) and guide installations when needed.
- **Mode Switching**: Toggle between planning, coding, and review modes for iterative development from the terminal.
- **Coding Loop**: Inspect files, apply patches safely, and run tests/lints from natural-language requests (slash commands remain optional).
- **Config Layers & Tool Controls**: Keep global credentials and defaults under `~/.solcoder/config.toml`, optionally add project overrides in `<project>/.solcoder/config.toml`, define per-tool policies (`allow`, `confirm`, `deny`), toggle behaviour per session, and audit every invocation.
- **Solana Knowledge Hub**: Query curated summaries of Anchor patterns, SPL token standards, cryptography tips, and runtime notes—powered by optional offline embeddings for semantic search.

## Quickstart
1. Install prerequisites: Python 3.11, Solana CLI, Anchor, Rust, Node.js.
2. Clone this repository and install dependencies:
   ```bash
   poetry install
   ```
3. Launch the agent:
   ```bash
   poetry run solcoder
   ```
4. On first launch, follow the prompts to set your LLM base URL and API key—credentials are encrypted and can be rotated later via `/config set`.
5. Complete the wallet wizard immediately after: choose **Create** or **Restore**, copy the recovery phrase someplace safe, and unlock the wallet so SolCoder can track balances. The passphrase you set for SolCoder encrypts the wallet too—no second password to remember.
6. Describe the dApp you want to build in plain language; reference project files with `@filename` and lean on slash commands (`/new`, `/deploy`, `/wallet`) only when you need deterministic control.
7. To resume an earlier run, pass the printed session ID: `poetry run solcoder --session <id>`; use `--new-session` to force a fresh context.
8. Global setup (LLM credentials, wallet secrets, default config) lives in `~/.solcoder/`. SolCoder also creates `<project>/.solcoder/` to capture session history and logs; drop a `config.toml` there if you need project overrides.
9. Inspect or tweak session metadata with `/settings`—for example, `/settings wallet <label>` or `/settings spend 0.75`.
10. Explore the built-in knowledge base: `poetry run solcoder` → `/kb search anchor macros` or ask “Explain the SPL token mint flow”. Rebuild embeddings with `poetry run python scripts/build_kb_index.py` after editing knowledge files.
11. Manage your Solana wallet via `/wallet`: start with `/wallet status` (shows lock state + current balance), run `/wallet create` to generate a new keypair, `/wallet unlock` to decrypt it for spending, `/wallet phrase` to view the recovery mnemonic (requires passphrase), and `/wallet export [path]` to copy the secret—omit `path` to print JSON, or supply one to write an on-disk backup with 0600 permissions.
12. Scaffold the reference counter workspace with `poetry run solcoder --template counter ./my-counter --program my_counter`. Inside the REPL you can run `/template counter ./my-counter` with optional `--program`, `--author`, and `--program-id` flags.

## Development Commands
- `poetry run pytest` — execute unit, integration, and e2e suites.
- `poetry run ruff check src tests` — lint Python sources and tests.
- `poetry run black src tests` — format code; add `--check` for CI parity.
- `poetry run solcoder --help` — inspect CLI flags and modes.
- `poetry run solcoder --dry-run-llm` — hit the live LLM once to confirm streaming before running full workflows.

## Project Layout
- `src/solcoder/cli/` — Prompt Toolkit REPL, command router, and UI widgets.
- `src/solcoder/core/` — shared services (config, session state, logging, tool orchestration).
- `src/solcoder/solana/` — wallet, RPC adapters, build/deploy flows, spend-policy enforcement.
- `templates/` — reusable Anchor blueprints (counter, NFT mint) plus client/README stubs.
- `tests/` — mirrors the package layout and holds e2e fixtures.
- `docs/` — strategy and planning artifacts (PRD, roadmap, WBS, milestones).

## Contributing
Please read `AGENTS.md` for contributor guidelines covering style, testing, and review expectations. Follow Conventional Commits, keep changes focused, and add regression tests for bug fixes.

## Roadmap & Status
- Progress is tracked in `docs/roadmap/milestones/`, `docs/roadmap/todo/`, `docs/roadmap/in_progress/`, and `docs/roadmap/done/`.
- The WBS (`docs/WBS.md`) and PRD (`docs/PRD.md`) outline priorities for the hackathon MVP.

### Milestones at a Glance
1. **Foundations & Onboarding** — repo/tooling, config wizard, wallet core, diagnostics, counter template ([MILESTONE-1](docs/roadmap/milestones/MILESTONE-1_FOUNDATIONS.md))
2. **Conversational Core** — live LLM streaming (`--dry-run-llm`), tool registry skeleton, status/log UX ([MILESTONE-2](docs/roadmap/milestones/MILESTONE-2_CONVERSATIONAL_CORE.md))
3. **Solana Deploy Loop** — guided installers, wallet policy, `/new`, `anchor build/deploy` wrappers ([MILESTONE-3](docs/roadmap/milestones/MILESTONE-3_SOLANA_DEPLOY_LOOP.md))
4. **Coding Workflow & Controls** — file intelligence, patch pipeline, command runner, context builder, tool policies ([MILESTONE-4](docs/roadmap/milestones/MILESTONE-4_CODING_WORKFLOW.md))
5. **Knowledge Hub & Prompts** — curated Solana docs, embeddings, `/kb search`, system prompts ([MILESTONE-5](docs/roadmap/milestones/MILESTONE-5_KNOWLEDGE_PROMPTS.md))
6. **Demo Polish & Packaging** — UX polish, tests/coverage, packaging, demo collateral, web search spike ([MILESTONE-6](docs/roadmap/milestones/MILESTONE-6_DEMO_POLISH.md))

## Codebase Context Strategy
- Each SolCoder launch creates a fresh session with its own transcript and context cache. You can resume a prior session by passing `--session <id>`, but context is always rebuilt on demand.
- Before every LLM turn, the agent assembles an ephemeral bundle: directory tree snapshot, relevant file excerpts (including any `@filename` mentions), git status/diffs, and recent conversation snippets.
- No remote vector database is used; context lives in memory for the active session and is discarded when SolCoder exits (apart from lightweight session metadata for resume/debug). Optional local embeddings (`knowledge/index.faiss`) stay on disk for faster knowledge search. Use `solcoder --dump-session <id>` to export the retained transcript when needed.
- Tool invocations respect allow/confirm/deny rules from your config: whitelisted tools run silently, blacklisted tools are blocked, and anything else asks for confirmation. All calls are logged (redacted) to `<project>/.solcoder/logs/` for auditing.
- Knowledge snippets pulled from `knowledge/` are appended to the context when relevant, giving the agent fast access to Solana best practices without network calls. When the embedding index is present, `/kb search` blends semantic and keyword ranking.
- This mirrors Codex CLI’s transient indexing approach: fast, scoped, and safe—without background services or long-lived embeddings. Web search and external API fetches are out of scope for the MVP; see `docs/roadmap/todo/TASK-3.7_WEB_SEARCH_SPIKE.md` for future exploration.

## Support & Feedback
Feature proposals, bug reports, and demo feedback are welcome via issues and discussions. For wallet or deployment problems, include your CLI output with sensitive secrets redacted.
