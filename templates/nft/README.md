## {{PROGRAM_NAME_TITLE}} — NFT Blueprint (Stub)

This is a stubbed Anchor workspace for an NFT-related program. It includes a minimal program with an `initialize` instruction.

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

- Metadata & minting:
  Use Metaplex tooling (Umi or metaboss) to register metadata and mint NFTs.
  Example script `scripts/mint.ts` demonstrates reading `blueprint.answers.json` and printing a suggested Umi command.

- Interact using SolCoder:
  - `/program inspect <PROGRAM_ID>` to view instructions
