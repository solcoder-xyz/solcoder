```
   @@@@@@    @@@@@@   @@@        @@@@@@@   @@@@@@   @@@@@@@   @@@@@@@@  @@@@@@@
  @@@@@@@   @@@@@@@@  @@@       @@@@@@@@  @@@@@@@@  @@@@@@@@  @@@@@@@@  @@@@@@@@
  !@@       @@!  @@@  @@!       !@@       @@!  @@@  @@!  @@@  @@!       @@!  @@@
  !@!       !@!  @!@  !@!       !@!       !@!  @!@  !@!  @!@  !@!       !@!  @!@
  !!@@!!    @!@  !@!  @!!       !@!       @!@  !@!  @!@  !@!  @!!!:!    @!@!!@!
   !!@!!!   !@!  !!!  !!!       !!!       !@!  !!!  !@!  !!!  !!!!!:    !!@!@!
       !:!  !!:  !!!  !!:       :!!       !!:  !!!  !!:  !!!  !!:       !!: :!!
      !:!   :!:  !:!   :!:      :!:       :!:  !:!  :!:  !:!  :!:       :!:  !:!
  :::: ::   ::::: ::   :: ::::   ::: :::  ::::: ::   :::: ::   :: ::::  ::   :::
  :: : :     : :  :   : :: : :   :: :: :   : :  :   :: :  :   : :: ::    :   : :
```

# 🚀 Build Solana dApps at Light Speed

> ***Transform your ideas into deployed Solana programs through natural conversation with an AI agent—no boilerplate, no friction, no learning curve.***

---

## ✨ **The Vision**

SolCoder democratizes Solana development. Instead of wrestling with Rust, Anchor, and deployment workflows, you **describe what you want** and watch an AI agent **build and deploy it**.

Whether you're hacking on an idea at 2 AM, shipping to devnet in 60 seconds, or iterating on a production dApp—SolCoder gets out of your way:

- 🎯 **Describe in English** → "Create a token staking contract with 7-day lockup"
- 🤖 **AI handles the rest** → Code generation, testing, deployment
- ⚡ **Deploy in seconds** → From idea to live explorer link
- 🔒 **Your wallet, your keys** → Encrypted locally, zero cloud storage

This is the hackathon MVP. The roadmap reaches further: DePIN inference, on-chain reputation, a network of AI agents improving Solana itself.

---

## 🎯 **Why SolCoder?**

### The Pain Today
- **Week 1:** Install Rust, Solana CLI, Anchor, Node, pray dependencies resolve
- **Week 2:** Read 47 tutorials (all outdated), debate where to store keys
- **Week 3:** Debug "account not initialized" errors, cry silently
- **Week 4:** Finally deploy to devnet (but only localhost works)
- **Week 5:** Give up, hire $200/hr consultant

**Total cost:** Weeks of time, countless tutorials, deep frustration.

### The SolCoder Way
```
User:     "Build a token staking pool"
SolCoder: ✓ Generated Anchor program
          ✓ Wrote tests (92% coverage)
          ✓ Built contract
          ✓ Deployed to devnet
          Program: 8xQz...
          Explorer: solscan.io/...
Time:     ~90 seconds
Cost:     <$0.10 in LLM fees
```

---

## 🔑 **Core Features**

### 🤖 **Conversational Agent Interface**
Talk to SolCoder like you'd talk to a developer:

```
You:       "I want an NFT mint with metadata and royalties"
SolCoder:  Creates a plan:
           1. Generate Anchor program with token metadata extension
           2. Add royalty logic to transfer hook
           3. Write comprehensive tests
           4. Deploy to devnet and verify

You:       "Looks good, proceed"
SolCoder:  [Builds, tests, deploys...]
           ✓ Done! Your NFT mint is live
```

The agent thinks in **plans** (multi-step projects) and **replies** (quick answers). You can interrupt, ask questions, or let it run.

