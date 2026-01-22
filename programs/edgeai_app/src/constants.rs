use anchor_lang::prelude::*;

#[constant]
pub const CONFIG_SEED: &[u8] = b"config";
#[constant]
pub const SUBSCRIPTION_SEED: &[u8] = b"subscription";
#[constant]
pub const STAKING_VAULT_SEED: &[u8] = b"staking_vault";
#[constant]
pub const TOKEN_MINT_SEED: &[u8] = b"token_mint";
#[constant]
pub const TOKEN_DECIMALS: u8 = 9;
