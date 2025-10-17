use anchor_lang::prelude::*;

declare_id!("{{PROGRAM_ID}}");

#[program]
pub mod {{PROGRAM_NAME_SNAKE}} {
    use super::*;

    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
        let counter = &mut ctx.accounts.counter;
        counter.authority = ctx.accounts.authority.key();
        counter.count = 0;
        Ok(())
    }

    pub fn increment(ctx: Context<UpdateCounter>, amount: i64) -> Result<()> {
        let counter = &mut ctx.accounts.counter;
        require_keys_eq!(
            counter.authority,
            ctx.accounts.authority.key(),
            CounterError::Unauthorized
        );
        counter.count = counter
            .count
            .checked_add(amount)
            .ok_or(CounterError::Overflow)?;
        Ok(())
    }

    pub fn decrement(ctx: Context<UpdateCounter>, amount: i64) -> Result<()> {
        let counter = &mut ctx.accounts.counter;
        require_keys_eq!(
            counter.authority,
            ctx.accounts.authority.key(),
            CounterError::Unauthorized
        );
        counter.count = counter
            .count
            .checked_sub(amount)
            .ok_or(CounterError::Overflow)?;
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(init, payer = authority, space = 8 + Counter::SIZE)]
    pub counter: Account<'info, Counter>,
    #[account(mut)]
    pub authority: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct UpdateCounter<'info> {
    #[account(mut)]
    pub counter: Account<'info, Counter>,
    pub authority: Signer<'info>,
}

#[account]
pub struct Counter {
    pub authority: Pubkey,
    pub count: i64,
}

impl Counter {
    pub const SIZE: usize = 32 + 8;
}

#[error_code]
pub enum CounterError {
    #[msg("Only the authority who initialized the counter can update it.")]
    Unauthorized,
    #[msg("Counter overflow or underflow encountered.")]
    Overflow,
}
