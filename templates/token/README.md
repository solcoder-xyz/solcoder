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

- Scripted flows (Token-2022)
  This blueprint includes example scripts that demonstrate common SPL Token flows using the CLI:

  - Create mint (Token-2022) and wallet ATA
  - Mint to your ATA
  - Transfer between ATAs

  See `scripts/mint.ts` and `scripts/transfer.ts`. You can run them on devnet after configuring your wallet:

  ```bash
  # Ensure Solana/Anchor CLIs and spl-token are installed
  solana config set -u devnet
  node scripts/mint.ts
  node scripts/transfer.ts
  ```

  If you only need a one-off mint without custom logic, you can also use SolCoder's quick flow:
  ```
  /new token --quick --decimals 0 --supply 1000000 --cluster devnet
  ```

- Interact using SolCoder:
  - `/program inspect <PROGRAM_ID>` to view instructions
