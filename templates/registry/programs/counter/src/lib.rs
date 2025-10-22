use anchor_lang::prelude::*;

declare_id!("{{PROGRAM_ID}}");

#[program]
pub mod {{PROGRAM_NAME_SNAKE}} {
    use super::*;

    pub fn upsert(ctx: Context<Upsert>, key: Vec<u8>, value: Vec<u8>) -> Result<()> {
        let record = &mut ctx.accounts.record;
        record.authority = ctx.accounts.authority.key();
        record.key = key;
        record.value = value;
        Ok(())
    }

    pub fn remove(_ctx: Context<Remove>) -> Result<()> {
        Ok(())
    }
}

#[account]
pub struct Record {
    pub authority: Pubkey,
    pub key: Vec<u8>,
    pub value: Vec<u8>,
}

impl Record {
    pub const MAX_KEY: usize = 64;
    pub const MAX_VALUE: usize = 256;
    pub const SIZE: usize = 32 + 4 + Self::MAX_KEY + 4 + Self::MAX_VALUE;
}

#[derive(Accounts)]
#[instruction(key: Vec<u8>)]
pub struct Upsert<'info> {
    #[account(
        init_if_needed,
        payer = authority,
        space = 8 + Record::SIZE,
        seeds = [b"registry", authority.key().as_ref(), key.as_ref()],
        bump
    )]
    pub record: Account<'info, Record>,
    #[account(mut)]
    pub authority: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
#[instruction(key: Vec<u8>)]
pub struct Remove<'info> {
    #[account(
        mut,
        close = authority,
        seeds = [b"registry", authority.key().as_ref(), key.as_ref()],
        bump
    )]
    pub record: Account<'info, Record>,
    #[account(mut)]
    pub authority: Signer<'info>,
}
