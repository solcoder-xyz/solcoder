# Task 1.1 — Repo Tooling & Pre-Commit

- Milestone: [MILESTONE-1_FOUNDATIONS](../milestones/MILESTONE-1_FOUNDATIONS.md)

## Objective
Bootstrap consistent Python tooling so every contributor shares an identical lint/test baseline and the CLI installs cleanly on macOS/Ubuntu.

## Deliverables
- `pyproject.toml` configured for Python 3.11, `poetry`, `ruff`, `black`, and `pytest`.
- Pre-commit hooks covering formatting, linting, and basic security checks.
- `poetry.lock` validated on macOS 13 and Ubuntu 22 runners (documented in README).
- Updated `README.md` quickstart reflecting new commands.

## Key Steps
1. Define dependency groups (core vs dev) in `pyproject.toml` and regenerate `poetry.lock`.
2. Configure `ruff` and `black` settings (line-length 88, target 3.11) plus `pyproject` hooks.
3. Install and configure `pre-commit`, adding hooks for `ruff`, `black`, `mypy` (optional), and `detect-secrets`.
4. Run `poetry install` on both macOS and Ubuntu environments; record any discrepancies.
5. Update `README.md` and `AGENTS.md` with verified command snippets.

## Dependencies
None; this task kicks off Milestone 1.

## Acceptance Criteria
- Running `poetry install` then `poetry run ruff check` and `poetry run black --check` succeeds on CI smoke scripts.
- Pre-commit passes locally and instructions exist for setting it up.
- Documentation updates merged alongside tooling changes.

## Owners
- Tech Lead / CLI engineer as primary, QA/DevOps for cross-platform validation.
