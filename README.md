# $EDGEAI - AI-Powered Prediction Market Booster

A Solana smart contract program built with Anchor framework for the $EDGEAI token and utility ecosystem. This program provides token minting, premium subscriptions, and staking functionality with fee distribution mechanisms.

## Features

### 🪙 Token
- SPL token mint for $EDGEAI with 9 decimals
- PDA-controlled mint authority via Config account

### ⚙️ Configuration
- Admin-controlled Config PDA
- Configurable subscription pricing (SOL/USDC)
- Flexible subscription duration settings
- Staking fee share percentage (basis points)

### 💎 Premium Subscriptions
- **SOL Payment**: Subscribe with native SOL
- **USDC Payment**: Subscribe with USDC tokens
- Timestamp-based expiration tracking
- Per-user subscription PDA accounts

### 🏦 Staking Vault
- Stake $EDGEAI tokens to earn fee shares
- Track total staked amount across all users
- Individual user stake tracking
- Unstake functionality

### 👨‍💼 Admin Functions
- Update configuration parameters
- Distribute fees to stakers based on configured fee share
- Secure admin-only operations with signer validation

## Security

- ✅ Checked math operations (no overflow vulnerabilities)
- ✅ Comprehensive account validation
- ✅ Proper signer checks for admin operations
- ✅ PDA-based account derivation
- ✅ Anchor framework best practices

## Tech Stack

- **Framework**: Anchor 0.32.1
- **Language**: Rust
- **Blockchain**: Solana
- **Token Standard**: SPL Token

## Program Structure

```
programs/edgeai_app/src/
├── lib.rs              # Main program entry point
├── constants.rs        # PDA seeds and constants
├── error.rs            # Custom error codes
├── state/              # Account state structs
│   └── mod.rs          # Config, Subscription, StakingVault, UserStake
└── instructions/       # Instruction handlers
    ├── initialize_config.rs
    ├── create_token_mint.rs
    ├── subscribe_sol.rs
    ├── subscribe_usdc.rs
    ├── stake.rs
    ├── unstake.rs
    ├── update_config.rs
    └── distribute_fees.rs
```

## Development

### Build
```bash
anchor build
```

### Test
```bash
anchor test
```

### Deploy
```bash
anchor deploy
```

## Future Integrations

- Polymarket Gamma API integration for off-chain prediction market data
- Enhanced fee distribution mechanisms
- Additional utility features for prediction market boosting

## License

ISC
