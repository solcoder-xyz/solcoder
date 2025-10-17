# Repository Guidelines

SolCoder is a CLI-first AI agent that scaffolds, deploys, and funds Solana dApps. Align every contribution with delivering a fast prompt-to-deploy loop and dependable tooling.

## Project Structure & Module Organization
- `src/solcoder/cli/` hosts the Prompt Toolkit REPL, command router, and presentation widgets.
- `src/solcoder/core/` keeps shared services: config loading, session state, logging, and tool orchestration.
- `src/solcoder/solana/` bundles wallet management, RPC helpers, build/deploy adapters, and spend rules.
- `templates/` contains Anchor workspace blueprints plus README/client stubs; extend with descriptive folder names.
- Render templates via `poetry run solcoder --template <name> <path>` (or `/template <name> <path>` inside the REPL). Add `--program`, `--author`, `--program-id`, or `--force` to control metadata.
- `tests/` mirrors the package layout (`tests/cli`, `tests/core`, `tests/solana`, `tests/e2e`), while `docs/` captures product direction.

## Build, Test, and Development Commands
- `poetry install` provisions the Python 3.11 environment, dev dependencies, and CLI entrypoint.
- `poetry run solcoder` launches the interactive agent; `--help` lists slash commands.
- `poetry run solcoder --dry-run-llm` calls the live LLM client once (Task 2.5a) so issues surface early.
- `poetry run pytest` runs unit and integration suites; add `-m "not slow"` for quick passes.
- `poetry run ruff check src tests` enforces lint rules; address all findings before committing.
- `poetry run black src tests` formats sources and tests; use `--check` for CI parity.

## Coding Style & Naming Conventions
- Rely on Black (88-char lines, 4-space indents) and complete type hints on public APIs.
- Use `snake_case` for functions, `CamelCase` for classes, and `UPPER_SNAKE_CASE` for constants.
- Align module names with commands (`deploy.py`, `wallet.py`) to keep router wiring explicit.

## Testing Guidelines
- Pair each module with a matching `pytest` file (`tests/solana/test_wallet.py`) and mock RPC calls.
- Target ≥80% coverage on `src/solcoder/core` and `src/solcoder/solana`; add regression tests for every fix.
- Keep end-to-end flows in `tests/e2e/test_prompt_to_deploy.py` with recorded devnet fixtures for determinism.
- Run `poetry run pytest --maxfail=1` locally before opening pull requests; CI blocks merges on failures.

## Commit & Pull Request Guidelines
- Follow Conventional Commits (`feat:`, `fix:`, `chore:`) with imperative, present-tense summaries under 60 characters.
- Keep commits focused (one feature or fix), and ensure lint plus tests pass before pushing.
- PRs must link roadmap items, note test runs, and attach terminal captures for UX changes; request review from the relevant domain owner.

## Roadmap Workflow
- Treat milestone briefs in `docs/roadmap/milestones/` as epics; keep them updated when scope shifts.
- Individual task briefs live in `docs/roadmap/todo/`; when you pick one up, move the file to `docs/roadmap/in_progress/` and note the start date or PR ID inside.
- Once work ships and the user signs off, move the task file to `docs/roadmap/done/` and append a short summary plus merged commit reference.
- Reflect status changes in the parent milestone document so progress rolls up cleanly.
- Avoid duplicate copies—always move the markdown file so there is a single source of truth for each task.

## Configuration Layers & Tool Controls
- Keep global credentials and defaults in `~/.solcoder/config.toml`; add overrides in `<workspace>/.solcoder/config.toml` (created automatically on launch) when you need project-specific tweaks. CLI flags (or `--config <file>`) win over both.
- On first run, prompt for LLM base URL + API key; encrypt and store credentials alongside wallet secrets. Expose `/config llm rotate` (or similar) to update them without editing raw files.
- The SolCoder passphrase is the single secret for both credentials and wallet encryption—never prompt for a second wallet password.
- Document new config keys (e.g., `[tool_controls]`, spend caps, prompt variants) and keep examples in sync with `README.md`.
- Honour per-tool policies: `allow` executes without prompts, `deny` blocks immediately, and `confirm` (or unspecified) asks the user before running. The registry must enforce these rules and emit structured audit logs to `<workspace>/.solcoder/logs/tool_calls.log`.
- Expose session-scoped overrides via CLI flags or `/tools` commands and reset them when the process exits.
- When adding features, include tests for merge precedence, validation errors, confirmation flows, and logging output.
- Wallet onboarding happens through `/wallet create`, `/wallet restore`, `/wallet unlock`, `/wallet lock`, `/wallet status`, and `/wallet export`; keep prompts ergonomic and wire results back into session metadata so the status bar stays truthful (including balance fetched from the configured RPC endpoint).
- The CLI bootstrap must require wallet creation or restoration before the REPL launches, and prompt users to unlock existing wallets on subsequent runs.

