## 0. Roles & Assumptions

**Team (wear multiple hats if smaller):**

* **TL** = Tech Lead / PM / Prompt engineer  
* **CLI** = Python CLI & UX engineer  
* **SOL** = Solana / Anchor engineer  
* **WAL** = Wallet & Security engineer  
* **QA/DO** = QA, DevOps, Packaging  

**Target platforms:** macOS 13+, Ubuntu 22+ (primary), Windows via WSL for smoke tests.  
**LLM providers:** GPT‑4/5 (primary), Claude optional; credentials captured securely on first run.

---

## 1. WBS Tree (hierarchical)

**1. Foundations & Onboarding (P0)**  
* **1.1** Repo & tooling bootstrap (poetry, lint/format, CI smoke)  
* **1.2** Core docs (README, AGENTS, roadmap quickstart)  
* **1.3** Config defaults + first-run wizard (LLM base URL/model/API key, spend caps, network)  
* **1.4** Session lifecycle (ID, transcript buffer, secure credential storage)  
* **1.5** Config overrides (global + project `.solcoder/config.toml`, CLI overrides)  
* **1.6** Session transcript export (`--dump-session`, `/session export`)  
* **1.7** Wallet core (create/restore/unlock, AES-GCM, key management)  
* **1.8** Environment diagnostics (`/env diag`, required tool checks)  
* **1.9** Counter template scaffold (Anchor workspace + README/client stub)

**2. Conversational Core (P0)**  
* **2.1** Live LLM integration spike (streaming client, retries, offline fallback, `--dry-run-llm`)  
* **2.2** Tool registry skeleton (plan/code/review stubs, tool metadata)  
* **2.3** Status bar & `/logs` v1 (session ID, active tool, recent output)

**3. Solana Deploy Loop (P0)**  
* **3.1** Guided installers (`/env install` for solana-cli, anchor, rust, node)  
* **3.2** Wallet balance, auto-airdrop, spend policy enforcement  
* **3.3** `/new` template pipeline (selection, rendering, session metadata)  
* **3.4** Build & deploy adapters (`anchor build/deploy`, explorer links, logging)

**4. Coding Workflow & Controls (P0)**  
* **4.1** Workspace discovery (`/files`, `/search`, `/open`, chat intents)  
* **4.2** Automated editing pipeline (patch validation, previews, rollback)  
* **4.3** Command runner (lint/test/build aliases via chat or `/run`)  
* **4.4** Ephemeral context builder (files/diffs/knowledge snippets per turn)  
* **4.5** Tool controls & audit logging (allow/confirm/deny, session overrides, `/logs tools`)

**5. Knowledge Hub & Prompts (P0/P1)**  
* **5.1** Curated Solana knowledge base (runtime, Anchor, SPL, crypto, Rust tips)  
* **5.2** Offline embedding index (FAISS/SQLite, deterministic rebuild)  
* **5.3** Knowledge retrieval & context injection (`/kb search`, hybrid ranking)  
* **5.4** System & assistant prompts (tool schemas, safety rails, knowledge usage)

**6. Demo Polish & Packaging (P1)**  
* **6.1** UX polish & error messaging (“Try:” hints, collapsible logs, diff previews)  
* **6.2** Agent fallbacks & offline flows (LLM outages, deterministic responses)  
* **6.3** Test automation & coverage (unit + e2e, spend policy, RPC failure)  
* **6.4** Packaging & distribution (`pipx`, smoke on clean hosts)  
* **6.5** Template hardening & docs (NFT mint template, README updates)  
* **6.6** Demo collateral & playbook (script, backup artifacts, screenshots)  
* **6.7** Web search spike (post-MVP research, gated tool) **(P2)**

---

## 2. Task Table (IDs, estimates, owners, deps, acceptance)

> Estimates are person-hours. P0 = critical path. Tasks marked **(P2)** are optional stretch goals.

