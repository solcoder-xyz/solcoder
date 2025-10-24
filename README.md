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

> ***An AI-powered CLI agent that transforms natural-language ideas into fully deployed Solana programs—no boilerplate, no delays, no friction.***

---

## ✨ **The Vision**

SolCoder democratizes Solana development by removing the learning curve and repetitive setup work. Whether you're a hackathon participant pitching a bold DeFi experiment or a seasoned builder iterating at breakneck speed, SolCoder meets you where you are: **describe what you want, and watch it build**.

This hackathon edition brings:
- **Instant scaffolding** from natural-language specs
- **Built-in wallet management** with encrypted key storage
- **Live deployment** to devnet with explorer links
- **Knowledge base** covering Anchor patterns, SPL standards, and Solana best practices
- **Session persistence** so you can pick up where you left off

---

## 🎯 **Mission & Values**

| 🧠 | **Intelligence** | AI-assisted planning + human control; no black boxes |
|---|---|---|
| ⚡ | **Speed** | Deploy working dApps in seconds, not days |
| 🔒 | **Security** | Encrypted wallet storage, audited tool calls, transparent policies |
| 🌐 | **Open** | Open-source, community-driven, built on DePIN principles |

---

## 🔑 **Core Features**

### 🤖 **Conversational Agent Loop**
Describe your dApp idea in plain English. SolCoder's agent orchestrates code generation, testing, and deployment through a structured loop—no slash commands required (but they're there if you need determinism).

### 💳 **Built-In Wallet**
Generate or restore Solana keypairs. SolCoder encrypts them locally (PBKDF2 + AES-GCM), tracks your balance in real-time, and enforces session spend caps so you never overspend on gas.

### 📦 **Reusable Templates**
Clone from production-ready blueprints (Counter, NFT Mint) and customize on the fly. Each template includes client stubs, tests, and README scaffolds.

### 📚 **Solana Knowledge Base**
Embedded summaries of Anchor macros, SPL token standards, cryptography tips, and runtime notes. Local embeddings (FAISS) enable semantic search—no external calls, pure offline mode.

### ⚙️ **Hands-Free Environment Setup**
Missing Rust? Solana CLI? Anchor? SolCoder detects gaps and walks you through guided installers. One command launches a complete dev environment.

### 🎛️ **Flexible Control**
Choose your mode: **Assistive** (full agentic autonomy), **Guided** (confirm before each tool), or **Manual** (slash commands only). Toggle at runtime via `/settings mode`.

### 🔐 **Config Layering & Audit Trail**
- **Global defaults** in `~/.solcoder/config.toml`
- **Project overrides** in `.solcoder/config.toml`
- **CLI flags** override everything
- Every tool invocation logged for transparency

---

## 🚀 **Quick Start**

### Prerequisites
- **Python 3.11+**, **Node.js**, **Rust**, **Solana CLI**, **Anchor**

### Installation

Before installing dependencies, activate a Python virtual environment (optional but
recommended for local development):

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
```

Option A — Global install via pipx (recommended)
```bash
git clone https://github.com/solcoder/SolCoder.git
cd SolCoder

# Install pipx if needed; then install SolCoder globally
./scripts/install_pipx.sh

# Now run the CLI from any directory
solcoder
```

Option B — Local dev via Poetry
```bash
git clone https://github.com/solcoder/SolCoder.git
cd SolCoder
poetry install
poetry run solcoder
```

Option C — Makefile helpers
```bash
# Install via pipx using the Makefile recipe
make install

# Install the local checkout in editable mode inside your active venv
make install-local
```
Using `make install-local` keeps the CLI pointed at your working copy so local changes
are reflected immediately when you invoke `solcoder`.

### Your First Project (2 min walkthrough)

1. **LLM Setup** — Enter your OpenAI/Anthropic API key (encrypted, asked once)
2. **Wallet Wizard** — Create a new keypair or restore from mnemonic
3. **Describe Your dApp** — e.g., *"Build a token swap contract with 2% fee. I want to deploy to devnet."*
4. **Watch It Build** — SolCoder scaffolds → builds → deploys → shows you the explorer link
5. **Resume Anytime** — `poetry run solcoder --session <id>` picks up your context

### Example Commands

```bash
# Global CLI
solcoder --help

