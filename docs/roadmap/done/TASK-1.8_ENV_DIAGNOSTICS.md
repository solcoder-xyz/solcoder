# Task 1.8 — Environment Diagnostics

- Milestone: [MILESTONE-1_FOUNDATIONS](../milestones/MILESTONE-1_FOUNDATIONS.md)

## Objective
Implement environment checks that detect required Solana/Anchor toolchain binaries and present actionable remediation guidance inside the CLI.

_Done — 2025-10-16 (CLI agent)_

## Deliverables
- `collect_environment_diagnostics` in `src/solcoder/core/env_diag.py` enumerates required toolchain binaries and surfaces version text plus remediation guidance.
- `/env diag` slash command renders a formatted status table, logs tool-call metadata, and ties into session transcripts.
- CLI launcher accepts direct invocation (`poetry run solcoder`) with DEBUG toggled via `SOLCODER_DEBUG`, defaulting to warning-level logging.
- Tests validate detection and CLI output (`tests/core/test_env_diag.py`, `tests/cli/test_shell.py`, `tests/test_cli_entrypoint.py`).
- Troubleshooting guidance in `AGENTS.md` now references `/env diag` and the debug toggle.

## Summary
Implemented the diagnostics collector, added CLI wiring with rich output, and tightened the entrypoint to honor environment flags while keeping default logging quiet. Updated docs and roadmap status.

## Owners
- CLI engineer primary; QA ran targeted pytest suites locally.