## Session & Context Management
- Every SolCoder launch issues a new session ID and writes metadata under `<workspace>/.solcoder/sessions/<id>/`; surface the ID in the CLI header and status bar.
- Support `--session <id>` to resume a previous run (restores metadata + recent transcript) and `--new-session` to discard cached state.
- Keep transcripts lightweight (last ~20 turns) and rotate old sessions to prevent disk bloat; pin noteworthy sessions for demos when needed.
- Context is rebuilt on demand per LLM turn—directory tree, selected file excerpts, git diffs, recent messages—and destroyed when the process exits. No persistent vector DBs.
- When adding features, ensure they respect the transient context model and trigger context rebuilds after each edit or checkout.
- Provide export utilities (`solcoder --dump-session <id>` or `/session export`) with secret redaction so debugging artifacts can be shared safely.
- Session directories live under `<workspace>/.solcoder/sessions/<id>/state.json`; keep format stable (metadata + transcript) so resume logic and tests stay green.
- CLI options `--session <id>` and `--new-session` must be kept up to date when you change session semantics or rotation limits.

## Solana Knowledge Base
- Maintain curated summaries under `knowledge/` (runtime, Anchor patterns, SPL tokens, cryptography, Rust tips). Each file needs front-matter metadata (title, tags, source URL, last_reviewed).
- Keep entries concise (≈300–600 tokens) and cite official docs; do not copy long passages verbatim.
- Update `knowledge/index.json` whenever you add/edit entries; run the knowledge linter before committing.
- Use `/kb search` to verify content renders correctly and appears in the context builder logs.
- Record refresh cadence or outstanding gaps in the roadmap so coverage stays current.
- Keep the embedding index (`knowledge/index.faiss` or similar) in sync by rebuilding with `poetry run python scripts/build_kb_index.py` after content changes; commit both the index and checksum.
- Ensure the retrieval service gracefully falls back to keyword search when embeddings are unavailable; add tests when adjusting ranking logic.

## LLM Prompt & Conversation Rules
- Maintain system/assistant prompts under `prompts/` (see `docs/roadmap/todo/TASK-2.10_SYSTEM_PROMPTS.md`); every change needs review and a changelog note explaining behavioural tweaks.
- Encode safety rails in prompts: require inspect → edit → test loops, refuse destructive shell actions without explicit confirmation, and respect spend policies.
- Keep tool descriptions in sync with capabilities (file intelligence, edit pipeline, command runner) so the LLM knows when to call them.
- When chatting with the agent or drafting examples, use `@filename` to resolve shorthand references into full workspace paths; the runtime will expand and echo resolved paths back to the user.
- Prefer natural-language guidance in transcripts; reserve slash commands for deterministic, user-driven actions.
- Use `poetry run solcoder --dry-run-llm` after changing credentials or prompts to verify real streaming still works.
- Web search and external HTTP/API tools are deliberately out of scope for the MVP; treat any such additions as post-hackathon research (see `docs/roadmap/todo/TASK-3.7_WEB_SEARCH_SPIKE.md`) and gate them behind configuration once approved.

## Security & Configuration Tips
- Never commit private keys; store devnet keypairs under `~/.solcoder/keys/` (global) and reference them from config. Project-level keys can live under `<workspace>/.solcoder/keys/` only when they’re intentionally scoped.
- `/wallet export` must redact secrets in logs and only surface them to the user when explicitly requested; when a path is provided, write the secret to disk with 0600 permissions.
- `/wallet phrase` should always require the wallet passphrase and clearly remind the user to safeguard the mnemonic after displaying it.
- Pipe installers through `scripts/install_*.py` wrappers so the agent can request user confirmation.
- Log spend-cap changes at INFO, redact secrets by default, and reserve DEBUG for local troubleshooting.

## Troubleshooting
- Inside the CLI, run `/env diag` to verify required developer tools (`solana`, `anchor`, `rustc`, `cargo`, `node`, `npm`). The command reports detected versions and lists remediation steps for missing binaries so you can install them before continuing.
- Set the environment variable `SOLCODER_DEBUG=1` before launching `solcoder` to enable verbose logging without passing explicit CLI flags; omit it to keep the default INFO verbosity.
