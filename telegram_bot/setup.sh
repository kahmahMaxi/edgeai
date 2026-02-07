#!/bin/bash
# Setup script for $EDGEAI Telegram Bot

echo "Setting up $EDGEAI Telegram Bot..."

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cat > .env << 'EOF'
# Telegram Bot Token (from @BotFather)
BOT_TOKEN=your_bot_token_here

# Backend API URL
BACKEND_URL=http://localhost:8000

# Solana RPC URL
RPC_URL=https://api.devnet.solana.com

# Fee wallet address (for subscription payments)
FEE_WALLET=your_fee_wallet_address_here

# Program ID (from your Anchor program)
PROGRAM_ID=JG8fS89RdsLUGUst41UTj8kFFEjBxQKV6yzPaBmAEwL

# Webhook URL (for production deployment - leave empty for polling mode)
WEBHOOK_URL=

# Port (for webhook mode)
PORT=8000
EOF
    echo "✅ .env file created. Please edit it with your bot token and settings."
else
    echo "✅ .env file already exists."
fi

echo ""
echo "Setup complete! Next steps:"
echo "1. Edit .env file with your BOT_TOKEN from @BotFather"
echo "2. Set BACKEND_URL to your FastAPI backend URL"
echo "3. Set FEE_WALLET to your fee wallet address"
echo "4. Run: source venv/bin/activate && python bot.py"
