use anchor_lang::prelude::*;

declare_id!("replace-with-program-id");

#[program]
pub mod nft {
    use super::*;

    pub fn initialize(_ctx: Context<Initialize>) -> Result<()> {
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Initialize {}

