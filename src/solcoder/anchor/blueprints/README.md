# SolCoder Anchor Blueprints

This folder defines the registry and wizard schemas for Anchor-ready blueprints that `/new` and the agent can scaffold.

## Layout

```
src/solcoder/anchor/blueprints/
├── registry.json                  # List of available blueprints
├── <key>/
│   ├── wizard.json               # Per-blueprint wizard questions/validation
│   └── template/                 # Renderable files copied into target workspace
```

- Keep renderable project files (Anchor.toml, Cargo.toml, program stubs, tests, scripts) under `src/solcoder/anchor/blueprints/<key>/template`. The registry maps each blueprint key to its `template_path`.

## Registry Format (`registry.json`)

```jsonc
{
  "blueprints": [
    {
      "key": "token",                       // canonical key used by /new
      "name": "Simple Token",               // friendly name
      "description": "Token scaffold (stub)",
      "template_path": "src/solcoder/anchor/blueprints/token/template",   // where the renderer copies files from
      "tags": ["spl"],                       // optional tags for search/filtering
      "required_tools": ["anchor", "solana"] // runtime tools the user may need
    }
  ]
}
```

Guidelines:
- Keys are lowercase snake-case: `counter`, `token`, `nft`, `registry`, `escrow`.
- `template_path` can be relative to repo root or absolute; `/new` resolves it and passes it to the renderer.
- Use concise, practical descriptions. Tags should help grouping in UIs and LLM prompts.

## Wizard Schema (`<key>/wizard.json`)

```jsonc
{
  "questions": [
    { "key": "program_name", "prompt": "Program name", "default": "token", "pattern": "^[a-zA-Z0-9_-]+$" },
    { "key": "token_name",   "prompt": "Token name",   "default": "SolCoder Token" },
    { "key": "symbol",       "prompt": "Symbol",       "default": "SCT", "pattern": "^[A-Z0-9]{1,10}$" }
  ]
}
```

Guidelines:
- `key`: machine key of the answer; avoid spaces, use snake_case.
- `prompt`: short, user-facing question.
- `default`: string/number; if omitted, user must provide input.
- `pattern`: optional regex for simple validation; failing input falls back to default with a yellow warning.

## How /new Uses This
- Loads `registry.json` for available keys and maps `template_path` into the renderer.
- Loads `<key>/wizard.json` and prompts for answers (or uses defaults). Answers are persisted to:
  - `README.md` (human-readable)
  - `blueprint.answers.json` (machine-readable; used by sample scripts)
- If an Anchor workspace (Anchor.toml) is detected, the program is inserted under `programs/<name>` and Anchor.toml/Cargo.toml are patched. Otherwise, a full workspace is scaffolded at `--dir`.

## Adding a New Blueprint
1. Create the template under `src/solcoder/anchor/blueprints/<key>/template` (program stub, tests, scripts, README, Anchor.toml, Cargo.toml).
2. Add `src/solcoder/anchor/blueprints/<key>/wizard.json` with the minimal question set.
3. Register it in `src/solcoder/anchor/blueprints/registry.json` with an entry that points `template_path` to the template directory.
4. Run: `poetry run pytest -q` — add tests for `/new <key>` if needed.

## Best Practices
- Keep wizards minimal and focused on must-have configuration.
- Prefer safe defaults (devnet, placeholder PROGRAM_ID) and show clear next steps.
- Ensure generated projects build with `anchor build` once Anchor is installed.
- Keep Windows/macOS portability (no hard-failing chmods).

---

Questions? Open an issue or start a discussion in the repo.
