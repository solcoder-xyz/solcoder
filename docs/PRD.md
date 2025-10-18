# Product Requirements Document (PRD) — SolCoder Hackathon MVP

**Product:** SolCoder
**Mode:** Interactive CLI agent (prompt-toolkit + Rich)
**Date:** Oct 15, 2025
**Owner:** Tech Lead / PM
**Status:** Ready for execution

---

## 1. Product Overview

**One-liner:**
SolCoder is a CLI-first AI agent that bootstraps your Solana environment, manages an autonomous wallet, and turns natural-language requests into deployed programs—all within one persistent terminal session.

**Experience flow:**
`solcoder` → onboarding wizard (wallet + LLM credentials + env checks) → conversational command panel (chat + slash commands) → inspect ▸ edit ▸ test ▸ deploy on devnet → demo-ready output.

**Key assets (deliverables)**
- Secure wallet & credential storage (solana keypair + LLM API key).
- Guided installers & diagnostics for Solana/Anchor toolchain.
- Conversational loop with live LLM streaming (`--dry-run-llm` smoke test).
- Template scaffolding and policy-aware deploy wrappers.
- Coding agent features: file intelligence, patch pipeline, command runner, context builder, tool controls.
- Offline Solana knowledge hub with optional embeddings feeding prompt context.
- Demo polish: error UX, tests/coverage, packaging, collateral.

---

## 2. Goals & Non-Goals

**Goals (MVP)**
1. Single-session onboarding with wallet + LLM credentials captured securely.
2. `/new` → `/deploy` loop on devnet ≤60s for curated Anchor templates.
3. Natural-language coding workflow (inspect → edit → test) with safe tool controls.
4. Offline Solana knowledge retrieval powering planning/review answers.
5. Demo-ready experience: modern CLI UX, packaging, fallback scripts.

**Non-Goals**
- Mainnet deployment, custody, or multisig support.
- Arbitrary code generation beyond curated templates and controlled diffs.
- GUI desktop app; CLI + Rich UI only.
- Persistent online vector DB or web search (post-MVP spike only).

---

## 3. Target Users & Value
- **New Solana builders:** zero-setup path to a devnet deploy with educational prompts.
- **Experienced devs:** faster scaffolds, one command for deploy/testing, wallet autonomy.
- **Hackathon judges:** polished “prompt → deploy → pay” story with knowledge-backed responses.

---

## 4. Success Metrics
| Metric | Target |
| --- | --- |
| Time from launch to first deploy | ≤ 60s on reference machine |
| Session reliability | ≥ 95% success for counter & NFT templates |
| Wallet policy enforcement | 100% overspend blocked or confirmed |
| Onboarding completion | ≥ 90% macOS/Ubuntu |
| Demo drill (onboarding → `/new` → `/deploy` → review) | < 7 minutes |

---

## 5. Scope & Milestones

| Milestone | Theme | Key Outcomes | Tasks | Time |
| --- | --- | --- | --- | --- |
| **M1** | Foundations & Onboarding | Repo + tooling, config wizard, session storage, wallet core, diagnostics, counter template | Tasks 1.1–1.9 | Day 0–1 |
| **M2** | Conversational Core | Live LLM streaming (`--dry-run-llm`), tool registry baseline, status/log UX | Tasks 2.1–2.3 | Day 1 (hrs 12–18) |
| **M3** | Solana Deploy Loop | Guided installers, wallet policy, `/new`, build/deploy wrappers | Tasks 3.1–3.4 | Day 1 eve – Day 2 morning |
| **M4** | Coding Workflow & Controls | File intelligence, patch pipeline, command runner, context builder, tool policies | Tasks 4.1–4.5 | Day 2 midday |
| **M5** | Knowledge Hub & Prompts | Solana knowledge base, embeddings, `/kb search`, system prompts | Tasks 5.1–5.4 | Day 2 evening |
| **M6** | Demo Polish & Packaging | UX polish, fallbacks, tests/coverage, packaging, demo collateral, optional web search spike | Tasks 6.1–6.7 | Day 3 |

*Detailed tasks, estimates, owners, dependencies, acceptance criteria are maintained in [docs/WBS.md](WBS.md).* 

---

## 6. User Journey & Key Moments

1. **First run (`poetry run solcoder`)**
   - Wizard captures: LLM base URL/model/API key (encrypted), wallet create/restore, environment check.
   - Option to resume previous session (`--session <id>`), start fresh (`--new-session`).
   - `/env diag` + `/env install` highlight missing tooling.

2. **Conversational loop**
   - `poetry run solcoder --dry-run-llm` verifies streaming before heavy usage.
   - Chat commands routed via tool registry; status bar shows wallet/spend/session.
   - `/help` or `/logs` provide visibility; offline mode fallback available.

