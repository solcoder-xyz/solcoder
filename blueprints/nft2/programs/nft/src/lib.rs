use anchor_lang::prelude::*;

declare_id!("DFvzyv1onfttLVHT9DFXDPK1ckamcr7UgpxhhSCMP9ia");

#[program]
pub mod nft {
    use super::*;

    pub fn initialize(_ctx: Context<Initialize>) -> Result<()> {
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Initialize {}