### 💳 **Built-In Wallet**
- **Generate or restore** Solana keypairs (BIP39 mnemonic support)
- **Military-grade encryption:** PBKDF2 (390k iterations) + AES-GCM
- **Session budgets:** Never overspend—cap how much SOL per session
- **Automated airdrops:** Request devnet funds with one command
- **Balance tracking:** Real-time updates in status bar

```bash
/wallet create              # Generate new keypair
/wallet status              # Check balance & lock state
/wallet address             # Show current public key
```

### 📦 **Blueprint Templates**
Start from production-ready projects:

- **Counter** — Basic on-chain state mutation
- **NFT Mint** — Full SPL Token with metadata
- **Token Staking** — Lockup periods and yield distribution (coming soon)
- **DAO Voting** — Governance with quadratic voting (coming soon)

Each includes:
- Full Rust implementation with comments
- Comprehensive test suite (80%+ coverage)
- Client stubs for off-chain interaction
- Deployment scripts and README

### 📚 **Offline Solana Knowledge Base**
Powered by a pre-built LightRAG workspace fine-tuned on Solana canon:
- **Anchor macros** and patterns
- **SPL Token-2022** standards
- **Solana runtime** concepts and best practices
- **Common pitfalls** and how to avoid them

- Query instantly from the REPL with `/kb "How does Proof of History work?"`.
- The autonomous agent can call the `knowledge_base_lookup` tool whenever it needs protocol context.
- Works completely offline once the workspace is unpacked locally; only your chosen LLM provider handles language generation.
- Set `SOLCODER_KB_BACKEND=local` to use the bundled index without importing LightRAG (useful for air-gapped demos).

### ⚙️ **Smart Environment Detection**
Missing Rust? Solana CLI? Node? SolCoder detects gaps and walks you through installation:

```bash
/env diag                   # Diagnose what's missing
/env install rust           # Auto-install via rustup
```

### 🎛️ **Flexible Control Modes**
- **Assistive** (default) → Agent runs autonomously
- **Guided** → Confirm before each tool invocation
- **Manual** → Slash commands only, no agentic behavior

Toggle anytime:

```bash
/settings mode assistive    # Full autonomy
/settings mode guided       # Confirm each step
/settings mode manual       # Slash commands only
```

### 🔐 **Three-Tier Configuration**
1. **Global defaults** → `~/.solcoder/config.toml`
2. **Project overrides** → `.solcoder/config.toml` (in your workspace)
3. **CLI flags** → Override everything at runtime

Example:
```bash
poetry run solcoder --llm-model gpt-5-codex --llm-reasoning high
```

### 📊 **Session Persistence**
Every conversation is saved. Pick up where you left off:

```bash
poetry run solcoder --session abc123def456    # Resume session
poetry run solcoder --dump-session abc123     # Export transcript
```

Sessions stored in `~/.solcoder/sessions/<id>/state.json` with full history, tool calls, and metadata.

---

## 🚀 **Quick Start (3 Minutes)**

### Prerequisites
- **Python 3.11+**
- **Git**
- *(Optional) Rust, Solana CLI, Anchor — SolCoder can install these for you*

### Installation

**Option A: Global Install via pipx (Recommended)**
```bash
git clone https://github.com/solcoder/SolCoder.git
cd SolCoder
./scripts/install_pipx.sh

# Now run from any directory
solcoder
```

**Option B: Local Development via Poetry**
```bash
git clone https://github.com/solcoder/SolCoder.git
cd SolCoder
poetry install
poetry run solcoder
```

**Option C: Makefile Helpers**
```bash
make install              # Global install via pipx
make install-local        # Local editable install
poetry run solcoder       # Launch
```

### Knowledge Base Setup (Recommended)

1. **Install dependencies & unpack the workspace**
   ```bash
   make setup-kb
   ```
   The Make target installs the vendored `LightRAG[api]` package into your Poetry
   environment and extracts `third_party/solana-rag/solana-knowledge-pack.tgz` into
   `var/lightrag/solana/`.

