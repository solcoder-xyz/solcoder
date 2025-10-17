import * as anchor from "@coral-xyz/anchor";

export async function runDemo(programId: string, authority: anchor.web3.Keypair) {
  const provider = anchor.AnchorProvider.env();
  anchor.setProvider(provider);

  const idl = await anchor.Program.fetchIdl(programId, provider);
  if (!idl) {
    throw new Error(`Unable to fetch IDL for ${programId}. Build the IDL first with \`anchor build\`.`);
  }

  const program = new anchor.Program(idl, programId, provider);
  const counterKeypair = anchor.web3.Keypair.generate();

  await program.methods
    .initialize()
    .accounts({
      counter: counterKeypair.publicKey,
      authority: authority.publicKey,
      systemProgram: anchor.web3.SystemProgram.programId,
    })
    .signers([authority, counterKeypair])
    .rpc();

  await program.methods
    .increment(new anchor.BN(1))
    .accounts({
      counter: counterKeypair.publicKey,
      authority: authority.publicKey,
    })
    .signers([authority])
    .rpc();

  const account = await program.account.counter.fetch(counterKeypair.publicKey);
  console.log("Counter value", account.count.toNumber());
}