# Resume previous session
poetry run solcoder --session abc123def456

# Force fresh context
poetry run solcoder --new-session

# Scaffold a template project
poetry run solcoder --template counter ./my-counter --program my_counter

# Test LLM connectivity
poetry run solcoder --dry-run-llm

# Offline mode (demos, no network)
poetry run solcoder --offline-mode
```

### One‑Line Token + Metadata Flow

```bash
# Quick Token‑2022 mint (decimals=0, supply=1M) and on‑chain metadata write
solcoder
/new token --quick --decimals 0 --supply 1000000 --cluster devnet \
  --meta-name "SolCoder Token" --meta-symbol SCT \
  --meta-uri file:///absolute/path/to/metadata.json \
  --meta-royalty-bps 500 --meta-run
```
If you omit --meta-uri, SolCoder auto‑generates a local metadata.json and uses its file:// URI. You can also upload assets first:

```bash
/metadata upload --file ./image.png
/metadata wizard --mint <MINT>    # prompts and then writes on‑chain (optional)
```

---

## 🎮 **Interactive Commands**
| Command | Purpose |
|---------|---------|
| `/init [DIR] [--offline]` | Initialize an Anchor workspace (in CWD or DIR) |
| `/new <key>` | Start blueprint wizard (counter, token, nft, registry, escrow) |
| `/program inspect <program_id>` | Inspect on-chain IDL (Anchor-first) or SPL catalog |
| `/program call <program_id> ...` | Prepare/execute memo/token flows; confirm before send |
| `/wallet status` | Check balance & lock state |
| `/wallet airdrop [amt]` | Request devnet/testnet airdrop with spinner and retry |
| `/wallet policy ...` | Show/update spend cap and auto-airdrop policy |
| `/wallet create` | Generate new keypair |
| `/wallet unlock` | Decrypt wallet for spending |
| `/wallet phrase` | View recovery mnemonic |
| `/toolkits list` | Show available automation |
| `/settings mode <level>` | Toggle assistive/guided/manual |
| `/settings spend <sol>` | Set session budget |
| `/deploy` | Manual deploy to devnet |
| `/config set` | Rotate LLM credentials |

### Examples

```bash
# Initialize a workspace in the current directory (no Anchor required)
/init --offline

# Initialize a named workspace under ./workspace (uses anchor init if available)
/init workspace --name my_workspace

# Add a counter program to an existing Anchor project
/new counter

# Inspect an Anchor program by id (falls back to SPL catalog)
/program inspect <PROGRAM_ID>
```

---

## 🧰 **Toolkits (Agent-Callable Tools)**

List toolkits and tools in the REPL:

```bash
/toolkits list
/toolkits solcoder.workspace tools
```

Notable tools:
- `solcoder.workspace.init_anchor_workspace` — initializes an Anchor workspace by dispatching `/init ...`.
- `solcoder.wallet.request_airdrop` — dispatches `/wallet airdrop ...` with spinner/polling.
- `solcoder.program.*` — inspects or prepares program calls; CLI confirms/executes safely.

---

## 📋 **Architecture at a Glance**

```
┌─────────────────────────────────────────────┐
│        CLI (Prompt Toolkit REPL)            │  🖥️ Your Interface
├─────────────────────────────────────────────┤
│   Agent Loop + Tool Registry (JSON Schema)  │  🧠 Orchestration
├─────────────────────────────────────────────┤
│  Wallet | RPC | Build | Deploy | Knowledge │  ⛓️  Solana Layer
└─────────────────────────────────────────────┘
```

**Each layer is independent:**
- Add new tools without touching CLI
- Swap LLM providers (OpenAI → Anthropic) with one flag
- Run offline or live seamlessly

---

## 🛠️ **Development & Testing**

### Run Tests
```bash
poetry run pytest                    # Full suite
poetry run pytest -m "not slow"      # Fast feedback
poetry run pytest --cov=solcoder     # Coverage report
```

### Code Quality
```bash
poetry run ruff check src tests      # Linting
poetry run black src tests           # Formatting
poetry run black src tests --check   # CI mode
```

### LLM Configuration
```bash
# Override provider & model
poetry run solcoder --llm-provider openai --llm-model gpt-5-codex

