## Nft — NFT Blueprint (Stub)

This is a stubbed Anchor workspace for an NFT-related program. It includes a minimal program with an `initialize` instruction.

- Program name: `nft`
- Cluster: `devnet`
- Program ID (placeholder): `replace-with-program-id`

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
  Ensure `declare_id!` and `Anchor.toml [programs.devnet]` are set to your program’s public key.

- Metadata & minting:
  Use Metaplex tooling (e.g., Umi or metaboss) to register metadata and mint NFTs for real use. See `scripts/mint.ts` for reading `blueprint.answers.json`.

- Interact using SolCoder:
  - `/program inspect <PROGRAM_ID>` to view instructions


### Wizard Answers


- name: nft2