2. **Verify the install**
   ```bash
   ls var/lightrag/solana/lightrag
   ```
   You should see multiple `kv_store_*.json` and `vdb_*.json` files alongside
   `graph_chunk_entity_relation.graphml`. Re-run the setup with
   `poetry run python scripts/setup_kb.py --force` if you need to refresh the pack.

3. **Provide API credentials**
   Ensure your `OPENAI_API_KEY` (or an alternative provider supported by SolCoder) is
   available in the environment before running the agent or `/kb` command. Set
   `SOLCODER_KB_BACKEND=local` to force the fully offline retrieval path when you do not
   want to import the `LightRAG` dependency.

### Using the Knowledge Base

```bash
/kb "How does Proof of History work?"
```

- Answers stream directly in the REPL together with source citations.
- The autonomous agent can call the `knowledge_base_lookup` tool automatically whenever
  it needs protocol context for planning or validation.
- Override the knowledge pack location by setting `WORKING_DIR=/custom/path` before
  launching `solcoder`.

### Your First Project (60 Seconds)

1. **Start SolCoder:**
   ```bash
   poetry run solcoder
   ```

2. **Configure LLM** (first time only):
   - Enter your OpenAI/Anthropic API key (encrypted, cached locally)
   - Choose model and reasoning effort

3. **Create/restore wallet:**
   - Generate new keypair or restore from mnemonic
   - Set session spend cap (optional, default 0.1 SOL)

4. **Describe your dApp:**
   ```
   You: "Build a token staking pool with 7-day lockup and 5% APY"
   ```

5. **Watch it build:**
   ```
   SolCoder: Creating plan:
            1. Generate Anchor program structure
            2. Implement staking logic with timelock
            3. Add yield calculation
            4. Write tests
            5. Build and deploy

   [Proceeds autonomously...]

   ✓ Deployed!
   Program ID: 8xQz...
   Explorer: solscan.io/...
   ```

---

## 💬 **Real Agent Conversations**

### Scenario 1: Multi-Step Project (Using Agent Loop)

```
You: "Create an NFT collection manager with on-chain metadata and royalties"

SolCoder: I'll help you build that. Here's my plan:
         1. Generate Anchor program with SPL Token extension
         2. Add metadata store for collection info
         3. Implement royalty logic in transfer hook
         4. Write tests for edge cases
         5. Deploy to devnet

You: "Skip the royalties, I'll add later"

SolCoder: Updated plan:
         1. Generate Anchor program with SPL Token extension
         2. Add metadata store for collection info
         3. Write tests for core functionality
         4. Deploy to devnet

[SolCoder runs each step, showing progress...]

✓ All done! Your NFT manager is live at 8xQz...
```

### Scenario 2: Quick Question (Instant Reply)

```
You: "What's the SPL Token-2022 format for metadata?"

SolCoder: The SPL Token-2022 metadata extension uses:
         - Mint extension: stores key metadata (name, symbol, URI)
         - Group pointer: links to token group for fungibles
         - Metadata pointer: embeds metadata on-chain

         You can use:
         spl_token_metadata_interface::state::TokenMetadata

         Query it with:
         let metadata = TokenMetadata::deserialize(&data)?;
         println!("Name: {}", metadata.name);
```

### Scenario 3: Debugging (With Agent Assistance)

```
You: "My test is failing with 'insufficient funds' error"

SolCoder: Let me check your test and fix it. [Reads test file...]

         I found the issue: Your test needs to request an airdrop
         before creating the staking account.

         [Generates fix...]

         ✓ Fixed! Run tests again: poetry run pytest

You: "Done, all green now"

SolCoder: Excellent! Ready to deploy to devnet?
```

---

## 🎮 **Interactive Commands (Slash Syntax)**

For quick, deterministic actions, use slash commands (no LLM):

