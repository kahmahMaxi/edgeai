use anchor_lang::prelude::*;
use anchor_spl::token::{Mint, Token, TokenAccount};
use anchor_spl::token::spl_token::instruction::AuthorityType;
use crate::state::Config;
use crate::constants::{CONFIG_SEED, TOKEN_MINT_SEED, TOKEN_DECIMALS};
use crate::error::ErrorCode;

#[derive(Accounts)]
pub struct CreateTokenMint<'info> {
    #[account(mut)]
    pub admin: Signer<'info>,
    
    #[account(
        seeds = [CONFIG_SEED],
        bump = config.bump,
        has_one = admin @ ErrorCode::Unauthorized
    )]
    pub config: Account<'info, Config>,
    
    #[account(
        init,
        payer = admin,
        mint::decimals = TOKEN_DECIMALS,
        mint::authority = config,
        seeds = [TOKEN_MINT_SEED],
        bump
    )]
    pub token_mint: Account<'info, Mint>,
    
    pub token_program: Program<'info, Token>,
    pub system_program: Program<'info, System>,
    pub rent: Sysvar<'info, Rent>,
}

pub fn handler(ctx: Context<CreateTokenMint>) -> Result<()> {
    let config = &mut ctx.accounts.config;
    config.token_mint = ctx.accounts.token_mint.key();
    
    msg!("Token mint created: {}", ctx.accounts.token_mint.key());
    Ok(())
}
