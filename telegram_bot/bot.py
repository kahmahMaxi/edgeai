import os
import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackQueryHandler
)
from telegram.constants import ParseMode
import aiohttp
from solders.pubkey import Pubkey
from dotenv import load_dotenv
import base58
import base64

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
RPC_URL = os.getenv("RPC_URL", "https://api.devnet.solana.com")
FEE_WALLET = os.getenv("FEE_WALLET", "")
PROGRAM_ID = os.getenv("PROGRAM_ID", "JG8fS89RdsLUGUst41UTj8kFFEjBxQKV6yzPaBmAEwL")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")

# Store user wallets (in production, use database)
user_wallets: Dict[int, str] = {}

# Subscription PDA seeds
SUBSCRIPTION_SEED = b"subscription"

def get_subscription_pda(user_pubkey: Pubkey, program_id: Pubkey) -> Pubkey:
    """Derive subscription PDA for a user"""
    seeds = [SUBSCRIPTION_SEED, bytes(user_pubkey)]
    return Pubkey.find_program_address(seeds, program_id)[0]

async def check_premium_status(user_pubkey_str: str) -> tuple[bool, Optional[datetime]]:
    """
    Check if user has active subscription by querying Solana RPC
    Returns (is_premium, expires_at)
    """
    try:
        # Parse pubkey
        user_pubkey = Pubkey.from_string(user_pubkey_str)
        program_pubkey = Pubkey.from_string(PROGRAM_ID)
        
        # Derive subscription PDA
        subscription_pda = get_subscription_pda(user_pubkey, program_pubkey)
        
        # Query account using aiohttp (solders async client can be complex)
        async with aiohttp.ClientSession() as session:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getAccountInfo",
                "params": [
                    str(subscription_pda),
                    {
                        "encoding": "base64"
                    }
                ]
            }
            
            async with session.post(RPC_URL, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    return False, None
                
                result = await response.json()
                
                if "result" not in result or result["result"]["value"] is None:
                    return False, None
                
                # Get account data (base64 encoded)
                account_data_b64 = result["result"]["value"]["data"][0]
                import base64
                data = base64.b64decode(account_data_b64)
                
                if len(data) < 50:  # Minimum expected size
                    return False, None
                
                # Parse account data
                # Structure: [discriminator(8), user(32), expires_at(8), payment_method(1), bump(1)]
                # Extract expires_at (i64, little-endian, at offset 40)
                expires_at_bytes = data[40:48]
                expires_at = int.from_bytes(expires_at_bytes, byteorder='little', signed=True)
                
                # Check if subscription is active
                current_timestamp = int(datetime.now().timestamp())
                is_active = expires_at > current_timestamp
                
                expires_at_dt = datetime.fromtimestamp(expires_at) if expires_at > 0 else None
                
                return is_active, expires_at_dt
            
    except Exception as e:
        logger.error(f"Error checking premium status: {e}")
        return False, None

async def fetch_backend(endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
    """Fetch data from backend API"""
    try:
        url = f"{BACKEND_URL}{endpoint}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Backend API error: {response.status}")
                    return None
    except Exception as e:
        logger.error(f"Error fetching from backend: {e}")
        return None

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user_id = update.effective_user.id
    username = update.effective_user.username or "there"
    
    # Check if user has wallet connected
    wallet = user_wallets.get(user_id)
    
    welcome_text = f"👋 Welcome to $EDGEAI Prediction Booster, @{username}!\n\n"
    welcome_text += "🚀 Get AI-powered boosted probabilities for Polymarket predictions.\n\n"
    
    if wallet:
        welcome_text += f"✅ Wallet connected: `{wallet[:8]}...{wallet[-8:]}`\n\n"
        # Check premium status
        is_premium, expires_at = await check_premium_status(wallet)
        if is_premium and expires_at:
            welcome_text += f"⭐ Premium active until: {expires_at.strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
        else:
            welcome_text += "🔓 Connect wallet to access premium features\n"
    else:
        welcome_text += "🔓 Connect your wallet to access premium features\n"
    
    welcome_text += "\n📋 Commands:\n"
    welcome_text += "/markets - View top prediction markets\n"
    welcome_text += "/boost <slug> - Get boosted probability\n"
    welcome_text += "/signals - View top signals (premium)\n"
    welcome_text += "/subscribe - Subscribe for premium access\n"
    
    # Add wallet connect button
    keyboard = []
    if not wallet:
        # Phantom deep link
        phantom_link = f"https://phantom.app/ul/v1/connect?app_url=https://t.me/{context.bot.username}&redirect_link=https://t.me/{context.bot.username}"
        keyboard.append([InlineKeyboardButton("🔗 Connect Phantom Wallet", url=phantom_link)])
    
    keyboard.append([InlineKeyboardButton("📊 View Markets", callback_data="markets")])
    
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    
    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /subscribe command"""
    user_id = update.effective_user.id
    wallet = user_wallets.get(user_id)
    
    if not wallet:
        text = "❌ No wallet connected.\n\n"
        text += "Please connect your wallet first using /start\n\n"
        text += "Or send your Solana wallet address to connect."
        await update.message.reply_text(text)
        return
    
    # Check premium status
    is_premium, expires_at = await check_premium_status(wallet)
    
    if is_premium and expires_at:
        text = f"✅ Premium Subscription Active\n\n"
        text += f"Expires: {expires_at.strftime('%Y-%m-%d %H:%M:%S')} UTC\n\n"
        text += "You have access to:\n"
        text += "• Real-time signals\n"
        text += "• Premium market analysis\n"
        text += "• Priority notifications"
    else:
        text = "🔓 Premium Subscription Required\n\n"
        text += "Subscribe to unlock:\n"
        text += "• Real-time boosted signals\n"
        text += "• Premium market analysis\n"
        text += "• Priority notifications\n\n"
        text += "💳 Payment Options:\n\n"
        text += "SOL Payment:\n"
        text += f"Send SOL to: `{FEE_WALLET}`\n\n"
        text += "USDC Payment:\n"
        text += f"Send USDC to: `{FEE_WALLET}`\n\n"
        text += "After payment, use the dApp to subscribe:\n"
        text += "Or wait for automatic verification (may take a few minutes)"
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def markets_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /markets command"""
    await update.message.reply_text("📊 Fetching top markets...")
    
    data = await fetch_backend("/markets", {"category": "crypto", "limit": "10"})
    
    if not data or not isinstance(data, list):
        await update.message.reply_text("❌ Failed to fetch markets. Please try again later.")
        return
    
    text = "📊 Top Prediction Markets\n\n"
    
    for i, market in enumerate(data[:10], 1):
        slug = market.get("slug", "unknown")
        question = market.get("question", "Unknown question")
        yes_prob = market.get("yes_prob", 0) * 100
        volume = market.get("volume", 0)
        
        # Truncate long questions
        if len(question) > 60:
            question = question[:57] + "..."
        
        text += f"{i}. {question}\n"
        text += f"   Yes: {yes_prob:.1f}% | Volume: ${volume:,.0f}\n"
        text += f"   `/boost {slug}`\n\n"
    
    text += "💡 Use /boost <slug> to get boosted probability"
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def boost_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /boost <market_slug> command"""
    if not context.args:
        await update.message.reply_text(
            "❌ Please provide a market slug.\n\n"
            "Example: /boost will-gta-6-cost-100\n\n"
            "Get slugs from /markets"
        )
        return
    
    market_slug = context.args[0]
    await update.message.reply_text(f"🔮 Calculating boosted probability for: {market_slug}...")
    
    data = await fetch_backend("/boost_prob", {"market_slug": market_slug})
    
    if not data:
        await update.message.reply_text("❌ Failed to fetch boosted probability. Please try again.")
        return
    
    market_prob = data.get("market_prob", 0) * 100
    boosted_prob = data.get("boosted_prob", 0) * 100
    signal = data.get("signal", "neutral")
    sentiment = data.get("sentiment_score", 0)
    momentum = data.get("price_momentum", 0)
    
    # Signal emoji
    signal_emoji = {
        "buy_yes": "🟢",
        "sell_yes": "🔴",
        "neutral": "🟡"
    }.get(signal, "⚪")
    
    text = f"📈 Boosted Probability Analysis\n\n"
    text += f"Market: `{market_slug}`\n\n"
    text += f"📊 Market Probability: {market_prob:.2f}%\n"
    text += f"🚀 Boosted Probability: {boosted_prob:.2f}%\n"
    text += f"📉 Difference: {boosted_prob - market_prob:+.2f}%\n\n"
    text += f"{signal_emoji} Signal: **{signal.upper().replace('_', ' ')}**\n\n"
    text += f"📊 Sentiment Score: {sentiment:+.2f}\n"
    text += f"📈 Price Momentum: {momentum:+.2f}\n\n"
    
    if signal == "buy_yes":
        text += "💡 Signal suggests buying YES shares"
    elif signal == "sell_yes":
        text += "💡 Signal suggests selling YES shares"
    else:
        text += "💡 Signal is neutral"
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def signals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /signals command - premium only"""
    user_id = update.effective_user.id
    wallet = user_wallets.get(user_id)
    
    if not wallet:
        await update.message.reply_text(
            "❌ Premium feature. Please connect wallet and subscribe.\n\n"
            "Use /start to connect wallet"
        )
        return
    
    # Check premium
    is_premium, _ = await check_premium_status(wallet)
    if not is_premium:
        await update.message.reply_text(
            "❌ Premium subscription required.\n\n"
            "Use /subscribe to get premium access"
        )
        return
    
    await update.message.reply_text("🔔 Fetching top signals...")
    
    # Fetch markets
    markets_data = await fetch_backend("/markets", {"category": "crypto", "limit": "50"})
    
    if not markets_data:
        await update.message.reply_text("❌ Failed to fetch signals. Please try again.")
        return
    
    signals = []
    for market in markets_data:
        slug = market.get("slug", "")
        market_prob = market.get("yes_prob", 0)
        
        # Get boosted probability
        boost_data = await fetch_backend("/boost_prob", {"market_slug": slug})
        if boost_data:
            boosted_prob = boost_data.get("boosted_prob", 0)
            signal = boost_data.get("signal", "neutral")
            
            # Only include buy_yes signals with significant boost
            if signal == "buy_yes" and (boosted_prob - market_prob) > 0.05:
                signals.append({
                    "slug": slug,
                    "question": market.get("question", ""),
                    "market_prob": market_prob,
                    "boosted_prob": boosted_prob,
                    "boost": boosted_prob - market_prob
                })
    
    # Sort by boost amount
    signals.sort(key=lambda x: x["boost"], reverse=True)
    
    if not signals:
        text = "📊 No strong signals at the moment.\n\n"
        text += "Check back later or use /boost <slug> for specific markets."
    else:
        text = f"🔔 Top {min(5, len(signals))} Signals\n\n"
        for i, signal in enumerate(signals[:5], 1):
            question = signal["question"]
            if len(question) > 50:
                question = question[:47] + "..."
            
            text += f"{i}. {question}\n"
            text += f"   Market: {signal['market_prob']*100:.1f}% → Boosted: {signal['boosted_prob']*100:.1f}% (+{signal['boost']*100:.1f}%)\n"
            text += f"   `/boost {signal['slug']}`\n\n"
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def handle_wallet_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle wallet address messages"""
    user_id = update.effective_user.id
    wallet_address = update.message.text.strip()
    
    # Basic validation (Solana addresses are base58, 32-44 chars)
    if len(wallet_address) < 32 or len(wallet_address) > 44:
        await update.message.reply_text(
            "❌ Invalid wallet address format.\n\n"
            "Please send a valid Solana wallet address (32-44 characters)"
        )
        return
    
    # Try to validate as base58
    try:
        base58.b58decode(wallet_address)
        # Store wallet
        user_wallets[user_id] = wallet_address
        await update.message.reply_text(
            f"✅ Wallet connected!\n\n"
            f"Address: `{wallet_address}`\n\n"
            f"Use /subscribe to check premium status"
        )
    except Exception:
        await update.message.reply_text(
            "❌ Invalid wallet address. Please send a valid Solana address."
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button callbacks"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "markets":
        # Trigger markets command
        update.message = query.message
        await markets_command(update, context)

async def background_signal_pusher(context: ContextTypes.DEFAULT_TYPE):
    """Background job to push signals to premium users every 10 minutes"""
    logger.info("Running background signal pusher...")
    
    # Fetch markets
    markets_data = await fetch_backend("/markets", {"category": "crypto", "limit": "50"})
    if not markets_data:
        logger.warning("No markets data available")
        return
    
    current_signals = []
    for market in markets_data:
        slug = market.get("slug", "")
        market_prob = market.get("yes_prob", 0)
        
        boost_data = await fetch_backend("/boost_prob", {"market_slug": slug})
        if boost_data:
            boosted_prob = boost_data.get("boosted_prob", 0)
            signal = boost_data.get("signal", "neutral")
            
            if signal == "buy_yes" and (boosted_prob - market_prob) > 0.05:
                current_signals.append({
                    "slug": slug,
                    "question": market.get("question", ""),
                    "market_prob": market_prob,
                    "boosted_prob": boosted_prob,
                    "boost": boosted_prob - market_prob
                })
    
    # Sort by boost amount
    current_signals.sort(key=lambda x: x["boost"], reverse=True)
    
    # Send to premium users
    sent_count = 0
    for user_id, wallet in list(user_wallets.items()):
        try:
            is_premium, _ = await check_premium_status(wallet)
            if is_premium and current_signals:
                # Send top 3 signals
                text = "🔔 New Signals Detected!\n\n"
                for i, signal in enumerate(current_signals[:3], 1):
                    question = signal["question"]
                    if len(question) > 50:
                        question = question[:47] + "..."
                    text += f"{i}. {question}\n"
                    text += f"   Boost: +{signal['boost']*100:.1f}%\n"
                    text += f"   `/boost {signal['slug']}`\n\n"
                
                await context.bot.send_message(
                    chat_id=user_id,
                    text=text,
                    parse_mode=ParseMode.MARKDOWN
                )
                sent_count += 1
        except Exception as e:
            logger.error(f"Error sending signal to user {user_id}: {e}")
    
    if sent_count > 0:
        logger.info(f"Sent signals to {sent_count} premium users")

def main():
    """Start the bot"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set in environment variables")
        return
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("subscribe", subscribe_command))
    application.add_handler(CommandHandler("markets", markets_command))
    application.add_handler(CommandHandler("boost", boost_command))
    application.add_handler(CommandHandler("signals", signals_command))
    
    # Add callback handler for inline buttons
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Add message handler for wallet addresses
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_wallet_address))
    
    # Set up webhook if WEBHOOK_URL is provided
    if WEBHOOK_URL:
        async def post_init(app: Application) -> None:
            await app.bot.set_webhook(WEBHOOK_URL)
            logger.info(f"Webhook set to {WEBHOOK_URL}")
        
        application.post_init = post_init
        logger.info("Running in webhook mode")
    else:
        logger.info("Running in polling mode")
    
    # Start background job
    job_queue = application.job_queue
    if job_queue:
        job_queue.run_repeating(
            background_signal_pusher,
            interval=600,  # 10 minutes
            first=60  # Start after 1 minute
        )
        logger.info("Background signal pusher scheduled")
    
    # Run the bot
    if WEBHOOK_URL:
        # Webhook mode (for Railway/Render)
        application.run_webhook(
            listen="0.0.0.0",
            port=int(os.getenv("PORT", "8000")),
            webhook_url=WEBHOOK_URL
        )
    else:
        # Polling mode (for local development)
        application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