| ID   | Task                                                       | Est | Owner        | Depends                   | Acceptance Criteria |
|------|-----------------------------------------------------------|----:|--------------|---------------------------|---------------------|
| 1.1  | Repo & tooling bootstrap                                  | 2   | TL/CLI       | —                         | `poetry install`, lint/format pipelines succeed |
| 1.2  | Core docs (README, AGENTS, roadmap)                       | 1.5 | TL           | 1.1                       | Quickstart + roadmap reflect latest milestones |
| 1.3  | Config defaults + LLM wizard                              | 3   | CLI          | 1.1                        | First run prompts for LLM base URL/model/API key, saves encrypted credentials, writes config with sane defaults |
| 1.4  | Session lifecycle & secure storage                        | 2.5 | CLI          | 1.3                       | Session ID printed, metadata persisted, secure credential reference stored, resume works |
| 1.5  | Config overrides (global + project)                       | 1.5 | CLI          | 1.3                       | `.solcoder/config.toml` overrides merge with global; `/config` commands reflect layered state |
| 1.6  | Session transcript export                                 | 1.5 | CLI          | 1.4                       | `--dump-session` & `/session export` output redacted transcripts, rotation respected |
| 1.7  | Wallet core & encryption                                  | 3   | WAL          | 1.3,1.4                   | `/wallet status` shows masked address; create/restore/unlock works; files 0600 |
| 1.8  | Environment diagnostics                                   | 2   | CLI          | 1.3                       | `/env diag` lists required tools, remediation text logged |
| 1.9  | Counter template scaffold                                 | 2.5 | SOL          | 1.3                       | Template renders/builds via `anchor`; README/client stub included |
| 2.1  | LLM integration spike (streaming client)                  | 3   | CLI/Prompt   | 1.2–1.4                   | `poetry run solcoder --dry-run-llm` streams tokens, retries/timeouts logged, offline flag works |
| 2.2  | Tool registry skeleton                                    | 3   | CLI          | 2.1,1.9                   | Plan/Code/Review stubs registered; tool metadata exposed |
| 2.3  | Status bar & `/logs` v1                                   | 2   | CLI          | 2.2                       | Status bar shows session/tool info; `/logs tools` lists recent calls |
| 3.1  | Guided installers (`/env install`)                        | 4   | SOL          | 1.8                       | `/env install anchor` installs tooling, reports success/failure |
| 3.2  | Wallet policy (balance, airdrop, spend cap)               | 3   | WAL          | 1.7,3.1                   | Auto-airdrop triggers below threshold; overspend blocked with guidance |
| 3.3  | `/new` template pipeline                                  | 3   | CLI          | 1.9,3.1                   | `/new "<prompt>"` renders workspace, registers in session |
| 3.4  | Build & deploy adapters                                   | 4   | SOL          | 3.2,3.3                   | `/deploy` wraps `anchor build/deploy`, logs output, prints Program ID + explorer URL |
| 4.1  | Workspace discovery & search                              | 3   | CLI          | 2.3,3.4                   | `/files`, `/search`, `/open`, chat intents show highlighted content with context |
| 4.2  | Automated editing pipeline                                | 4   | CLI          | 4.1,3.4                   | Patches validated (`git apply --check`), diff summary displayed, rollback command works |
| 4.3  | Command runner & `/test`                                  | 3   | CLI          | 4.1,3.4                   | “Run tests” streams command output, timeouts/cancel handled |
| 4.4  | Ephemeral context builder                                 | 3   | CLI          | 2.1,4.1,4.3               | Context bundles include files/diffs; reset on session change; logs show included snippets |
| 4.5  | Tool controls & audit logging                             | 3   | CLI          | 4.2,4.3                   | Allow/confirm/deny policies enforced; `/tools set` overrides session-only; audit log redacts secrets |
| 5.1  | Solana knowledge base curation                            | 4   | TL/SOL       | 3.4                       | Knowledge entries with metadata/citations committed; lint passes |
| 5.2  | Knowledge embedding index                                 | 3   | CLI/ML       | 5.1                       | `scripts/build_kb_index.py` generates deterministic index; checksum records |
| 5.3  | Knowledge retrieval & context injection                   | 3   | CLI          | 5.1,5.2,4.4               | `/kb search` returns ranked results; context builder appends relevant snippets |
| 5.4  | System prompts & safety rails                             | 3   | Prompt/TL    | 2.1,2.2,5.3               | Versioned prompts checked in; transcripts show inspect→edit→test behaviour |
| 6.1  | UX polish & error messaging                               | 3   | CLI          | 4.5,5.4                   | Errors include “Try:” hints; logs collapsible; diffs formatted |
| 6.2  | Agent fallbacks & offline flows                           | 2   | CLI/Prompt   | 2.1,5.4                   | LLM outages fall back to deterministic guidance; toggle configurable |
| 6.3  | Test automation & coverage                                | 3   | QA/DO        | 3.4,4.3,5.4               | `poetry run pytest --cov` ≥80% on core modules; e2e covers onboarding→deploy |
| 6.4  | Packaging & distribution                                  | 2.5 | QA/DO        | 6.3                       | `pipx install solcoder` works on clean macOS/Ubuntu |
| 6.5  | Template hardening & docs                                 | 2   | SOL          | 3.4                       | NFT mint template validated; docs updated |
| 6.6  | Demo collateral & playbook                                | 2   | TL/QA        | 6.1–6.5                   | Demo script, backups, screenshots ready; failure playbook logged |
| 6.7  | Web search spike (post-MVP, **P2**)                       | 2   | TL/Research  | 5.4                       | Report summarizing API options, safety considerations, recommendation |

