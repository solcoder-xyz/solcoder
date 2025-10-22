## {{PROGRAM_NAME_TITLE}} — Registry Blueprint (Stub)

This is a stubbed Anchor workspace for a PDA registry program.

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
  - Extend `programs/{{PROGRAM_NAME_SNAKE}}/src/lib.rs` to add PDA set/get instructions.
