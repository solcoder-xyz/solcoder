import * as anchor from "@coral-xyz/anchor";
import { Program } from "@coral-xyz/anchor";
import { assert } from "chai";

describe("{{PROGRAM_NAME_SNAKE}}", () => {
  const provider = anchor.AnchorProvider.env();
  anchor.setProvider(provider);

  const program = anchor.workspace.{{PROGRAM_NAME_PASCAL}} as Program<any>;
  const counterKeypair = anchor.web3.Keypair.generate();

  it("initializes a counter", async () => {
    await program.methods
      .initialize()
      .accounts({
        counter: counterKeypair.publicKey,
        authority: provider.wallet.publicKey,
        systemProgram: anchor.web3.SystemProgram.programId,
      })
      .signers([counterKeypair])
      .rpc();

    const account = await program.account.counter.fetch(
      counterKeypair.publicKey,
    );
    assert.equal(account.count.toNumber(), 0);
    assert.equal(
      account.authority.toBase58(),
      provider.wallet.publicKey.toBase58(),
    );
  });

  it("increments and decrements the counter", async () => {
    await program.methods
      .increment(new anchor.BN(3))
      .accounts({
        counter: counterKeypair.publicKey,
        authority: provider.wallet.publicKey,
      })
      .rpc();

    await program.methods
      .decrement(new anchor.BN(2))
      .accounts({
        counter: counterKeypair.publicKey,
        authority: provider.wallet.publicKey,
      })
      .rpc();

    const account = await program.account.counter.fetch(
      counterKeypair.publicKey,
    );
    assert.equal(account.count.toNumber(), 1);
  });
});
