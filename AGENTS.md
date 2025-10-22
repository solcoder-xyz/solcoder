# Repository Guidelines

## Project Structure & Module Organization
Core CLI code lives under `src/solcoder/cli/` (Prompt Toolkit REPL, command router, widgets). Shared services such as config, session state, logging, and tool orchestration sit in `src/solcoder/core/`, while `src/solcoder/solana/` handles wallets, RPC helpers, and deploy adapters. Anchor-ready blueprints reside under `src/solcoder/anchor/blueprints/<key>/template`, and matching tests in `tests/cli`, `tests/core`, `tests/solana`, and `tests/e2e`. Keep roadmap docs in `docs/roadmap/` synchronized with milestone status.

## Build, Test, and Development Commands
Install dependencies once with `poetry install`. Launch the agent via `poetry run solcoder`, or dry-run the LLM request path using `poetry run solcoder --dry-run-llm`. The default provider hits OpenAI's Responses API with the `gpt-5-codex` model at `medium` reasoning effort; override via `--llm-model`, `--llm-reasoning`, or config, or adjust on the fly with `/settings model …` and `/settings reasoning …`. Run fast feedback loops with `poetry run pytest -m "not slow"` and enforce the full suite using `poetry run pytest`. Lint and format with `poetry run ruff check src tests` and `poetry run black src tests --check`. When editing knowledge entries, rebuild embeddings through `poetry run python scripts/build_kb_index.py`.

Tooling is exposed through the registry (`src/solcoder/core/tool_registry.py`) and grouped into toolkits under `src/solcoder/core/tools/`. Use `/toolkits list` and `/toolkits <toolkit> tools` in the CLI to inspect what the agent can call; direct user invocation of individual tools is intentionally disabled so orchestration stays behind the scenes.

## Coding Style & Naming Conventions
Format Python with Black (88-character lines, 4-space indents) and satisfy Ruff before committing. Public APIs need full type hints, and modules should mirror command names (e.g., `deploy.py`, `wallet.py`). Follow `snake_case` for functions, `CamelCase` for classes, and `UPPER_SNAKE_CASE` for constants. Prefer brief, purposeful comments ahead of complex logic; keep documentation in Markdown under `docs/`.

## Testing Guidelines
Use `pytest` with fixtures that mock Solana RPC interactions. Maintain ≥80% coverage in `src/solcoder/core` and `src/solcoder/solana`, and add regression tests for every fix or feature. Structure new tests alongside their modules (e.g., `tests/solana/test_wallet.py`). Before merging, run `poetry run pytest --maxfail=1` to surface failures early, and ensure knowledge updates pass the linter.

## Commit & Pull Request Guidelines
Write Conventional Commit messages (`feat:`, `fix:`, `chore:`) in present tense under 60 characters. Each PR should link the relevant roadmap task, note test and lint runs, and include CLI output for UX changes. Keep commits focused and ensure CI-critical commands (`ruff`, `black --check`, `pytest`) pass locally before pushing.

## Security & Configuration Tips
Global defaults live in `~/.solcoder/config.toml`; project overrides sit in `<workspace>/.solcoder/config.toml`, with CLI flags taking priority. Store Solana keys under `~/.solcoder/keys/` and respect spend policies (`allow`, `deny`, `confirm`) through the tool registry. Wallet onboarding flows (`/wallet create`, `/wallet restore`, `/wallet unlock`) should complete before entering the REPL, and wallet exports must redact secrets unless the user explicitly requests output. Keep logs in `<workspace>/.solcoder/logs/` and rotate sessions under `.solcoder/sessions/`.
