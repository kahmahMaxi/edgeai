use anchor_lang::prelude::*;
use anchor_spl::token::{Token, Transfer};
use crate::state::{Config, StakingVault};
use crate::constants::{CONFIG_SEED, STAKING_VAULT_SEED};
use crate::error::ErrorCode;

#[derive(Accounts)]
pub struct DistributeFees<'info> {
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
        seeds = [STAKING_VAULT_SEED],
        bump = staking_vault.bump
    )]
    pub staking_vault: Account<'info, StakingVault>,
    
    /// CHECK: Fee wallet token account (USDC or EDGEAI)
    #[account(mut)]
    pub fee_wallet_token_account: UncheckedAccount<'info>,
    
    /// CHECK: Staking vault token account for rewards
    #[account(mut)]
    pub staking_vault_token_account: UncheckedAccount<'info>,
    
    pub token_program: Program<'info, Token>,
}

pub fn handler(ctx: Context<DistributeFees>, amount: u64) -> Result<()> {
    require!(amount > 0, ErrorCode::InvalidAmount);
    require!(
        ctx.accounts.staking_vault.total_staked > 0,
        ErrorCode::StakingVaultNotInitialized
    );
    
    // Calculate fee share for stakers
    let fee_share = (amount as u128)
        .checked_mul(ctx.accounts.config.staking_fee_share_bps as u128)
        .ok_or(ErrorCode::MathOverflow)?
        .checked_div(10000)
        .ok_or(ErrorCode::MathOverflow)? as u64;
    
    // Transfer fee share to staking vault
    let cpi_accounts = Transfer {
        from: ctx.accounts.fee_wallet_token_account.to_account_info(),
        to: ctx.accounts.staking_vault_token_account.to_account_info(),
        authority: ctx.accounts.admin.to_account_info(),
    };
    
    let cpi_program = ctx.accounts.token_program.to_account_info();
    let cpi_ctx = CpiContext::new(cpi_program, cpi_accounts);
    
    anchor_spl::token::transfer(cpi_ctx, fee_share)?;
    
    // Update staking vault
    let staking_vault = &mut ctx.accounts.staking_vault;
    staking_vault.total_rewards_distributed = staking_vault
        .total_rewards_distributed
        .checked_add(fee_share)
        .ok_or(ErrorCode::MathOverflow)?;
    
    let clock = Clock::get()?;
    staking_vault.last_distribution = clock.unix_timestamp;
    
    msg!(
        "Distributed {} tokens to staking vault. Total rewards: {}",
        fee_share,
        staking_vault.total_rewards_distributed
    );
    
    Ok(())
}
