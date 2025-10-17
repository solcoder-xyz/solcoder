# Task 3.3 — Test Automation & Coverage

- Milestone: [MILESTONE-6_DEMO_POLISH](../milestones/MILESTONE-6_DEMO_POLISH.md)

## Objective
Expand automated testing to hit ≥80% coverage for `src/solcoder/core` and `src/solcoder/solana`, adding e2e scripts that exercise onboarding through deploy.

## Deliverables
- Additional unit tests covering spend policy edge cases, RPC failure retries, and CLI command flows.
- E2E test script (pytest marker) simulating onboarding → `/new` → `/deploy` with mocked RPC responses.
- Coverage reporting integrated into CI pipeline with fail-under thresholds.
- Documentation explaining how to run fast vs full test suites.

## Key Steps
1. Audit current coverage report; identify high-risk gaps.
2. Implement new tests using fixtures/mocks to avoid real network calls.
3. Create e2e test harness leveraging recorded devnet fixtures; mark as `slow`.
4. Configure `pytest.ini` or `pyproject` for coverage reporting and thresholds.
5. Update README/AGENTS with testing commands and environments.

## Dependencies
- Tasks from Milestones 1 and 2 providing core functionality.

## Acceptance Criteria
- `poetry run pytest --cov` meets coverage thresholds; CI fails if coverage drops.
- E2E test passes locally and in CI with controlled fixtures.
- Documentation clearly differentiates between quick and full test runs.

## Owners
- QA/DevOps, with contributions from Wallet and Solana engineers for fixtures.