# Control reasoning effort
poetry run solcoder --llm-reasoning high

# Smoke-test connectivity
poetry run solcoder --dry-run-llm
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
│   ├── cli/          # Prompt Toolkit REPL, commands, branding
│   ├── core/         # Agent loop, tool registry, config, session
│   ├── solana/       # Wallet, RPC, build/deploy adapters
│   └── session/      # Session persistence
├── templates/        # Blueprint projects (Counter, NFT Mint)
├── tests/            # Unit, integration, e2e fixtures
├── docs/             # PRD, roadmap, milestones, WBS
├── knowledge/        # Curated Solana docs & embeddings
└── poetry.lock       # Dependency snapshot
```

---

## 🌟 **What's Next: Beyond Hackathon**

### **Phase 2: DePIN-Powered Inference**

After shipping the hackathon MVP, SolCoder will integrate with decentralized inference networks on Solana:

- **Distributed LLM calls** powered by DePIN platforms (Gradient, Gensyn, etc.)
- **No single point of failure** — redundancy built in
- **Transparent pricing** — pay what you use, only when deployed

```
User ─► SolCoder ─► DePIN Router ─► [Node 1, Node 2, Node 3] ─► Result
                                      (Solana-settled)
```

### **Phase 3: SolCoder Token (SCR)**

A native token enabling:

- **Pay-for-inference** — Use SCR to execute agentic jobs
- **Staking rewards** — Run a node, earn SCR from inference traffic
- **Governance** — Vote on template additions, feature priorities
- **Community fund** — Allocate SCR to developer grants & bounties

**Why token?** Aligns incentives. The more builders use SolCoder, the more nodes run, the better inference becomes.

### **Phase 4: Agentic Contribution Network**

The boldest vision: **a network of AI agents extending the Solana ecosystem**.

**How it works:**

1. **Deploy Your Node** — Run SolCoder in "network mode"; lock SCR as collateral
2. **Accept Contribution Tasks** — Agents propose:
   - 🐛 Find & fix bugs in popular Solana crates
   - 🔧 Extend Anchor macro library
   - 📚 Improve documentation
   - 🧪 Write test coverage
   - 🎯 Design new SPL standards

3. **Earn Reputation & Rewards**
   - Validated contributions earn SCR tokens
   - Build public developer reputation on-chain
   - Top contributors get featured in ecosystem

4. **Solana Grows Faster**
   - Hundreds of AI agents working 24/7 on ecosystem improvements
   - Bugs caught earlier, features shipped faster
   - Community-approved, cryptographically signed changes

**Example flow:**
```
Node Operator ─┐
               ├─► Agent Network ─► "Audit anchor-lang for missing tests"
Developer     ─┘                     └─► Automated PR + validation
                                        └─► SCR reward if accepted
```

This is **Solana's distributed workforce**. Not replacing humans—amplifying them.

---

## 🤝 **Contributing**

We welcome contributions from builders of all levels. Here's how:

### **Ideas & Feedback**
- [**Discussions**](https://github.com/solcoder/SolCoder/discussions) — Share feature requests, ask questions
- [**Issues**](https://github.com/solcoder/SolCoder/issues) — Report bugs or propose enhancements

### **Code Contributions**

1. **Fork & clone** the repository
2. **Create a feature branch** — `git checkout -b feat/my-feature`
3. **Follow our style guide** — See `CLAUDE.md` for architecture & coding standards
4. **Write tests** — Target ≥80% coverage in `src/solcoder/core` and `src/solcoder/solana`
5. **Run checks** — Ensure `ruff`, `black`, and `pytest` pass
6. **Commit & push** — Use Conventional Commits (`feat:`, `fix:`, `chore:`)
7. **Open a PR** — Link relevant roadmap tasks & explain the "why"

### **Areas We Need Help**

- 🎨 **UI/UX** — Improve REPL styling & error messages
- 🧪 **Testing** — Expand e2e coverage for edge cases
- 📚 **Documentation** — Add tutorials & guides for common patterns
- 🔗 **Templates** — Submit new Anchor blueprint projects
- 🌍 **Localization** — Translate docs & error messages

### **Development Commands**

```bash
# Setup
poetry install
poetry run solcoder --dry-run-llm