| Command | Purpose |
|---------|---------|
| `/help` | List all available commands |
| `/wallet create` | Generate new keypair |
| `/wallet status` | Check balance & lock state |
| `/wallet address` | Show current public key |
| `/env diag` | Diagnose missing tools (Rust, Solana, Anchor) |
| `/env install <tool>` | Auto-install (rust, solana, anchor, node) |
| `/template list` | Show available blueprint templates |
| `/blueprint counter` | Create a Counter program from template |
| `/new` | Initialize new Anchor workspace |
| `/kb <question>` | Query the Solana knowledge base with citations |
| `/init` | Convert existing folder to Anchor project |
| `/deploy` | Build and deploy current workspace to devnet |
| `/deploy verify` | Verify deployment on devnet |
| `/toolkits list` | Show available tools for the agent |
| `/toolkits <name> tools` | Show tools in a toolkit |
| `/settings mode <level>` | Change control mode (assistive/guided/manual) |
| `/settings spend <sol>` | Set session budget |
| `/todo add <task>` | Add TODO item |
| `/todo list` | Show all TODO items |
| `/todo done <id>` | Mark TODO as done |
| `/session list` | Show all saved sessions |
| `/session resume <id>` | Load previous session |
| `/logs` | View session logs |
| `/quit` | Exit SolCoder gracefully |

### Command Examples

```bash
# Check what needs installing
/env diag

# Auto-install missing tools
/env install rust

# Create a new Anchor workspace
/new

# List templates
/template list

# Scaffold a Counter program
/blueprint counter

# Deploy it
/deploy

# Query the Solana knowledge base
/kb "Explain Solana rent exemptions"

# Check wallet balance
/wallet status

# Set session budget
/settings spend 0.5

# Resume previous session
/session resume abc123def456
```

---

## 🧰 **How Tools Work (Agent's Capabilities)**

The agent has access to these toolkits:

| Toolkit | Purpose |
|---------|---------|
| **solcoder.planning** | Generate structured project plans |
| **solcoder.code** | File operations (read, write, insert) |
| **solcoder.blueprint** | Scaffold programs from templates |
| **solcoder.deploy** | Build, test, and deploy |
| **solcoder.wallet** | Wallet operations |
| **solcoder.knowledge** | Search Solana KB |
| **solcoder.diagnostics** | Environment checks |
| **solcoder.workspace** | Detect and validate projects |
| **solcoder.token** | Create SPL tokens quickly |
| **solcoder.metadata** | Manage token metadata |
| **solcoder.command** | Run shell commands safely |

You see these in action automatically—the agent chooses the right tool for each step.

---

## 🛠️ **Development & Testing**

### Run Tests
```bash
poetry run pytest                    # Full suite
poetry run pytest -m "not slow"      # Quick feedback
poetry run pytest --cov=solcoder     # Coverage report (target ≥80%)
```

### Code Quality
```bash
poetry run ruff check src tests      # Lint
poetry run black src tests           # Format
poetry run black src tests --check   # Check (CI mode)
```

### LLM Configuration
```bash
# Test connectivity once
poetry run solcoder --dry-run-llm

# Use offline stubs (for demos)
poetry run solcoder --offline-mode

# Override provider & model
poetry run solcoder --llm-provider openai --llm-model gpt-5-codex

# Control reasoning effort
poetry run solcoder --llm-reasoning high
```

### Knowledge Base
```bash
# Rebuild embeddings after editing docs
poetry run python scripts/build_kb_index.py
```

---

## 📁 **Project Layout**

```
SolCoder/
├── src/solcoder/
│   ├── cli/                 # REPL, commands, branding
│   ├── core/                # Agent loop, tool registry, config
│   ├── solana/              # Wallet, RPC, build/deploy
│   └── session/             # Session persistence
├── templates/               # Blueprint projects (Counter, NFT)
├── tests/                   # Unit, integration, e2e
├── docs/                    # PRD, roadmap, WBS
├── knowledge/               # Solana KB & embeddings
├── scripts/                 # Build scripts
└── poetry.lock              # Dependencies
```

