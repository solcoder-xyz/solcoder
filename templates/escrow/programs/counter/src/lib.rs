use anchor_lang::prelude::*;

declare_id!("{{PROGRAM_ID}}");

#[program]
pub mod {{PROGRAM_NAME_SNAKE}} {
    use super::*;

    pub fn init_escrow(_ctx: Context<InitEscrow>, _amount: u64) -> Result<()> {
        Ok(())
    }

    pub fn deposit(_ctx: Context<Deposit>) -> Result<()> {
        Ok(())
    }

    pub fn withdraw(_ctx: Context<Withdraw>) -> Result<()> {
        Ok(())
    }

    pub fn cancel(_ctx: Context<Cancel>) -> Result<()> {
        Ok(())
    }
}

#[derive(Accounts)]
pub struct InitEscrow {}

#[derive(Accounts)]
pub struct Deposit {}

#[derive(Accounts)]
pub struct Withdraw {}

#[derive(Accounts)]
pub struct Cancel {}
