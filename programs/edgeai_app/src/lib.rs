pub mod constants;
pub mod error;
pub mod instructions;
pub mod state;

use anchor_lang::prelude::*;

pub use constants::*;
pub use instructions::*;
pub use state::*;

declare_id!("JG8fS89RdsLUGUst41UTj8kFFEjBxQKV6yzPaBmAEwL");

#[program]
pub mod edgeai_app {
    use super::*;

    /// Initialize the config PDA with admin settings
    pub fn initialize_config(
        ctx: Context<InitializeConfig>,
        subscription_price_sol: u64,
        subscription_price_usdc: u64,
        subscription_duration: i64,
        staking_fee_share_bps: u16,
    ) -> Result<()> {
        instructions::initialize_config::handler(
            ctx,
            subscription_price_sol,
            subscription_price_usdc,
            subscription_duration,
            staking_fee_share_bps,
        )
    }

    /// Create the $EDGEAI token mint
    pub fn create_token_mint(ctx: Context<CreateTokenMint>) -> Result<()> {
        instructions::create_token_mint::handler(ctx)
    }

    /// Subscribe with SOL payment
    pub fn subscribe_sol(ctx: Context<SubscribeSol>) -> Result<()> {
        instructions::subscribe_sol::handler(ctx)
    }

    /// Subscribe with USDC payment
    pub fn subscribe_usdc(ctx: Context<SubscribeUsdc>) -> Result<()> {
        instructions::subscribe_usdc::handler(ctx)
    }

    /// Stake $EDGEAI tokens
    pub fn stake(ctx: Context<Stake>, amount: u64) -> Result<()> {
        instructions::stake::handler(ctx, amount)
    }

    /// Unstake $EDGEAI tokens
    pub fn unstake(ctx: Context<Unstake>, amount: u64) -> Result<()> {
        instructions::unstake::handler(ctx, amount)
    }

    /// Update config (admin only)
    pub fn update_config(
        ctx: Context<UpdateConfig>,
        subscription_price_sol: Option<u64>,
        subscription_price_usdc: Option<u64>,
        subscription_duration: Option<i64>,
        staking_fee_share_bps: Option<u16>,
        fee_wallet: Option<Pubkey>,
    ) -> Result<()> {
        instructions::update_config::handler(
            ctx,
            subscription_price_sol,
            subscription_price_usdc,
            subscription_duration,
            staking_fee_share_bps,
            fee_wallet,
        )
    }

    /// Distribute fees to stakers (admin only)
    pub fn distribute_fees(ctx: Context<DistributeFees>, amount: u64) -> Result<()> {
        instructions::distribute_fees::handler(ctx, amount)
    }
}
