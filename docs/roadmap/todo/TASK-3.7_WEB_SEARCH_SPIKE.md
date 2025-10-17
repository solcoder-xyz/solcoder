# Task 3.7 — Web Search Spike (Post-MVP)

- Milestone: [MILESTONE-6_DEMO_POLISH](../milestones/MILESTONE-6_DEMO_POLISH.md)

## Objective
Evaluate the feasibility of adding a web search/fetch tool after the MVP, outlining requirements, safety controls, and integration costs before committing to full implementation.

## Deliverables
- Discovery doc comparing options (third-party APIs, custom scraper, MCP server) with security and rate-limit considerations.
- Prototype tool schema (even if stubbed) describing how web search results would be surfaced to the LLM, including token budgeting and citation format.
- Risk assessment covering network egress policies, user consent, and audit logging.
- Recommendation on whether to pursue web search in a future iteration, with required effort and timeline.

## Key Steps
1. Inventory potential APIs or MCP adapters that could support search (Bing, Google CSE, Perplexity, etc.) and note licensing constraints.
2. Draft tool contract (inputs/outputs) and confirm how it would fit into the existing tool controls (`allow/confirm/deny`).
3. Evaluate sandbox and configuration updates needed to safely enable outbound HTTP requests.
4. Document findings in `/docs/roadmap/done/` (or similar) and link back to Milestone 3 as a stretch recommendation.

## Dependencies
- Completion of MVP features (Milestones 1 & 2) to ensure core loop is stable before exploring web search.

## Acceptance Criteria
- Written report and recommendation checked into `docs/done/` or `docs/roadmap/` with owners assigned for any follow-up work.
- No code changes required for MVP; tooling remains Solana/local-only until a future decision is made.

## Owners
- Tech Lead or Research engineer; QA/security reviewers consulted for risk assessment.
