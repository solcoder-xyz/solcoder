import * as anchor from "@coral-xyz/anchor";

describe("Nft", () => {
  it("builds", async () => {
    const provider = anchor.AnchorProvider.local();
    anchor.setProvider(provider);
  });
});