---

## 📊 **Roadmap: Building the Future**

### ✅ **Phase 1: Hackathon MVP (Live Now)**
- [x] CLI agent with JSON schema contracts
- [x] Conversational interface (plan → tool → result loops)
- [x] Built-in wallet with encryption (PBKDF2 + AES-GCM)
- [x] Anchor scaffolding & deployment to devnet
- [x] Counter & NFT Mint templates
- [x] Offline Solana knowledge base
- [x] Session persistence & resumption
- [x] Multi-provider LLM support (OpenAI, Anthropic)

### 🎯 **Phase 2: DePIN-Powered Inference (Q3 2025)**
Decentralized LLM inference network backed by Solana:

- [ ] Integrate with DePIN platforms (Gradient, Gensyn, etc.)
- [ ] Transparent Solana-settled pricing (no middleman)
- [ ] Multi-provider LLM routing for redundancy
- [ ] Advanced patch pipeline & safety checks
- [ ] Web search spike for knowledge augmentation

**Vision:** Users pay only for compute they use, verified on-chain.

### 🟣 **Phase 3: SolCoder Token (SCR) (Q1 2026)**
Native token enabling ecosystem growth:

- [ ] Launch SCR token on Solana
- [ ] Pay-for-inference with SCR
- [ ] Staking rewards for inference providers
- [ ] Governance voting (template priorities, fund allocation)
- [ ] Community grants fund (distribute SCR to contributors)

**Why token?** Aligns incentives—the more builders use SolCoder, the more nodes run, the better inference becomes.

### 🌌 **Phase 4: Agentic Contribution Network (Q2 2026+)**
The boldest vision: **AI agents maintaining the Solana ecosystem**

**How it works:**

1. **Deploy Your Node**
   ```
   solcoder --network-mode
   └─ Lock SCR as collateral
   ```

2. **Accept Contribution Tasks**
   Agents propose and execute:
   - 🐛 Find & fix bugs in popular Solana crates
   - 🔧 Extend Anchor macro library
   - 📚 Improve documentation
   - 🧪 Write test coverage
   - 🎯 Design SPL standards

3. **Earn On-Chain Reputation & Rewards**
   ```
   Contribution → Code Review → Validation → SCR Reward
                                 ↓
                          Public Reputation on-chain
   ```

4. **Solana Ecosystem Accelerates**
   - Hundreds of AI agents working 24/7
   - Bugs caught earlier, features shipped faster
   - Community-vetted, cryptographically signed PRs
   - Sustainable incentives via SCR rewards

**Example flow:**
```
Node Operator submits to network:
  "I can fix bugs in anchor-lang"
    ↓
Agent network proposes task:
  "Add missing tests to macro module"
    ↓
Agent executes:
  - Audit code
  - Identify gaps
  - Write tests
  - Submit PR with explanation
    ↓
Community validates:
  - Code review passes
  - Tests pass
  - Maintainers approve
    ↓
Agent earns SCR + public reputation
```

**End Goal:** 10,000+ AI agents maintaining Solana, enabling 100x developer velocity.

---

## 🤝 **Contributing**

SolCoder is **100% open-source** under MIT. We welcome contributions from builders of all levels.

### **How to Contribute**

