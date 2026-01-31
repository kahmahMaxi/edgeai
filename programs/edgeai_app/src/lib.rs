pub mod constants;
pub mod error;
pub mod state;

use anchor_lang::prelude::*;
use anchor_spl::token::{Mint, Token, TokenAccount, Transfer, MintTo};

pub use constants::*;
pub use error::ErrorCode;
pub use state::*;

// declare_id!("JG8fS89RdsLUGUst41UTj8kFFEjBxQKV6yzPaBmAEwL");
declare_id!("2ZfXnm4EnjBfqZtvTao8gdoEb6cp1yMvfppUEVY5svxQ");

// ============================================================================
// Instruction Accounts Structs
// ============================================================================

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

#[derive(Accounts)]
pub struct CreateTokenMint<'info> {
    #[account(mut)]
    pub admin: Signer<'info>,
    
    #[account(
        mut,
        seeds = [CONFIG_SEED],
        bump = config.bump,
        has_one = admin @ ErrorCode::Unauthorized
    )]
    pub config: Account<'info, Config>,
    
    #[account(
        init,
        payer = admin,
        mint::decimals = TOKEN_DECIMALS,
        mint::authority = config,
        seeds = [TOKEN_MINT_SEED],
        bump
    )]
    pub token_mint: Account<'info, Mint>,
    
    pub token_program: Program<'info, Token>,
    pub system_program: Program<'info, System>,
    pub rent: Sysvar<'info, Rent>,
}

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

#[derive(Accounts)]
pub struct MintTokens<'info> {
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
        address = config.token_mint @ ErrorCode::InvalidTokenMint
    )]
    pub token_mint: Account<'info, Mint>,
    
    #[account(mut)]
    pub destination: Account<'info, TokenAccount>,
    
    pub token_program: Program<'info, Token>,
}

// ============================================================================
// Handler Functions
// ============================================================================

fn initialize_config_handler(
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

fn create_token_mint_handler(ctx: Context<CreateTokenMint>) -> Result<()> {
    let config = &mut ctx.accounts.config;
    config.token_mint = ctx.accounts.token_mint.key();
    
    msg!("Token mint created: {}", ctx.accounts.token_mint.key());
    Ok(())
}

fn subscribe_sol_handler(ctx: Context<SubscribeSol>) -> Result<()> {
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

fn subscribe_usdc_handler(ctx: Context<SubscribeUsdc>) -> Result<()> {
    let clock = Clock::get()?;
    let config = &ctx.accounts.config;
    
    // Re-init protection: if an active subscription already exists, reject.
    let existing = &ctx.accounts.subscription;
    if existing.expires_at != 0 && existing.is_active(clock.unix_timestamp) {
        return Err(ErrorCode::SubscriptionAlreadyActive.into());
    }
    
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

fn stake_handler(ctx: Context<Stake>, amount: u64) -> Result<()> {
    require!(amount > 0, ErrorCode::InvalidAmount);
    
    let clock = Clock::get()?;
    
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

fn unstake_handler(ctx: Context<Unstake>, amount: u64) -> Result<()> {
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

fn update_config_handler(
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

fn distribute_fees_handler(ctx: Context<DistributeFees>, amount: u64) -> Result<()> {
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

fn mint_tokens_handler(ctx: Context<MintTokens>, amount: u64) -> Result<()> {
    require!(amount > 0, ErrorCode::InvalidAmount);
    
    // Mint tokens using config PDA as authority
    let seeds = &[
        CONFIG_SEED,
        &[ctx.accounts.config.bump],
    ];
    let signer = &[&seeds[..]];
    
    let cpi_accounts = MintTo {
        mint: ctx.accounts.token_mint.to_account_info(),
        to: ctx.accounts.destination.to_account_info(),
        authority: ctx.accounts.config.to_account_info(),
    };
    
    let cpi_program = ctx.accounts.token_program.to_account_info();
    let cpi_ctx = CpiContext::new_with_signer(cpi_program, cpi_accounts, signer);
    
    anchor_spl::token::mint_to(cpi_ctx, amount)?;
    
    msg!("Minted {} tokens to {}", amount, ctx.accounts.destination.key());
    Ok(())
}

// ============================================================================
// Program Module
// ============================================================================

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
        initialize_config_handler(
            ctx,
            subscription_price_sol,
            subscription_price_usdc,
            subscription_duration,
            staking_fee_share_bps,
        )
    }

    /// Create the $EDGEAI token mint
    pub fn create_token_mint(ctx: Context<CreateTokenMint>) -> Result<()> {
        create_token_mint_handler(ctx)
    }

    /// Subscribe with SOL payment
    pub fn subscribe_sol(ctx: Context<SubscribeSol>) -> Result<()> {
        subscribe_sol_handler(ctx)
    }

    /// Subscribe with USDC payment
    pub fn subscribe_usdc(ctx: Context<SubscribeUsdc>) -> Result<()> {
        subscribe_usdc_handler(ctx)
    }

    /// Stake $EDGEAI tokens
    pub fn stake(ctx: Context<Stake>, amount: u64) -> Result<()> {
        stake_handler(ctx, amount)
    }

    /// Unstake $EDGEAI tokens
    pub fn unstake(ctx: Context<Unstake>, amount: u64) -> Result<()> {
        unstake_handler(ctx, amount)
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
        update_config_handler(
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
        distribute_fees_handler(ctx, amount)
    }

    /// Mint tokens (admin only, for testing/initial distribution)
    pub fn mint_tokens(ctx: Context<MintTokens>, amount: u64) -> Result<()> {
        mint_tokens_handler(ctx, amount)
    }
}