# Before committing
poetry run ruff check src tests
poetry run black src tests
poetry run pytest --maxfail=1

# Code review
poetry run solcoder --dump-session <id>  # Export session for analysis
```

See **[AGENTS.md](./AGENTS.md)** for detailed contributor guidelines.

---

## 📊 **Roadmap**

### ✅ **Hackathon MVP (Live Now)**
- [x] CLI agent loop with JSON schema contracts
- [x] Built-in wallet (PBKDF2 + AES-GCM encryption)
- [x] Anchor build & deploy to devnet
- [x] Counter & NFT Mint templates
- [x] Solana knowledge base with embeddings
- [x] Session persistence & resumption
- [x] Config layering (global/project/CLI)

### 🎯 **Phase 2 (Q1 2025)**
- [ ] DePIN inference network integration
- [ ] Multi-provider LLM routing
- [ ] Web search spike for knowledge augmentation
- [ ] Advanced patch pipeline & safety checks

### 🚀 **Phase 3 (Q2 2025)**
- [ ] SolCoder token (SCR) on-chain
- [ ] Staking & reward distribution
- [ ] Governance voting system

### 🌌 **Phase 4 (Q3 2025+)**
- [ ] Agentic contribution network
- [ ] On-chain reputation system
- [ ] Automated ecosystem improvement workflows

See `docs/roadmap/` for detailed milestones, tasks, and in-progress work.

---

## 📖 **Documentation**

- **[README](./README.md)** — This file; high-level overview
- **[CLAUDE.md](./CLAUDE.md)** — Architecture deep-dive for developers
- **[AGENTS.md](./AGENTS.md)** — Contributor guidelines & style standards
- **[PRD](./docs/PRD.md)** — Product requirements & vision
- **[WBS](./docs/WBS.md)** — Work breakdown structure
- **[Milestones](./docs/roadmap/milestones/)** — Detailed phase plans

---

## 🆘 **Support & Feedback**

- 💬 **[GitHub Discussions](https://github.com/solcoder/SolCoder/discussions)** — Ask questions, share ideas
- 🐛 **[GitHub Issues](https://github.com/solcoder/SolCoder/issues)** — Report bugs or suggest features
- 🔐 **Security** — For wallet or deployment issues, include CLI output (with secrets redacted)

## 📞 **Contact**

- 🐦 **X** — [@solcoderxyz](https://x.com/solcoderxyz)
- 📧 **Email** — [contact@solcoder.xyz](mailto:contact@solcoder.xyz)
- 💬 **Telegram** — [Join our community](https://t.me/+pNKuDgtZ0H9lM2U0)

---

## 📜 **License**

SolCoder is **open-source** under the [MIT License](./LICENSE). Use it freely, modify it, build on it.

---

## 🙏 **Acknowledgments**

Built with love by the SolCoder team and inspired by the Solana community. Special thanks to:
- **Anchor team** for the excellent Solana framework
- **Solana validators & DePIN pioneers** for infrastructure
- **Hackathon judges & mentors** for feedback & support
- **You**, for believing in the vision

---

<div align="center">

### ⚡ **Ready to Build?**

```bash
poetry run solcoder
```

**Transform your Solana ideas into deployed dApps at light speed.**

🚀 **SolCoder** — *Where AI meets blockchain.*

</div>

---

<div align="center">

**Made with ❤️ for the Solana ecosystem** | [Follow us](https://twitter.com/solcoder) | [Star ⭐ us on GitHub](https://github.com/solcoder/SolCoder)

</div>
