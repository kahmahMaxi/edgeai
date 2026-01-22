use anchor_lang::prelude::*;
use crate::state::Config;
use crate::constants::CONFIG_SEED;
use crate::error::ErrorCode;

#[derive(Accounts)]
pub struct UpdateConfig<'info> {
    #[account(mut)]
    pub admin: Signer<'info>,
    
    #[account(
        mut,
        seeds = [CONFIG_SEED],
        bump = config.bump,
        has_one = admin @ ErrorCode::Unauthorized
    )]
    pub config: Account<'info, Config>,
}

pub fn handler(
    ctx: Context<UpdateConfig>,
    subscription_price_sol: Option<u64>,
    subscription_price_usdc: Option<u64>,
    subscription_duration: Option<i64>,
    staking_fee_share_bps: Option<u16>,
    fee_wallet: Option<Pubkey>,
) -> Result<()> {
    let config = &mut ctx.accounts.config;
    
    if let Some(price_sol) = subscription_price_sol {
        config.subscription_price_sol = price_sol;
    }
    
    if let Some(price_usdc) = subscription_price_usdc {
        config.subscription_price_usdc = price_usdc;
    }
    
    if let Some(duration) = subscription_duration {
        require!(
            duration > 0,
            ErrorCode::InvalidSubscriptionDuration
        );
        config.subscription_duration = duration;
    }
    
    if let Some(fee_share) = staking_fee_share_bps {
        require!(
            fee_share <= 10000,
            ErrorCode::InvalidAmount
        );
        config.staking_fee_share_bps = fee_share;
    }
    
    if let Some(new_fee_wallet) = fee_wallet {
        config.fee_wallet = new_fee_wallet;
    }
    
    msg!("Config updated by admin: {}", config.admin);
    Ok(())
}
