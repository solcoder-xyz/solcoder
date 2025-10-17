# Task 3.4 — Packaging & Distribution

- Milestone: [MILESTONE-6_DEMO_POLISH](../milestones/MILESTONE-6_DEMO_POLISH.md)

## Objective
Prepare SolCoder for `pipx` distribution, validate installs on clean machines, and document the installation path for judges and contributors.

## Deliverables
- Packaging configuration (console entry points, dependency extras) ready for PyPI/pipx.
- Automated script or instructions for building and publishing test artifacts.
- Validation logs from macOS and Ubuntu clean environments confirming `pipx install solcoder` and CLI launch.
- README and AGENTS updates noting packaging workflow and troubleshooting tips.

## Key Steps
1. Finalize `pyproject.toml` metadata (version, description, classifiers).
2. Configure build backend (Poetry or PDM) to produce wheels and source distributions.
3. Test `pipx install` using local wheel and remote artifact to ensure dependencies resolved.
4. Capture install/uninstall steps, note common failures, and document in README.
5. Optionally explore PyInstaller single binary; document decision outcome.

## Dependencies
- Requires stable functionality from Milestones 1 & 2.

## Acceptance Criteria
- `pipx install <local-wheel>` followed by `solcoder --help` succeeds on both target OS setups.
- Documented fallback instructions provided if packaging fails due to environment constraints.
- Packaging configuration checked into repo with CI job to verify build integrity.

## Owners
- QA/DevOps lead; Tech Lead approves release-ready metadata.
