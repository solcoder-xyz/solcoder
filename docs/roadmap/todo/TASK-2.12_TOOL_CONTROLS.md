# Task 2.12 — Tool Controls & Audit Logging

- Milestone: [MILESTONE-4_CODING_WORKFLOW](../milestones/MILESTONE-4_CODING_WORKFLOW.md)

## Objective
Allow users to enforce explicit allow/deny policies for each agent tool (files, edit, command runner, wallet, deploy, shell aliases, etc.), where whitelisted tools run without prompts, blacklisted tools are rejected outright, and anything unspecified triggers an inline confirmation request—all while logging every invocation for auditing.

## Deliverables
- Configuration schema (`tool_controls`) supporting global/project overrides with three states: `allow` (no prompt), `deny` (hard block), and `confirm` (ask user each time).
- Runtime checks in the tool registry enforcing the configuration: auto-executing allowed tools, rejecting denied tools, and presenting confirmation prompts for anything marked `confirm` or absent from the lists.
- Session-level overrides (`/tools set <tool> allow|confirm|deny`, CLI `--tool-policy command_runner=deny`) that persist only for the active session.
- Audit log entries recording tool name, arguments summary, timestamp, session ID, and outcome status.
- Tests covering configuration merges, runtime enforcement, and log output.

## Key Steps
1. Extend config models (Task 1.5) to include a `tool_controls` block with default policies (`allow`, `confirm`, `deny`).
2. Update tool registry wrapper to consult controls before dispatching, trigger confirmation prompts for `confirm`/undefined tools, and emit audit records.
3. Create CLI/slash helpers for session overrides and ensure status bar reflects current restrictions.
4. Implement audit logger writing to `~/.solcoder/logs/tool_calls.log` (rotating) and exposing `/logs tools`.
5. Write tests in `tests/core/test_tool_controls.py` covering allow/confirm/deny behaviour, overrides, and logging.

## Dependencies
- Task 1.5 config overrides (layered configuration).
- Task 2.5 tool registry integration.
- Task 1.4 session lifecycle (session ID for logging).

## Acceptance Criteria
- Disabling a tool via config prevents both chat-triggered and slash-triggered usage, yielding friendly guidance.
- Tools marked `allow` execute without additional prompts; `deny` rejects immediately; unspecified or `confirm` tools display a confirmation request before proceeding.
- Audit log entries include session ID, tool, parameters summary, exit status, and error messages when applicable.
- Session overrides revert when SolCoder exits; documentation outlines how to adjust defaults globally or per project.
- Tests pass, and `/logs tools` displays recent invocations with redacted secrets.

## Owners
- CLI engineer primary; QA verifies enforcement and log rotation; Tech Lead signs off on safety defaults.
