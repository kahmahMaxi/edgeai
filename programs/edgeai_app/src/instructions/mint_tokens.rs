use anchor_lang::prelude::*;
use anchor_spl::token::{Mint, Token, TokenAccount, MintTo};
use crate::state::Config;
use crate::constants::CONFIG_SEED;
use crate::error::ErrorCode;

#[derive(Accounts)]
pub struct MintTokens<'info> {
    #[account(mut)]
    pub admin: Signer<'info>,
    
    #[account(
        seeds = [CONFIG_SEED],
        bump = config.bump,
        has_one = admin @ ErrorCode::Unauthorized
    )]
    pub config: Account<'info, Config>,
    
    #[account(
        mut,
        address = config.token_mint @ ErrorCode::InvalidTokenMint
    )]
    pub token_mint: Account<'info, Mint>,
    
    #[account(mut)]
    pub destination: Account<'info, TokenAccount>,
    
    pub token_program: Program<'info, Token>,
}

pub fn handler(ctx: Context<MintTokens>, amount: u64) -> Result<()> {
    require!(amount > 0, ErrorCode::InvalidAmount);
    
    // Mint tokens using config PDA as authority
    let seeds = &[
        CONFIG_SEED,
        &[ctx.accounts.config.bump],
    ];
    let signer = &[&seeds[..]];
    
    let cpi_accounts = MintTo {
        mint: ctx.accounts.token_mint.to_account_info(),
        to: ctx.accounts.destination.to_account_info(),
        authority: ctx.accounts.config.to_account_info(),
    };
    
    let cpi_program = ctx.accounts.token_program.to_account_info();
    let cpi_ctx = CpiContext::new_with_signer(cpi_program, cpi_accounts, signer);
    
    anchor_spl::token::mint_to(cpi_ctx, amount)?;
    
    msg!("Minted {} tokens to {}", amount, ctx.accounts.destination.key());
    Ok(())
}
