# Task 1.4 — Session Lifecycle & History

- Milestone: [MILESTONE-1_FOUNDATIONS](../milestones/MILESTONE-1_FOUNDATIONS.md)

## Objective
Implement session management so every SolCoder launch starts a fresh conversational context with a unique ID, while allowing users to resume a prior session via CLI flags and storing lightweight transcripts for debugging.

## Deliverables
- Session ID generator (UUID or timestamp slug) surfaced on startup and stored under `<project>/.solcoder/sessions/`.
- CLI options: `solcoder --session <id>` to resume state (config, active project, recent history) and `--new-session` for an explicit reset.
- Session persistence layer capturing key metadata (start time, active template, last commands, wallet spend) plus trimmed transcript snippets (latest N turns).
- Secure storage reference for LLM credentials so sessions can reuse encrypted tokens without re-prompting.
- Cleanup/rotation policy keeping only the most recent N sessions unless the user pins one.
- Unit tests verifying session creation, resume, rotation, and corruption handling.

## Key Steps
1. Extend session manager model to include ID, created/updated timestamps, transcript buffer, and references to secure credential storage for LLM provider/wallet secrets.
2. Write persistence helpers to serialize/deserialize session metadata into JSON/TOML under `<project>/.solcoder/sessions/<id>/state.json`.
3. Update CLI entrypoint to parse `--session` flags, load existing state, and fall back to new session when not found.
4. Integrate session info into status bar and logs (e.g., `Session: a1b2c3`).
5. Add tests in `tests/core/test_session.py` covering creation, resume, invalid IDs, and rotation.
6. Document usage in README (`solcoder --session <id>`) and AGENTS guide.

## Dependencies
- Task 1.3 config & session services.
- Task 1.2 CLI shell for argument parsing and UI integrations.

## Acceptance Criteria
- Starting SolCoder prints `Session ID: <slug>` and writes metadata to disk.
- `solcoder --session <id>` restores recent context (active project path, wallet state, open logs) when available and gracefully falls back when missing.
- Transcript buffer keeps the last ~20 turns and can be inspected for debugging; rotation prevents unbounded disk growth.
- Tests pass; docs updated with instructions.

## Owners
- CLI engineer primary; QA validates resume behaviour on macOS/Ubuntu.
