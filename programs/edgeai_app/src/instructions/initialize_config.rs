use anchor_lang::prelude::*;
use crate::state::Config;
use crate::constants::CONFIG_SEED;
use crate::error::ErrorCode;

#[derive(Accounts)]
pub struct InitializeConfig<'info> {
    #[account(mut)]
    pub admin: Signer<'info>,
    
    /// CHECK: Fee wallet, validated by admin
    pub fee_wallet: UncheckedAccount<'info>,
    
    #[account(
        init,
        payer = admin,
        space = Config::LEN,
        seeds = [CONFIG_SEED],
        bump
    )]
    pub config: Account<'info, Config>,
    
    pub system_program: Program<'info, System>,
}

pub fn handler(
    ctx: Context<InitializeConfig>,
    subscription_price_sol: u64,
    subscription_price_usdc: u64,
    subscription_duration: i64,
    staking_fee_share_bps: u16,
) -> Result<()> {
    require!(
        subscription_duration > 0,
        ErrorCode::InvalidSubscriptionDuration
    );
    require!(
        staking_fee_share_bps <= 10000,
        ErrorCode::InvalidAmount
    );

    let config = &mut ctx.accounts.config;
    config.admin = ctx.accounts.admin.key();
    config.fee_wallet = ctx.accounts.fee_wallet.key();
    config.token_mint = Pubkey::default(); // Will be set when mint is created
    config.subscription_price_sol = subscription_price_sol;
    config.subscription_price_usdc = subscription_price_usdc;
    config.subscription_duration = subscription_duration;
    config.staking_fee_share_bps = staking_fee_share_bps;
    config.bump = ctx.bumps.config;

    msg!("Config initialized by admin: {}", config.admin);
    Ok(())
}
