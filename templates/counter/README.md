# {{PROGRAM_NAME_TITLE}} Counter Template

This template scaffolds a simple Anchor program that tracks a signed integer counter controlled by an authority.

## Features

- Instructions to initialize, increment, and decrement the counter.
- Authority checks enforced on every update.
- Anchor TypeScript test that exercises the full flow.
- Configured for the `{{CLUSTER}}` cluster with placeholder program ID `{{PROGRAM_ID}}`.

## Usage

1. Ensure the Solana CLI, Anchor, Rust, and Node.js toolchains are installed (`/env diag` reports their status).
2. Render the template with SolCoder:

   ```bash
   poetry run solcoder --template counter ./my-counter --program my_counter --author {{AUTHOR_PUBKEY}}
   ```

   Or inside the REPL: `/template counter ./my-counter --program my_counter --author {{AUTHOR_PUBKEY}}`

3. Change into the new workspace and install dependencies:

   ```bash
   cd my-counter
   npm install
   ```

4. Build the program:

   ```bash
   anchor build
   ```

5. Verify configuration (inside SolCoder):

   ```
   /deploy verify
   ```
   This checks toolchain, wallet, cluster, and Program ID consistency (declare_id! and Anchor.toml mapping).

6. Deploy the program:

   ```bash
   anchor deploy
   ```
   If you haven’t set a real Program ID yet, generate one and update both declare_id! and Anchor.toml’s `[programs.{{CLUSTER}}]` mapping. Task 2.4 adapters will automate this.

7. Run the included test suite with `anchor test` to verify behavior.

## Account Layout

| Field      | Type    | Description                              |
| ---------- | ------- | ---------------------------------------- |
| authority  | Pubkey  | The wallet authorized to update counter. |
| count      | i64     | Signed integer value of the counter.     |

## Client Stub

Use the generated `client/counter.ts` script as a starting point for interacting with the program from TypeScript.

## Next Steps
- Inspect on-chain IDL and instructions:
  - `/program inspect <PROGRAM_ID>`
- Try the sample script after deploying and setting the correct IDL:
  - `node client/counter.ts`
