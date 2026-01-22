use anchor_lang::prelude::*;
use anchor_spl::token::{Token, TokenAccount, Transfer};
use crate::state::{Config, StakingVault, UserStake};
use crate::constants::{CONFIG_SEED, STAKING_VAULT_SEED};
use crate::error::ErrorCode;

#[derive(Accounts)]
pub struct Unstake<'info> {
    #[account(mut)]
    pub user: Signer<'info>,
    
    #[account(
        seeds = [CONFIG_SEED],
        bump = config.bump
    )]
    pub config: Account<'info, Config>,
    
    #[account(
        mut,
        constraint = user_token_account.owner == user.key() @ ErrorCode::Unauthorized,
        constraint = user_token_account.mint == config.token_mint @ ErrorCode::InvalidTokenMint
    )]
    pub user_token_account: Account<'info, TokenAccount>,
    
    #[account(
        mut,
        seeds = [STAKING_VAULT_SEED],
        bump = staking_vault.bump
    )]
    pub staking_vault: Account<'info, StakingVault>,
    
    /// CHECK: Staking vault token account
    #[account(mut)]
    pub staking_vault_token_account: UncheckedAccount<'info>,
    
    #[account(
        mut,
        seeds = [STAKING_VAULT_SEED, user.key().as_ref()],
        bump = user_stake.bump,
        has_one = user @ ErrorCode::Unauthorized
    )]
    pub user_stake: Account<'info, UserStake>,
    
    pub token_program: Program<'info, Token>,
}

pub fn handler(ctx: Context<Unstake>, amount: u64) -> Result<()> {
    require!(amount > 0, ErrorCode::InvalidAmount);
    
    let user_stake = &mut ctx.accounts.user_stake;
    
    // Verify user has enough staked
    require!(
        user_stake.amount >= amount,
        ErrorCode::InsufficientFunds
    );
    
    // Transfer tokens back to user
    let seeds = &[
        STAKING_VAULT_SEED,
        &[ctx.accounts.staking_vault.bump],
    ];
    let signer = &[&seeds[..]];
    
    let cpi_accounts = Transfer {
        from: ctx.accounts.staking_vault_token_account.to_account_info(),
        to: ctx.accounts.user_token_account.to_account_info(),
        authority: ctx.accounts.staking_vault.to_account_info(),
    };
    
    let cpi_program = ctx.accounts.token_program.to_account_info();
    let cpi_ctx = CpiContext::new_with_signer(cpi_program, cpi_accounts, signer);
    
    anchor_spl::token::transfer(cpi_ctx, amount)?;
    
    // Update staking vault
    let staking_vault = &mut ctx.accounts.staking_vault;
    staking_vault.total_staked = staking_vault
        .total_staked
        .checked_sub(amount)
        .ok_or(ErrorCode::MathOverflow)?;
    
    // Update user stake
    user_stake.amount = user_stake
        .amount
        .checked_sub(amount)
        .ok_or(ErrorCode::MathOverflow)?;
    
    msg!(
        "User {} unstaked {} tokens. Remaining staked: {}",
        user_stake.user,
        amount,
        user_stake.amount
    );
    
    Ok(())
}
