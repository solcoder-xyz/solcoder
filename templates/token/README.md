## {{PROGRAM_NAME_TITLE}} — Token Blueprint (Stub)

This is a stubbed Anchor workspace for a token-related program. It includes a minimal program with an `initialize` instruction.

- Program name: `{{PROGRAM_NAME_SNAKE}}`
- Cluster: `{{CLUSTER}}`
- Program ID (placeholder): `{{PROGRAM_ID}}`

### Next Steps
- Build with Anchor:
  ```bash
  anchor build
  ```
- Verify (inside SolCoder):
  ```
  /deploy verify
  ```
  Checks toolchain, wallet, cluster, and Program ID consistency.

- Deploy (Anchor):
  ```bash
  anchor deploy
  ```
  Ensure `declare_id!` and `Anchor.toml [programs.{{CLUSTER}}]` are set to your program’s public key.

- Quick path (no custom program):
  If you only need an SPL token mint without custom logic, use the Solana `spl-token` CLI directly:
  ```
  spl-token create-token
  spl-token create-account <MINT>
  spl-token mint <MINT> 1000000
  ```

- Interact using SolCoder:
  - `/program inspect <PROGRAM_ID>` to view instructions
