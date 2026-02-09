# $EDGEAI Telegram Bot

Telegram bot for $EDGEAI prediction booster signals. Provides real-time market data, boosted probabilities, and premium signals to subscribers.

## Features

- 📊 **Market Data**: View top prediction markets from Polymarket
- 🚀 **Boosted Probabilities**: Get AI-enhanced probability calculations
- 🔔 **Premium Signals**: Real-time signal notifications for subscribers
- 💰 **Wallet Integration**: Connect Solana wallet and check subscription status
- ⚡ **Background Jobs**: Automatic signal pushing every 10 minutes

## Setup

### Prerequisites

1. **Telegram Bot Token**
   - Message [@BotFather](https://t.me/BotFather) on Telegram
   - Create a new bot with `/newbot`
   - Copy the bot token

2. **Python 3.11+**
   ```bash
   sudo apt install python3 python3-pip python3-venv
   ```

### Installation

1. **Create virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   # The .env file should be in the telegram_bot folder (not root)
   # Run setup.sh to create it, or create manually:
   cat > .env << 'EOF'
BOT_TOKEN=your_bot_token_from_botfather
BACKEND_URL=http://localhost:8000
RPC_URL=https://api.devnet.solana.com
FEE_WALLET=your_fee_wallet_address
PROGRAM_ID=JG8fS89RdsLUGUst41UTj8kFFEjBxQKV6yzPaBmAEwL
WEBHOOK_URL=
PORT=8000
EOF
   # Then edit .env and add your BOT_TOKEN from @BotFather
   ```
   
   **Getting Bot Token:**
   1. Open Telegram, search for [@BotFather](https://t.me/BotFather)
   2. Send `/newbot` command
   3. Follow prompts to name your bot
   4. Copy the token BotFather gives you
   5. Paste it as `BOT_TOKEN` in `.env`

### Environment Variables

```bash
BOT_TOKEN=your_bot_token_from_botfather
BACKEND_URL=http://localhost:8000  # Your FastAPI backend URL
RPC_URL=https://api.devnet.solana.com  # Solana RPC endpoint
FEE_WALLET=3vqEDEV6PBvpRc6TSC7grWPNAWGhL4q8mhxfeAubZ6RJ  # Fee wallet for subscription payments
PROGRAM_ID=JG8fS89RdsLUGUst41UTj8kFFEjBxQKV6yzPaBmAEwL  # Your program ID

# Subscription payment configuration
SUBSCRIBE_SOL_ENABLED=true   # Enable/disable SOL payments
SUBSCRIBE_SOL_AMOUNT=0.01    # Amount in SOL (e.g., 0.01 SOL)
SUBSCRIBE_USDC_ENABLED=true # Enable/disable USDC payments
SUBSCRIBE_USDC_AMOUNT=3.0    # Amount in USDC (e.g., 3.0 USDC)
WEBHOOK_URL=  # Leave empty for polling, set for webhook mode
PORT=8000  # For webhook mode
```

## Running

### Local Development (Polling Mode)

```bash
source venv/bin/activate
python bot.py
```

The bot will run in polling mode, fetching updates from Telegram.

### Production (Webhook Mode)

For deployment on Railway/Render/Vercel:

1. Set `WEBHOOK_URL` to your public URL (e.g., `https://your-bot.railway.app`)
2. Set `PORT` environment variable
3. Deploy and the bot will automatically set the webhook

```bash
# Example for Railway
railway up
```

## Commands

### `/start`
Welcome message and wallet connection instructions. Automatically creates user entry in database.

### `/help`
Show comprehensive command guide and quick start instructions.

### `/connect <pubkey>`
Connect your Solana wallet to the bot:
- Validates wallet address format (base58)
- Stores wallet in database
- Required for premium features

Example: `/connect 7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU`

### `/subscribe`
Check premium subscription status and subscribe:
- Shows active subscription expiration (if premium)
- **Configurable payment options** from `.env`:
  - SOL payment: Amount and wallet from `SUBSCRIBE_SOL_AMOUNT` and `FEE_WALLET`
  - USDC payment: Amount and wallet from `SUBSCRIBE_USDC_AMOUNT` and `FEE_WALLET`
- If both methods disabled → Shows "Subscription temporarily disabled"
- **Simple flow**: Send payment using your wallet (Phantom/etc), bot auto-detects subscription
- **Auto-polling**: Automatically checks for subscription every 30 seconds (up to 5 minutes)
- Sends confirmation "Premium Active!" when subscription is detected
- No dApp needed — just send payment and wait!

**Configuration**: Set `SUBSCRIBE_SOL_ENABLED`, `SUBSCRIBE_SOL_AMOUNT`, `SUBSCRIBE_USDC_ENABLED`, `SUBSCRIBE_USDC_AMOUNT` in `.env` to customize payment options.

### `/status`
Check your current status:
- Connected wallet address
- Premium subscription status and expiration (if active)
- Alerts opt-in status (enabled/disabled)
- Quick reference for all your settings

### `/alerts on/off`
Toggle signal notifications:
- `/alerts on` - Enable background signal notifications
- `/alerts off` - Disable notifications
- Default: enabled for all users
- Only premium users with alerts enabled receive notifications

### `/markets`
Fetch and display top 10 prediction markets from backend with:
- Market question
- Yes probability
- Trading volume
- Quick boost command

### `/boost <market_slug>`
Get boosted probability for a specific market:
- Market probability
- Boosted probability
- Signal (buy_yes/sell_yes/neutral)
- Sentiment score
- Price momentum

Example: `/boost will-gta-6-cost-100`

### `/signals` (Premium Only)
View top signals where boosted probability significantly exceeds market probability:
- Shows markets with boost > 5%
- Sorted by boost amount
- Includes quick boost commands

## Database

The bot uses SQLite (`users.db`) to store:
- `user_id` - Telegram user ID
- `chat_id` - Telegram chat ID
- `wallet_pubkey` - Connected Solana wallet address
- `alerts_opt_in` - Notification preference (default: enabled)
- `created_at` / `updated_at` - Timestamps

The database is automatically created on first run. No manual setup required.

## Wallet Connection

Users can connect their Solana wallet by:
1. Using `/connect <pubkey>` command (recommended)
2. Sending wallet address as a message (fallback)

The bot validates the address format (base58) and stores it in the database for premium checks.

## Subscription Configuration

**Payment options are configured via `.env`** for easy testing and customization:

- `SUBSCRIBE_SOL_ENABLED` - Enable/disable SOL payments (true/false)
- `SUBSCRIBE_SOL_AMOUNT` - Amount in SOL (e.g., 0.01)
- `SUBSCRIBE_USDC_ENABLED` - Enable/disable USDC payments (true/false)
- `SUBSCRIBE_USDC_AMOUNT` - Amount in USDC (e.g., 3.0)
- `FEE_WALLET` - Wallet address to receive payments

### Example Configuration

For testing with low amounts:
```bash
SUBSCRIBE_SOL_ENABLED=true
SUBSCRIBE_SOL_AMOUNT=0.01
SUBSCRIBE_USDC_ENABLED=true
SUBSCRIBE_USDC_AMOUNT=3.0
FEE_WALLET=3vqEDEV6PBvpRc6TSC7grWPNAWGhL4q8mhxfeAubZ6RJ
```

To disable a payment method:
```bash
SUBSCRIBE_SOL_ENABLED=false
SUBSCRIBE_USDC_ENABLED=true
```

**Note**: The bot shows payment instructions based on these `.env` values. Users send payments directly to `FEE_WALLET`, and the bot automatically detects subscriptions via on-chain polling. No dApp required!

## Premium Subscription Check

The bot checks subscription status by:
1. Deriving the subscription PDA: `["subscription", user_pubkey]`
2. Querying Solana RPC for the account
3. Checking if `expires_at > current_timestamp`

**Subscription Polling:**
- After `/subscribe` shows payment instructions, the bot automatically polls RPC every 30 seconds
- Polls for up to 5 minutes (10 attempts)
- Sends confirmation message when subscription is detected
- No manual refresh needed!

Premium users get:
- Access to `/signals` command
- Automatic signal notifications every 10 minutes (if alerts enabled)
- Priority updates

## Background Jobs

The bot runs a background job every 10 minutes that:
1. Fetches markets from backend
2. Calculates boosted probabilities
3. Identifies new strong signals (boost > 5%)
4. Pushes notifications to **opted-in premium users only**
   - Checks database for `alerts_opt_in = 1`
   - Verifies premium status on-chain
   - Sends to users who meet both conditions

## Deployment

### Railway

1. Connect your GitHub repo
2. Set environment variables in Railway dashboard
3. Set `WEBHOOK_URL` to your Railway app URL
4. Deploy

### Render

1. Create new Web Service
2. Set build command: `pip install -r requirements.txt`
3. Set start command: `python bot.py`
4. Add environment variables
5. Set `WEBHOOK_URL` to your Render URL

### Vercel

1. Create `vercel.json`:
```json
{
  "version": 2,
  "builds": [{"src": "bot.py", "use": "@vercel/python"}],
  "routes": [{"src": "/(.*)", "dest": "bot.py"}]
}
```
2. Deploy with environment variables

## Troubleshooting

### Bot not responding
- Check BOT_TOKEN is correct
- Verify backend is running and accessible
- Check logs for errors

### Database issues
- Database file `users.db` is created automatically
- If corrupted, delete `users.db` and restart bot (users will need to reconnect)
- Check file permissions in deployment environment

### Premium check failing
- Verify RPC_URL is correct and accessible
- Check PROGRAM_ID matches your deployed program
- Ensure wallet address format is correct
- Use `/connect` to reconnect wallet if needed

### Signals not pushing
- Check background job is running (logs should show "Running background signal pusher...")
- Verify users have active subscriptions
- Check users have alerts enabled (`/alerts on`)
- Verify backend API is responding
- Check database for opted-in users: `SELECT * FROM users WHERE alerts_opt_in = 1`

### Subscription polling not working
- Ensure wallet is connected (`/connect`)
- Check RPC endpoint is accessible
- Subscription may take a few minutes to appear on-chain
- Try `/subscribe` again if polling times out

## Development

### Testing Commands

1. Start the bot locally
2. Find your bot on Telegram
3. Send `/start` to begin
4. Test each command

### Logging

Logs are output to console with INFO level. For production, consider:
- File logging
- Log aggregation service (e.g., Logtail, Datadog)
- Error tracking (e.g., Sentry)

## Security Notes

- Never commit `.env` file
- Use environment variables for all secrets
- Validate wallet addresses before storing
- Rate limit commands if needed
- Consider adding user authentication

## Future Enhancements

- [x] SQLite database for persistent user/wallet storage
- [x] `/connect` command for wallet connection
- [x] `/help` command
- [x] `/alerts` toggle for notifications
- [x] Subscription polling for automatic confirmation
- [ ] Admin commands for bot management
- [ ] Custom signal filters per user
- [ ] Integration with Solana wallet adapter
- [ ] Multi-language support
- [ ] Analytics and usage tracking
- [ ] Transaction links in subscription messages