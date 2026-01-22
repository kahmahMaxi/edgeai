use anchor_lang::prelude::*;

#[error_code]
pub enum ErrorCode {
    #[msg("Unauthorized: Only admin can perform this action")]
    Unauthorized,
    #[msg("Invalid subscription duration")]
    InvalidSubscriptionDuration,
    #[msg("Subscription expired")]
    SubscriptionExpired,
    #[msg("Insufficient funds")]
    InsufficientFunds,
    #[msg("Invalid amount")]
    InvalidAmount,
    #[msg("Math overflow")]
    MathOverflow,
    #[msg("Staking vault not initialized")]
    StakingVaultNotInitialized,
    #[msg("Invalid token mint")]
    InvalidTokenMint,
}
