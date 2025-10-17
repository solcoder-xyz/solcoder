# Task 3.5 — Template Hardening & Documentation

- Milestone: [MILESTONE-6_DEMO_POLISH](../milestones/MILESTONE-6_DEMO_POLISH.md)

## Objective
Finalize the NFT-mint template, polish existing templates, and ensure supporting docs equip users to extend or customize them.

## Deliverables
- Updated `templates/nft-mint/` workspace with verified Anchor program, tests, and README/client samples.
- Refreshed counter template README covering best practices and troubleshooting tips.
- Migration notes outlining how to add new templates, including naming conventions and metadata.
- Manual test evidence showing both templates build/deploy successfully via SolCoder.

## Key Steps
1. Implement NFT template instructions (mint authority, metadata accounts) and write tests.
2. Review counter template code/comments for clarity; align style between templates.
3. Document template registry process and how CLI discovers new templates.
4. Run full deploy loop for both templates, capturing logs for demo collateral.
5. Update docs (`README`, `AGENTS`, milestone notes) to reflect template availability.

## Dependencies
- Task 2.3 template pipeline and Task 2.4 deploy adapters.

## Acceptance Criteria
- Both templates deploy via `/new` + `/deploy` without manual tweaks.
- Documentation clearly explains template differences and customization entry points.
- Manual test logs archived in milestone folder; tests covering template rendering pass.

## Owners
- Solana/Anchor engineer primary; CLI engineer supports documentation updates.
