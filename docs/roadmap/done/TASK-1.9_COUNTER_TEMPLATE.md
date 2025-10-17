# Task 1.9 — Counter Template Scaffold

- Milestone: [MILESTONE-1_FOUNDATIONS](../milestones/MILESTONE-1_FOUNDATIONS.md)

## Objective
Deliver the reference Anchor counter template and supporting files so the deploy loop has a verified baseline project.

_Done — 2025-10-16 (CLI agent)_

## Deliverables
- `templates/counter/` workspace with Anchor program, tests, client stub, and README placeholders.
- Rendering utility `render_template` + CLI `/template` command (also available via `solcoder --template`).
- Tests covering renderer, CLI integration, and entrypoint flag handling (`tests/core/test_templates.py`, `tests/cli/test_shell.py`, `tests/test_cli_entrypoint.py`).
- Docs updated in `README.md` and `AGENTS.md` describing template usage.

## Summary
Implemented a reusable renderer that substitutes metadata into the counter template, exposed it through CLI command/flags, and added regression tests. Template renders cleanly; manual `anchor build` will be verified once the installer task provisions Anchor (tracked for Task 2.x installers) to avoid partial setup on contributors.

## Owners
- Solana/Anchor engineer primary; CLI engineer integrated renderer.
