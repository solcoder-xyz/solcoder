# Task 3.1 — UX Polish & Error Messaging

- Milestone: [MILESTONE-6_DEMO_POLISH](../milestones/MILESTONE-6_DEMO_POLISH.md)

## Objective
Refine user-facing messages, add actionable error guidance, and improve visual presentation so the demo feels production-ready.

## Deliverables
- Human-readable error summaries with “Try:” hints for common failure cases (install, build, deploy).
- Collapsible build/deploy log sections and copy-to-clipboard snippets in CLI output.
- Style adjustments (color palette, spacing, spinner usage) aligned with demo script.
- Regression tests ensuring formatted errors contain guidance text.

## Key Steps
1. Audit existing messages; categorize by command and severity.
2. Implement error wrapper that maps exceptions to user-friendly summaries and remediation hints.
3. Upgrade Rich widgets to support collapsible sections and copy commands.
4. Run manual UX review with team, capture feedback, iterate.
5. Add tests verifying error mappings and formatting.

## Dependencies
- Tasks 2.4 and 2.6 for deploy logs and status bar infrastructure.

## Acceptance Criteria
- All critical commands provide actionable guidance on failure, validated via manual scenario testing.
- Visual polish matches demo expectations; screenshots added to demo collateral.
- Tests covering error mapping pass; no regression in existing CLI behavior.

## Owners
- CLI engineer primary; Tech Lead signs off on UX.
