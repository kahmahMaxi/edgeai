use anchor_lang::prelude::*;
use anchor_spl::token::{Token, TokenAccount, Transfer};
use crate::state::{Config, StakingVault, UserStake};
use crate::constants::{CONFIG_SEED, STAKING_VAULT_SEED};
use crate::error::ErrorCode;

#[derive(Accounts)]
pub struct Stake<'info> {
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
        init_if_needed,
        payer = user,
        space = StakingVault::LEN,
        seeds = [STAKING_VAULT_SEED],
        bump
    )]
    pub staking_vault: Account<'info, StakingVault>,
    
    /// CHECK: Staking vault token account
    #[account(mut)]
    pub staking_vault_token_account: UncheckedAccount<'info>,
    
    #[account(
        init_if_needed,
        payer = user,
        space = UserStake::LEN,
        seeds = [STAKING_VAULT_SEED, user.key().as_ref()],
        bump
    )]
    pub user_stake: Account<'info, UserStake>,
    
    pub token_program: Program<'info, Token>,
    pub system_program: Program<'info, System>,
}

pub fn handler(ctx: Context<Stake>, amount: u64) -> Result<()> {
    require!(amount > 0, ErrorCode::InvalidAmount);
    
    let clock = Clock::get()?;
    let config = &ctx.accounts.config;
    
    // Verify user has enough tokens
    require!(
        ctx.accounts.user_token_account.amount >= amount,
        ErrorCode::InsufficientFunds
    );
    
    // Transfer tokens to staking vault (user is the authority)
    let cpi_accounts = Transfer {
        from: ctx.accounts.user_token_account.to_account_info(),
        to: ctx.accounts.staking_vault_token_account.to_account_info(),
        authority: ctx.accounts.user.to_account_info(),
    };
    
    let cpi_program = ctx.accounts.token_program.to_account_info();
    let cpi_ctx = CpiContext::new(cpi_program, cpi_accounts);
    
    anchor_spl::token::transfer(cpi_ctx, amount)?;
    
    // Update staking vault
    let staking_vault = &mut ctx.accounts.staking_vault;
    staking_vault.total_staked = staking_vault
        .total_staked
        .checked_add(amount)
        .ok_or(ErrorCode::MathOverflow)?;
    staking_vault.bump = ctx.bumps.staking_vault;
    
    // Update user stake
    let user_stake = &mut ctx.accounts.user_stake;
    user_stake.user = ctx.accounts.user.key();
    user_stake.amount = user_stake
        .amount
        .checked_add(amount)
        .ok_or(ErrorCode::MathOverflow)?;
    user_stake.staked_at = clock.unix_timestamp;
    user_stake.bump = ctx.bumps.user_stake;
    
    msg!(
        "User {} staked {} tokens. Total staked: {}",
        user_stake.user,
        amount,
        staking_vault.total_staked
    );
    
    Ok(())
}
