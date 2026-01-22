use anchor_lang::prelude::*;
use anchor_spl::token::TokenAccount;

#[account]
pub struct Config {
    pub admin: Pubkey,
    pub fee_wallet: Pubkey,
    pub token_mint: Pubkey,
    pub subscription_price_sol: u64,        // Price in lamports
    pub subscription_price_usdc: u64,       // Price in USDC (6 decimals)
    pub subscription_duration: i64,         // Duration in seconds
    pub staking_fee_share_bps: u16,         // Fee share for stakers in basis points (10000 = 100%)
    pub bump: u8,
}

impl Config {
    pub const LEN: usize = 8 + // discriminator
        32 + // admin
        32 + // fee_wallet
        32 + // token_mint
        8 +  // subscription_price_sol
        8 +  // subscription_price_usdc
        8 +  // subscription_duration
        2 +  // staking_fee_share_bps
        1;   // bump
}

#[account]
pub struct Subscription {
    pub user: Pubkey,
    pub expires_at: i64,                    // Unix timestamp
    pub payment_method: PaymentMethod,      // SOL or USDC
    pub bump: u8,
}

#[derive(AnchorSerialize, AnchorDeserialize, Clone, Copy, PartialEq)]
pub enum PaymentMethod {
    Sol,
    Usdc,
}

impl Subscription {
    pub const LEN: usize = 8 + // discriminator
        32 + // user
        8 +  // expires_at
        1 +  // payment_method
        1;   // bump

    pub fn is_active(&self, current_timestamp: i64) -> bool {
        current_timestamp < self.expires_at
    }
}

#[account]
pub struct StakingVault {
    pub total_staked: u64,                  // Total tokens staked
    pub total_rewards_distributed: u64,     // Total rewards distributed
    pub last_distribution: i64,             // Last distribution timestamp
    pub bump: u8,
}

impl StakingVault {
    pub const LEN: usize = 8 + // discriminator
        8 + // total_staked
        8 + // total_rewards_distributed
        8 + // last_distribution
        1;  // bump
}

#[account]
pub struct UserStake {
    pub user: Pubkey,
    pub amount: u64,                        // Staked amount
    pub staked_at: i64,                     // Timestamp when staked
    pub bump: u8,
}

impl UserStake {
    pub const LEN: usize = 8 + // discriminator
        32 + // user
        8 +  // amount
        8 +  // staked_at
        1;   // bump
}
