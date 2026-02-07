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
FEE_WALLET=your_fee_wallet_address  # For subscription payments
PROGRAM_ID=JG8fS89RdsLUGUst41UTj8kFFEjBxQKV6yzPaBmAEwL  # Your program ID
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
Welcome message and wallet connection instructions.

### `/subscribe`
Check premium subscription status. Shows:
- Active subscription expiration date (if premium)
- Payment instructions (if not premium)

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

## Wallet Connection

Users can connect their Solana wallet by:
1. Sending their wallet address as a message to the bot
2. Using the Phantom deep link (if implemented in frontend)

The bot validates the address format and stores it for premium checks.

## Premium Subscription Check

The bot checks subscription status by:
1. Deriving the subscription PDA: `["subscription", user_pubkey]`
2. Querying Solana RPC for the account
3. Checking if `expires_at > current_timestamp`

Premium users get:
- Access to `/signals` command
- Automatic signal notifications every 10 minutes
- Priority updates

## Background Jobs

The bot runs a background job every 10 minutes that:
1. Fetches markets from backend
2. Calculates boosted probabilities
3. Identifies new strong signals (boost > 5%)
4. Pushes notifications to premium users

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

### Premium check failing
- Verify RPC_URL is correct and accessible
- Check PROGRAM_ID matches your deployed program
- Ensure wallet address format is correct

### Signals not pushing
- Check background job is running (logs should show "Starting background signal pusher...")
- Verify users have active subscriptions
- Check backend API is responding

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

- [ ] Database for persistent user/wallet storage
- [ ] Admin commands for bot management
- [ ] Custom signal filters per user
- [ ] Integration with Solana wallet adapter
- [ ] Multi-language support
- [ ] Analytics and usage tracking
