use anchor_lang::prelude::*;
use anchor_spl::token::{Token, TokenAccount, Transfer};
use crate::state::{Config, Subscription, PaymentMethod};
use crate::constants::{CONFIG_SEED, SUBSCRIPTION_SEED};
use crate::error::ErrorCode;

#[derive(Accounts)]
pub struct SubscribeUsdc<'info> {
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
        constraint = user_token_account.amount >= config.subscription_price_usdc @ ErrorCode::InsufficientFunds
    )]
    pub user_token_account: Account<'info, TokenAccount>,
    
    /// CHECK: Fee wallet token account
    #[account(mut)]
    pub fee_wallet_token_account: UncheckedAccount<'info>,
    
    #[account(
        init_if_needed,
        payer = user,
        space = Subscription::LEN,
        seeds = [SUBSCRIPTION_SEED, user.key().as_ref()],
        bump
    )]
    pub subscription: Account<'info, Subscription>,
    
    pub token_program: Program<'info, Token>,
    pub system_program: Program<'info, System>,
}

pub fn handler(ctx: Context<SubscribeUsdc>) -> Result<()> {
    let clock = Clock::get()?;
    let config = &ctx.accounts.config;
    
    // Transfer USDC to fee wallet
    let cpi_accounts = Transfer {
        from: ctx.accounts.user_token_account.to_account_info(),
        to: ctx.accounts.fee_wallet_token_account.to_account_info(),
        authority: ctx.accounts.user.to_account_info(),
    };
    
    let cpi_program = ctx.accounts.token_program.to_account_info();
    let cpi_ctx = CpiContext::new(cpi_program, cpi_accounts);
    
    anchor_spl::token::transfer(cpi_ctx, config.subscription_price_usdc)?;
    
    // Calculate expiration
    let expires_at = clock
        .unix_timestamp
        .checked_add(config.subscription_duration)
        .ok_or(ErrorCode::MathOverflow)?;
    
    // Update subscription
    let subscription = &mut ctx.accounts.subscription;
    subscription.user = ctx.accounts.user.key();
    subscription.expires_at = expires_at;
    subscription.payment_method = PaymentMethod::Usdc;
    subscription.bump = ctx.bumps.subscription;
    
    msg!(
        "USDC subscription created for user: {}, expires at: {}",
        subscription.user,
        subscription.expires_at
    );
    
    Ok(())
}