3. **Deploy loop**
   - `/new "counter demo"` scaffolds Anchor workspace, updates session metadata.
   - `/deploy` builds/deploys to devnet, prints Program ID + explorer link, logs spend.
   - `/wallet status` confirms auto-airdrop/spend cap, `/logs deploy` shows run history.

4. **Coding workflow**
   - Ask “show me src/solcoder/core/config.py” → snippet with line numbers.
   - “Rename the config class” → patch validated, diff previewed, rollback possible.
   - “Run tests” → command runner streams `poetry run pytest --maxfail=1`.
   - Tool controls (`allow/confirm/deny`) enforce guardrails and audit logs.

5. **Knowledge-backed answers**
   - `/kb search pda` returns curated summary with citations.
   - Knowledge snippets inserted into context builder when relevant; prompts reference the same.

6. **Demo polish**
   - Error UX: human-readable message + “Try:” suggestion.
   - Coverage reports, packaging (`pipx install solcoder`), backup artifacts (prebuilt workspace, transcripts).
   - Demo script + failure playbook finalised.

---

## 7. Slash Command Spec (expanded)
```
/help                          # list commands & usage
/new "<prompt>" [--template counter|nft-mint] [--dir ./myapp]
/plan [--summary|--detailed]
/code [--apply] [--dry-run]
/review [--summary|--detailed]
/deploy [--network devnet|testnet|mainnet] [--force]
/wallet status|airdrop [AMOUNT]|policy|address|export|unlock|lock
/env diag|install [solana|anchor|rust|node]
/config get <key> | /config set <key> <value>
/tools set <tool> allow|confirm|deny
/kb search <query>
/logs [tools|build|deploy|wallet]
/session export [id]
/quit
```

---

## 8. Architecture Overview

**Languages & Frameworks:** Python 3.11, prompt_toolkit, Rich, Jinja2, cryptography, FAISS/AnnLite (optional), Typer/Click.

**Layers & Responsibilities**
1. CLI shell (`src/solcoder/cli/app.py`): prompt loop, status bar, slash router.
2. Session/config services (`src/solcoder/core/config.py`, `session.py`): layered config, secure credential store, transcript management.
3. Wallet service (`src/solcoder/solana/wallet.py`): keygen, encryption, spend meter, autopolicy.
4. Deploy adapters (`src/solcoder/solana/deploy.py`): wrapper around anchor CLI with structured output.
5. Tool registry (`src/solcoder/agent/tools.py`): callable entries + metadata for LLM tools.
6. LLM client (`src/solcoder/core/llm/client.py`): streaming, retries, offline fallback.
7. Knowledge services (`knowledge/`, `src/solcoder/knowledge.py`): indexing, search, context injection.
8. Context builder (`src/solcoder/agent/context_builder.py`): composes files/diffs/knowledge before each LLM call.
9. Command runner (`src/solcoder/core/commands.py`): whitelisted shell commands with streaming output.
10. Tool controls (`src/solcoder/core/policy.py`): allow/confirm/deny enforcement, audit logging.
11. Packaging & scripts (`scripts/`, `pyproject.toml`): installer/packaging flows, CI tasks.

**Security & Safety**
- Wallet keys encrypted at rest; LLM API key stored alongside (AES-GCM, optional keyring).
- Tool controls prevent destructive commands; confirmation prompts for risky actions.
- Spend cap/policy enforced with overrides behind explicit consent.
- Logs redact secrets; transcripts exportable with redaction.
- Optional offline mode ensures deterministic behaviour without network.

---

## 9. Risks & Mitigations
| Risk | Mitigation |
| --- | --- |
| Installer failures / slow downloads | Cache installers, provide manual fallback script, document homebrew alternative |
| Devnet instability | Retry/backoff, allow custom RPC endpoint, pre-record backup Program IDs |
| LLM streaming fails (rate limits, outages) | Retries + exponential backoff, offline fallback, `--dry-run-llm` smoke test before demos |
| Patch pipeline corrupts workspace | Use git stash/commit checkpoints, dry-run validation, clear rollback command |
| Token window overflow | Context builder token budgeting, snippet truncation with ellipsis and “open file” suggestion |
| Knowledge becomes stale / licensing issues | Summarize with citations, schedule refresh post-hackathon, note licensing per source |
| Demo reliability | Backup project, cached dependencies, failure playbook, recorded transcript |

---

## 10. Appendices
- [Milestone docs](./roadmap/milestones/) — detailed goals, success criteria, owners per milestone
- [Task briefs](./roadmap/todo/) — acceptance criteria, dependencies, test plans
- [Work Breakdown Structure](./WBS.md) — role mapping, estimates, critical path
- [Roadmap timeline](./roadmap/milestones/MILESTONE-1_FOUNDATIONS.md) — day-by-day view
- [Demo collateral] (to be produced in Milestone 6)
