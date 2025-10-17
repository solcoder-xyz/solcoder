# Task 1.5 — Global & Project Config Overrides

- Milestone: [MILESTONE-1_FOUNDATIONS](../milestones/MILESTONE-1_FOUNDATIONS.md)

## Objective
Support layered configuration so contributors can define global defaults in `~/.solcoder/config.toml` and override them per project using `.solcoder/config.toml`, mirroring Codex CLI’s setup.

_In progress — 2025-10-16 (CLI agent)_

## Deliverables
- Config loader that merges global + project-local files, with deterministic precedence (project overrides global; CLI flags override both).
- Autodiscovery of `.solcoder/config.toml` from the current workspace root (configurable via `--config` flag).
- Validation errors surfaced with actionable messages referencing which file caused the issue.
- Tests validating merge order, missing-file fallbacks, and environment variable overrides.
- Documentation updates describing config layering and example snippets for tool toggles, LLM provider overrides, prompts, and spend policies.

## Key Steps
1. Extend existing config module to look for `~/.solcoder/config.toml` and `<project>/.solcoder/config.toml`.
2. Implement merge logic preserving nested structures (e.g., `[tool_controls]`) with clear conflict resolution.
3. Allow CLI flags (e.g., `--config`) to point to custom config files and bypass project discovery when needed.
4. Add unit tests in `tests/core/test_config.py` covering merge precedence, invalid TOML, and missing directories.
5. Update `README.md` and `AGENTS.md` to show layered config examples.

## Dependencies
- Task 1.3 config & session services.

## Acceptance Criteria
- Running `poetry run solcoder` in a project with `.solcoder/config.toml` merges settings with the global file and logs which overrides are active, including LLM endpoints/models while reusing securely stored API keys.
- CLI flags can override both layers and are reflected in the status bar/session metadata.
- Tests pass; documentation clearly explains where to place global vs project configuration.

## Owners
- CLI engineer primary; QA verifies behaviour on macOS/Ubuntu with sample projects.
