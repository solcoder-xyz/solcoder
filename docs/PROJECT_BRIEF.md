⚡ Project Brief — SolCoder (Hackathon MVP)

🧠 Concept

SolCoder is a CLI-first AI agent that lets you describe a Solana dApp in plain English and watch the terminal scaffold, test, deploy, and fund it on devnet—no manual setup required.

It bundles live LLM reasoning, secure wallet automation, anchor build/deploy wrappers, and a curated Solana knowledge hub into one terminal experience.

⸻

💡 Core Differentiator

“Talk to SolCoder — it boots your environment, codes your app, deploys it, and even pays the fees.”

Unlike generic coding agents, SolCoder is chain-aware and ships with offline Solana expertise plus an autonomous wallet.

⸻

🛠️ MVP Scope (Milestones)

**M1 — Foundations & Onboarding (Day 0–1)**
- Repo/tooling, README/AGENTS refresh
- First-run wizard: LLM base URL/model/API key, wallet create/restore, env diagnostics
- Secure session storage (`--session`, `--new-session`, `--dump-session`)
- Counter Anchor template scaffold

**M2 — Conversational Core (Day 1, hrs 12–18)**
- Live LLM streaming (`poetry run solcoder --dry-run-llm`), retries, offline fallback
- Tool registry skeleton for plan/code/review
- Status bar + `/logs` v1 (session ID, active tool, recent calls)

**M3 — Solana Deploy Loop (Day 1 eve – Day 2 AM)**
- `/env diag` + `/env install` guided tooling
- Wallet balance/auto-airdrop/spend policy enforcement
- `/new` template pipeline, session metadata updates
- `anchor build/deploy` wrappers, explorer link parsing

**M4 — Coding Workflow & Controls (Day 2 midday)**
- Workspace discovery (`/files`, `/search`, `/open`) via chat
- Patch pipeline with validation, diff preview, rollback
- Command runner (`run tests`, `run lint`) with streaming output
- Ephemeral context builder + token budgeting
- Tool controls (allow/confirm/deny) + audit logging

**M5 — Knowledge Hub & Prompts (Day 2 evening)**
- Offline Solana knowledge base (runtime, Anchor, SPL, crypto, Rust tips)
- Optional embedding index for semantic search
- `/kb search` and automatic snippet injection into context
- Versioned system/assistant prompts with safety rails

**M6 — Demo Polish & Packaging (Day 3)**
- UX polish (error guidance, collapsible logs, diff UX)
- Offline fallbacks, deterministic responses for outages
- Tests/coverage (`poetry run pytest --cov` ≥80%), CI artifacts
- Packaging (`pipx install solcoder`), demo script, backup project
- Optional web search spike (report only)

⸻

🌟 WOW Moments
1. **Prompt → Deploy → Pay**: In one conversation, SolCoder scaffolds an Anchor workspace, deploys to devnet, shows Program ID + explorer link, and logs spend under a policy cap.
2. **Autonomous Wallet**: Agent wallet auto-requests devnet airdrops, tracks spend, and blocks overspending unless the user confirms.
3. **Conversational Coding**: “Show me `src/solcoder/core/config.py`,” “Apply this diff,” “Run tests” — all handled safely with previews, rollbacks, and audit logs.
4. **Embedded Solana Knowledge**: `/kb search PDA` retrieves curated, citation-backed notes that inform the agent’s plan/review responses—without network fetches.
5. **First-run Wizard**: Zero-config onboarding captures both wallet and LLM credentials securely, so every demo starts with a magical handshake.

⸻

🚀 Hackathon Mission
Deliver a live demo where a judge can:
1. Launch `solcoder` → watch onboarding set up wallet, LLM, environment.
2. Describe a dApp → see SolCoder plan, scaffold, and deploy it on devnet.
3. Ask for tweaks → observe the agent inspect files, apply diffs, run tests.
4. Request context → `/kb` surfaces Solana best practices inline.
5. Exit with confidence → transcripts exported, packaging ready, backup artifacts on hand.

🎯 Demo target: <7 minutes, resilient to network hiccups, polished CLI aesthetics.

