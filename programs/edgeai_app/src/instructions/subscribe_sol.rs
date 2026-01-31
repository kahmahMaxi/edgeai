use anchor_lang::prelude::*;
use crate::state::{Config, Subscription, PaymentMethod};
use crate::constants::{CONFIG_SEED, SUBSCRIPTION_SEED};
use crate::error::ErrorCode;

#[derive(Accounts)]
pub struct SubscribeSol<'info> {
    #[account(mut)]
    pub user: Signer<'info>,
    
    #[account(
        seeds = [CONFIG_SEED],
        bump = config.bump
    )]
    pub config: Account<'info, Config>,
    
    /// CHECK: Fee wallet
    #[account(mut)]
    pub fee_wallet: UncheckedAccount<'info>,
    
    #[account(
        init_if_needed,
        payer = user,
        space = Subscription::LEN,
        seeds = [SUBSCRIPTION_SEED, user.key().as_ref()],
        bump
    )]
    pub subscription: Account<'info, Subscription>,
    
    pub system_program: Program<'info, System>,
}

pub fn handler(ctx: Context<SubscribeSol>) -> Result<()> {
    let clock = Clock::get()?;
    let config = &ctx.accounts.config;

    // Re-init protection: if an active subscription already exists, reject.
    let existing = &ctx.accounts.subscription;
    if existing.expires_at != 0 && existing.is_active(clock.unix_timestamp) {
        return Err(ErrorCode::SubscriptionAlreadyActive.into());
    }
    
    let required_lamports = config.subscription_price_sol;
    
    // Verify user has enough SOL (account for rent exemption)
    let user_balance = ctx.accounts.user.lamports();
    let subscription_rent = ctx.accounts.subscription.to_account_info().lamports();
    let total_required = required_lamports
        .checked_add(subscription_rent)
        .ok_or(ErrorCode::MathOverflow)?;
    
    require!(
        user_balance >= total_required,
        ErrorCode::InsufficientFunds
    );
    
    // Transfer SOL to fee wallet
    anchor_lang::solana_program::program::invoke(
        &anchor_lang::solana_program::system_instruction::transfer(
            &ctx.accounts.user.key(),
            &ctx.accounts.fee_wallet.key(),
            required_lamports,
        ),
        &[
            ctx.accounts.user.to_account_info(),
            ctx.accounts.fee_wallet.to_account_info(),
            ctx.accounts.system_program.to_account_info(),
        ],
    )?;
    
    // Calculate expiration
    let expires_at = clock
        .unix_timestamp
        .checked_add(config.subscription_duration)
        .ok_or(ErrorCode::MathOverflow)?;
    
    // Update subscription
    let subscription = &mut ctx.accounts.subscription;
    subscription.user = ctx.accounts.user.key();
    subscription.expires_at = expires_at;
    subscription.payment_method = PaymentMethod::Sol;
    subscription.bump = ctx.bumps.subscription;
    
    msg!(
        "Subscription created for user: {}, expires at: {}",
        subscription.user,
        subscription.expires_at
    );
    
    Ok(())
}
