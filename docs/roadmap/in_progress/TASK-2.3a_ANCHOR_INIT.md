# Task 2.3a — `/init` Anchor Workspace Initializer

- Milestone: [MILESTONE-3_SOLANA_DEPLOY_LOOP](../milestones/MILESTONE-3_SOLANA_DEPLOY_LOOP.md)

## Objective
Provide a first‑class command to initialize an Anchor workspace so users can immediately scaffold programs with `/new` and deploy in the same session.

## Command
`/init [DIRECTORY] [--name <workspace_name>] [--force] [--offline]`

- Without arguments, initializes an Anchor workspace in the current project root (where SolCoder runs).
- With `DIRECTORY`, initializes (or prepares) the workspace in that path (relative or absolute).
- `--name` overrides the anchor workspace name (defaults to directory name).
- `--force` allows re‑initializing minimal files in an existing directory (never overwrites non‑trivial content without explicit confirmation).
- `--offline` creates a minimal workspace scaffold (Anchor.toml, Cargo workspace, programs/) without invoking `anchor init` (for machines without Anchor installed); prints a follow‑up to run `/env install anchor` and `anchor build` later.

## Behavior
- Detect if an Anchor workspace already exists:
  - Search for `Anchor.toml` starting at target directory.
  - If found, print a friendly message (already initialized) and set active project to that root; offer a hint to run `/new <key>` to add a program.
  - If not found, proceed to initialize.
- Initialization strategies:
  1) Preferred: `anchor init <workspace_name>` at the target directory if the `anchor` CLI is available.
  2) Offline: minimal scaffold if `anchor` missing or `--offline` provided (create `Anchor.toml`, `Cargo.toml` with workspace members, `programs/`, `.gitignore`, basic README).
- After initialization succeeds:
  - Set `active_project` to the workspace root.
  - Log a build event; print next steps: `/new counter`, `/new token`, `/deploy` once ready.
  - On macOS/Windows, guard chmod/permissions; never fail on `PermissionError`.

## Checks & Prompts
- If `anchor` is not installed and not in `--offline` mode:
  - Suggest `/env install anchor` with a one‑line explanation and offer to switch to offline mode.
- If the target directory is non‑empty:
  - Prompt before adding files unless `--force` is set; always avoid overwriting existing non‑template files without confirm.
- If `Anchor.toml` exists but is malformed:
  - Warn the user; offer to back up and re‑create minimal files (opt‑in; `--force` required).

## Session Integration
- Update `session_context.metadata.active_project` and persist.
- Status bar shows the workspace path; subsequent `/new` defaults to adding programs under `programs/`.

## Tests
- `tests/cli/test_init_command.py`:
  - Initializes in root and custom directory.
  - Detects existing workspace and does not re‑initialize.
  - Offline scaffold path when `anchor` is not available.
  - `--force` behavior on non‑empty directories.
  - Session `active_project` update.

## Dependencies
- `/env diag` + installers for Anchor (Task 2.1).
- Session services (Task 1.3).

## Acceptance Criteria
- Running `/init` in a fresh directory creates an Anchor workspace (via `anchor init` if available, otherwise offline scaffold), sets active project, and prints next steps.
- `/init ./workspace` works with relative/absolute paths; on existing workspaces it is a no‑op with a helpful message.
- Behavior is Windows/macOS‑friendly; no crashes on chmod or missing tools.

