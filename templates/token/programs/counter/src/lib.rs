use anchor_lang::prelude::*;

declare_id!("{{PROGRAM_ID}}");

#[program]
pub mod {{PROGRAM_NAME_SNAKE}} {
    use super::*;

    pub fn initialize(_ctx: Context<Initialize>) -> Result<()> {
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Initialize {}

