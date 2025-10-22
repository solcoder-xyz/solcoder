## {{PROGRAM_NAME_TITLE}} — Escrow Blueprint (Stub)

This is a stubbed Anchor workspace for a basic escrow program.

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

- Interact using SolCoder:
  - `/program inspect <PROGRAM_ID>` to view instructions
  - See `scripts/escrow_demo.ts` for reading `blueprint.answers.json` and sketching flows.