---

## 3. Critical Path (P0)

1. **Foundations:** 1.1 → 1.3 → 1.4 → 1.7 → 1.8 → 1.9  
2. **Conversational core:** 2.1 → 2.2 → 2.3  
3. **Deploy loop:** 3.1 → 3.2 → 3.3 → 3.4  
4. **Coding workflow:** 4.1 → 4.2 → 4.3 → 4.4 → 4.5  
5. **Knowledge & prompts:** 5.1 → 5.2 → 5.3 → 5.4  
6. **Polish:** 6.1 → 6.3 → 6.4 → 6.6  

Risk hot spots: installing anchor/rust (3.1), deploy parsing (3.4), LLM streaming stability (2.1), patch pipeline (4.2), token budgeting in context builder (4.4), knowledge freshness (5.1). Mitigation: cache installers, provide manual fallback scripts, log retries, use git checkpoints, monitor token counts, schedule knowledge refresh.

---

## 4. 72‑Hour Hackathon Timeline

**Day 1 (0 – 24h) — Foundations & Conversational Core**  
* Morning (0‑8h): 1.1–1.5 (repo, docs, config wizard), start 1.7.  
* Midday (8‑16h): finish 1.7–1.9, ship session export. Kick off 2.1 LLM spike.  
* Evening (16‑24h): complete 2.1–2.3 (LLM streaming, tool registry, status/logs).  
  *Checkpoint @ T24h:* `--dry-run-llm` streams live tokens; wallet onboarding works; counter template builds.

**Day 2 (24 – 48h) — Deploy Loop & Coding Workflow**  
* Morning (24‑32h): 3.1 installers + 3.2 wallet policy.  
* Midday (32‑40h): 3.3 `/new` pipeline + 3.4 deploy adapters. Achieve `/new` → `/deploy` golden path.  
* Afternoon (40‑48h): 4.1–4.3 (file intelligence, edit pipeline, command runner).  
  *Checkpoint @ T48h:* Chat-driven inspect→edit→test works on counter template; devnet deploy produces Program ID.

**Day 3 (48 – 72h) — Knowledge, Prompts & Demo Polish**  
* Morning (48‑56h): 4.4 context builder + 4.5 tool controls.  
* Midday (56‑64h): 5.1–5.4 (knowledge base, embeddings, retrieval, prompts).  
* Afternoon (64‑72h): 6.1–6.6 polish, coverage, packaging, demo collateral. Optional 6.7 web search spike if time permits.  
  *Final Checkpoint:* Full loop recorded (transcript + video), backup artifacts ready, demo script rehearsed under seven minutes.