1. **Share feedback**
   - [GitHub Discussions](https://github.com/solcoder/SolCoder/discussions) — Ideas, questions
   - [GitHub Issues](https://github.com/solcoder/SolCoder/issues) — Bugs, enhancements

2. **Improve code**
   - Fork the repo → Create feature branch → Make changes → Test → PR
   - Follow [CLAUDE.md](./CLAUDE.md) for architecture & coding standards
   - Target ≥80% coverage in `src/solcoder/core` and `src/solcoder/solana`

3. **Add templates**
   - Create Anchor blueprint in `templates/`
   - Include tests, client stubs, README
   - Submit PR with use-case

4. **Expand knowledge base**
   - Write Solana deep-dives in `knowledge/`
   - Improve Anchor patterns docs
   - Submit PRs or Discussions

5. **Improve docs & UX**
   - Write tutorials for beginners
   - Improve error messages
   - Translate to other languages

### **Development Workflow**

```bash
# Setup
poetry install
poetry run solcoder --dry-run-llm     # Verify LLM config

# Make changes
# ...

# Before committing
poetry run ruff check src tests
poetry run black src tests
poetry run pytest --maxfail=1

# Commit (Conventional Commits)
git commit -m "feat: add staking template"

# Push & open PR
git push origin feat/staking-template
```

### **Areas We Need Help**

- 🎨 **UI/UX** — Improve REPL styling, themes, error messages
- 🧪 **Testing** — Expand e2e coverage, edge cases
- 📚 **Docs** — Tutorials, guides, API reference
- 🔗 **Templates** — Token Staking, DAO Voting, AMM, Escrow
- 🌍 **Localization** — Translate docs and messages
- 🔒 **Security** — Audit, fuzzing, vulnerability research

### **Future: SCR Token Rewards**

Early contributors (Phase 1-3) will receive **retroactive airdrops** and **governance power** when SCR launches in Q1 2026.

---

## 📖 **Documentation**

| Document | Purpose |
|----------|---------|
| **[README](./README.md)** | This file—overview & quick start |
| **[CLAUDE.md](./CLAUDE.md)** | Deep-dive on architecture, patterns, config system |
| **[AGENTS.md](./AGENTS.md)** | Contributor guidelines & style standards |
| **[PRD](./docs/PRD.md)** | Product requirements & vision statement |
| **[WBS](./docs/WBS.md)** | Work breakdown structure (tasks & owners) |
| **[Roadmap](./docs/roadmap/)** | Detailed phase plans & milestones |
| **[Whitepaper](https://solcoder.xyz/whitepaper.pdf)** | Full vision & technical approach |

---

## 🆘 **Support & Feedback**

- 💬 **[GitHub Discussions](https://github.com/solcoder/SolCoder/discussions)** — Ask questions, share ideas, show demos
- 🐛 **[GitHub Issues](https://github.com/solcoder/SolCoder/issues)** — Report bugs or request features
- 🐦 **[Twitter/X](https://x.com/solcoderxyz)** — Latest updates and announcements
- 📧 **[Email](mailto:contact@solcoder.xyz)** — Direct contact
- 💬 **[Telegram](https://t.me/+pNKuDgtZ0H9lM2U0)** — Community chat

---

## 📜 **License & Security**

- **License:** MIT (open-source, use freely)
- **Security:** For wallet or deployment issues, include CLI output (with API keys redacted)
- **Privacy:** Keys stored locally only, encrypted with PBKDF2 + AES-GCM
- **No telemetry:** SolCoder doesn't phone home

---

## 🙏 **Acknowledgments**

Built with love by the SolCoder team and inspired by the Solana community. Special thanks to:

- **Anchor team** — Excellent framework that made this possible
- **Solana validators & DePIN pioneers** — Infrastructure backbone
- **Hackathon judges & mentors** — Early feedback and support
- **You** — For believing in a vision where anyone can build on Solana

---

<div align="center">

## ⚡ **Ready to Build?**

```bash
poetry run solcoder
```

**Transform your Solana ideas into deployed dApps at light speed.**

🚀 **SolCoder** — *Where AI meets blockchain.*

</div>

---

<div align="center">

**Made with ❤️ for the Solana ecosystem** | [GitHub](https://github.com/solcoder/SolCoder) | [Twitter](https://twitter.com/solcoderxyz) | [Whitepaper](https://solcoder.xyz/whitepaper.pdf)

</div>
