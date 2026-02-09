import os
import asyncio
import logging
import sqlite3
from datetime import datetime
from typing import Optional, Dict, List, Tuple

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
FEE_WALLET = os.getenv("FEE_WALLET", "3vqEDEV6PBvpRc6TSC7grWPNAWGhL4q8mhxfeAubZ6RJ")
PROGRAM_ID = os.getenv("PROGRAM_ID", "JG8fS89RdsLUGUst41UTj8kFFEjBxQKV6yzPaBmAEwL")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")

# Subscription configuration
SUBSCRIBE_SOL_ENABLED = os.getenv("SUBSCRIBE_SOL_ENABLED", "true").lower() == "true"
SUBSCRIBE_SOL_AMOUNT = float(os.getenv("SUBSCRIBE_SOL_AMOUNT", "0.01"))
SUBSCRIBE_USDC_ENABLED = os.getenv("SUBSCRIBE_USDC_ENABLED", "true").lower() == "true"
SUBSCRIBE_USDC_AMOUNT = float(os.getenv("SUBSCRIBE_USDC_AMOUNT", "3.0"))

# Database file
DB_FILE = "users.db"

# Subscription PDA seeds
SUBSCRIPTION_SEED = b"subscription"
CONFIG_SEED = b"config"

# ============================================================================
# Database Functions
# ============================================================================

def init_database():
    """Initialize SQLite database"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            chat_id INTEGER NOT NULL,
            wallet_pubkey TEXT,
            alerts_opt_in INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()
    logger.info("Database initialized")

def get_user(user_id: int) -> Optional[Tuple]:
    """Get user from database"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, chat_id, wallet_pubkey, alerts_opt_in FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result

def create_or_update_user(user_id: int, chat_id: int, wallet_pubkey: Optional[str] = None, alerts_opt_in: bool = True):
    """Create or update user in database"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Check if user exists
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    exists = cursor.fetchone()
    
    if exists:
        # Update existing user
        if wallet_pubkey is not None:
            cursor.execute("""
                UPDATE users 
                SET wallet_pubkey = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE user_id = ?
            """, (wallet_pubkey, user_id))
        else:
            cursor.execute("""
                UPDATE users 
                SET alerts_opt_in = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE user_id = ?
            """, (1 if alerts_opt_in else 0, user_id))
    else:
        # Create new user
        cursor.execute("""
            INSERT INTO users (user_id, chat_id, wallet_pubkey, alerts_opt_in)
            VALUES (?, ?, ?, ?)
        """, (user_id, chat_id, wallet_pubkey, 1 if alerts_opt_in else 0))
    
    conn.commit()
    conn.close()

def update_alerts_opt_in(user_id: int, opt_in: bool):
    """Update alerts opt-in status"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users 
        SET alerts_opt_in = ?, updated_at = CURRENT_TIMESTAMP 
        WHERE user_id = ?
    """, (1 if opt_in else 0, user_id))
    conn.commit()
    conn.close()

def get_opted_in_premium_users() -> List[Tuple[int, int, str]]:
    """Get all users who have opted in and have premium (returns list of (user_id, chat_id, wallet_pubkey))"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user_id, chat_id, wallet_pubkey 
        FROM users 
        WHERE alerts_opt_in = 1 AND wallet_pubkey IS NOT NULL
    """)
    results = cursor.fetchall()
    conn.close()
    return results

# ============================================================================
# Solana Functions
# ============================================================================

def get_config_pda(program_id: Pubkey) -> Pubkey:
    """Derive Config PDA"""
    seeds = [CONFIG_SEED]
    return Pubkey.find_program_address(seeds, program_id)[0]

def get_subscription_pda(user_pubkey: Pubkey, program_id: Pubkey) -> Pubkey:
    """Derive subscription PDA for a user"""
    seeds = [SUBSCRIPTION_SEED, bytes(user_pubkey)]
    return Pubkey.find_program_address(seeds, program_id)[0]

async def get_subscription_prices() -> Optional[Dict[str, int]]:
    """
    Fetch subscription prices from on-chain Config PDA
    Returns dict with 'sol' (lamports) and 'usdc' (6 decimals) or None if error
    """
    try:
        program_pubkey = Pubkey.from_string(PROGRAM_ID)
        config_pda = get_config_pda(program_pubkey)
        
        async with aiohttp.ClientSession() as session:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getAccountInfo",
                "params": [
                    str(config_pda),
                    {
                        "encoding": "base64"
                    }
                ]
            }
            
            async with session.post(RPC_URL, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    return None
                
                result = await response.json()
                
                if "result" not in result or result["result"]["value"] is None:
                    return None
                
                # Get account data (base64 encoded)
                account_data_b64 = result["result"]["value"]["data"][0]
                data = base64.b64decode(account_data_b64)
                
                if len(data) < 120:  # Minimum expected size
                    return None
                
                # Parse Config account data
                # Structure: [discriminator(8), admin(32), fee_wallet(32), token_mint(32), 
                #            subscription_price_sol(8), subscription_price_usdc(8), ...]
                # subscription_price_sol at offset 104 (8+32+32+32)
                # subscription_price_usdc at offset 112 (104+8)
                
                price_sol_bytes = data[104:112]
                price_usdc_bytes = data[112:120]
                
                price_sol = int.from_bytes(price_sol_bytes, byteorder='little', signed=False)
                price_usdc = int.from_bytes(price_usdc_bytes, byteorder='little', signed=False)
                
                return {
                    "sol": price_sol,  # in lamports
                    "usdc": price_usdc  # in USDC (6 decimals)
                }
            
    except Exception as e:
        logger.error(f"Error fetching subscription prices: {e}")
        return None

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
        
        # Query account using aiohttp
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

async def poll_subscription_status(user_pubkey_str: str, max_attempts: int = 10, interval: int = 30) -> tuple[bool, Optional[datetime]]:
    """
    Poll RPC for subscription status (for subscription confirmation)
    Returns (is_premium, expires_at)
    """
    for attempt in range(max_attempts):
        is_premium, expires_at = await check_premium_status(user_pubkey_str)
        if is_premium:
            return True, expires_at
        await asyncio.sleep(interval)
    return False, None

# ============================================================================
# Backend API Functions
# ============================================================================

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

# ============================================================================
# Command Handlers
# ============================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    username = update.effective_user.username or "there"
    
    # Ensure user exists in DB
    create_or_update_user(user_id, chat_id)
    
    # Get user from DB
    user = get_user(user_id)
    wallet = user[2] if user and user[2] else None
    
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
    welcome_text += "/help - Show all commands\n"
    welcome_text += "/connect <pubkey> - Connect Solana wallet\n"
    welcome_text += "/status - Check wallet, premium, alerts status\n"
    welcome_text += "/markets - View top prediction markets\n"
    welcome_text += "/boost <slug> - Get boosted probability\n"
    welcome_text += "/signals - View top signals (premium)\n"
    welcome_text += "/subscribe - Subscribe for premium access\n"
    welcome_text += "/alerts on/off - Toggle signal notifications\n"
    
    # Add wallet connect button
    keyboard = []
    if not wallet:
        # Phantom deep link
        phantom_link = f"https://phantom.app/ul/v1/connect?app_url=https://t.me/{context.bot.username}&redirect_link=https://t.me/{context.bot.username}"
        keyboard.append([InlineKeyboardButton("🔗 Connect Phantom Wallet", url=phantom_link)])
    
    keyboard.append([InlineKeyboardButton("📊 View Markets", callback_data="markets")])
    keyboard.append([InlineKeyboardButton("❓ Help", callback_data="help")])
    
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    
    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    text = "📚 $EDGEAI Bot Commands Guide\n\n"
    
    text += "🔹 **Basic Commands:**\n"
    text += "/start - Welcome message and setup\n"
    text += "/help - Show this help message\n"
    text += "/markets - View top prediction markets\n"
    text += "/boost <slug> - Get boosted probability for a market\n\n"
    
    text += "🔹 **Wallet & Premium:**\n"
    text += "/connect <pubkey> - Connect your Solana wallet\n"
    text += "/status - Check wallet, premium, and alerts status\n"
    text += "/subscribe - Subscribe for premium access\n"
    text += "/signals - View top signals (premium only)\n\n"
    
    text += "🔹 **Notifications:**\n"
    text += "/alerts on - Enable signal notifications\n"
    text += "/alerts off - Disable signal notifications\n\n"
    
    text += "💡 **Quick Start:**\n"
    text += "1. Use /connect to link your wallet\n"
    text += "2. Use /subscribe to get premium\n"
    text += "3. Use /markets to browse predictions\n"
    text += "4. Use /boost <slug> for AI-enhanced odds\n\n"
    
    text += "🔔 Premium users get:\n"
    text += "• Real-time signal notifications\n"
    text += "• Access to /signals command\n"
    text += "• Priority market analysis"
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def connect_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /connect <pubkey> command"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if not context.args:
        await update.message.reply_text(
            "❌ Please provide your Solana wallet address.\n\n"
            "Usage: /connect <your_wallet_address>\n\n"
            "Example: /connect 7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"
        )
        return
    
    wallet_address = context.args[0].strip()
    
    # Validate wallet address
    if len(wallet_address) < 32 or len(wallet_address) > 44:
        await update.message.reply_text(
            "❌ Invalid wallet address format.\n\n"
            "Please provide a valid Solana wallet address (32-44 characters)"
        )
        return
    
    # Try to validate as base58
    try:
        base58.b58decode(wallet_address)
        # Validate as Pubkey
        Pubkey.from_string(wallet_address)
        
        # Save to database
        create_or_update_user(user_id, chat_id, wallet_pubkey=wallet_address)
        
        await update.message.reply_text(
            f"✅ Wallet connected successfully!\n\n"
            f"Address: `{wallet_address}`\n\n"
            f"Use /subscribe to check premium status"
        )
    except Exception as e:
        logger.error(f"Error validating wallet: {e}")
        await update.message.reply_text(
            "❌ Invalid wallet address. Please provide a valid Solana address."
        )

async def alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /alerts on/off command"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Ensure user exists
    create_or_update_user(user_id, chat_id)
    
    if not context.args:
        # Show current status
        user = get_user(user_id)
        if user:
            opt_in = bool(user[3])
            status = "enabled" if opt_in else "disabled"
            emoji = "✅" if opt_in else "❌"
            await update.message.reply_text(
                f"{emoji} Signal notifications are currently **{status}**.\n\n"
                f"Use /alerts on to enable\n"
                f"Use /alerts off to disable"
            )
        else:
            await update.message.reply_text(
                "Use /alerts on to enable notifications\n"
                "Use /alerts off to disable notifications"
            )
        return
    
    action = context.args[0].lower()
    
    if action == "on":
        update_alerts_opt_in(user_id, True)
        await update.message.reply_text(
            "✅ Signal notifications **enabled**!\n\n"
            "You'll receive alerts for strong signals every 10 minutes (premium users only)."
        )
    elif action == "off":
        update_alerts_opt_in(user_id, False)
        await update.message.reply_text(
            "❌ Signal notifications **disabled**.\n\n"
            "Use /alerts on to re-enable."
        )
    else:
        await update.message.reply_text(
            "❌ Invalid option. Use /alerts on or /alerts off"
        )

async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /subscribe command with polling for confirmation"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Ensure user exists
    create_or_update_user(user_id, chat_id)
    
    # Get user from DB
    user = get_user(user_id)
    wallet = user[2] if user and user[2] else None
    
    if not wallet:
        text = "❌ No wallet connected.\n\n"
        text += "Please connect your wallet first:\n"
        text += "• Use /connect <your_wallet_address>\n"
        text += "• Or send your wallet address as a message"
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
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        return
    
    # Check if any payment method is enabled
    if not SUBSCRIBE_SOL_ENABLED and not SUBSCRIBE_USDC_ENABLED:
        text = "⚠️ Subscription temporarily disabled.\n\n"
        text += "Please check back later or contact support."
        await update.message.reply_text(text)
        return
    
    # Not premium - show payment instructions
    text = "🔓 Premium Subscription Required\n\n"
    text += "Subscribe to unlock:\n"
    text += "• Real-time boosted signals\n"
    text += "• Premium market analysis\n"
    text += "• Priority notifications\n\n"
    
    text += "💳 Payment Options:\n\n"
    
    # Show enabled payment methods from .env
    payment_options = []
    
    if SUBSCRIBE_SOL_ENABLED:
        payment_options.append(f"**SOL Payment:** Send `{SUBSCRIBE_SOL_AMOUNT} SOL` to\n`{FEE_WALLET}`")
    
    if SUBSCRIBE_USDC_ENABLED:
        payment_options.append(f"**USDC Payment:** Send `{SUBSCRIBE_USDC_AMOUNT} USDC` to\n`{FEE_WALLET}`")
    
    text += "\n\n".join(payment_options)
    text += "\n\n"
    
    text += "📱 **How to Subscribe:**\n"
    text += "1. Send payment using your wallet (Phantom/etc)\n"
    text += "2. I'll automatically detect and confirm subscription in a few minutes\n"
    text += "3. No dApp needed — just send and wait!\n\n"
    text += "⏳ Polling active — checking every 30 seconds..."
    
    status_msg = await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    
    # Start polling for subscription (up to 5 minutes = 10 attempts * 30 seconds)
    logger.info(f"Starting subscription polling for user {user_id}")
    
    async def poll_and_notify():
        is_premium, expires_at = await poll_subscription_status(wallet, max_attempts=10, interval=30)
        
        if is_premium and expires_at:
            success_text = f"✅ **Premium Active!**\n\n"
            success_text += f"Expires: {expires_at.strftime('%Y-%m-%d %H:%M:%S')} UTC\n\n"
            success_text += "🔔 Alerts are active. You'll receive signal notifications every 10 minutes.\n"
            success_text += "✨ You now have access to /signals and premium features!"
            await status_msg.edit_text(success_text, parse_mode=ParseMode.MARKDOWN)
        else:
            timeout_text = "⏱️ Subscription not detected yet.\n\n"
            timeout_text += "If you've already sent payment, it may take a few minutes to confirm.\n"
            timeout_text += "Try /subscribe again later or check your transaction status."
            await status_msg.edit_text(timeout_text, parse_mode=ParseMode.MARKDOWN)
    
    # Run polling in background
    asyncio.create_task(poll_and_notify())

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command - show wallet, premium status, alerts"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Ensure user exists
    create_or_update_user(user_id, chat_id)
    
    # Get user from DB
    user = get_user(user_id)
    wallet = user[2] if user and user[2] else None
    alerts_opt_in = bool(user[3]) if user else True
    
    text = "📊 **Your Status**\n\n"
    
    # Wallet status
    if wallet:
        text += f"🔗 **Wallet:** `{wallet[:8]}...{wallet[-8:]}`\n"
    else:
        text += "🔗 **Wallet:** Not connected\n"
        text += "Use /connect <pubkey> to connect\n"
    
    text += "\n"
    
    # Premium status
    if wallet:
        is_premium, expires_at = await check_premium_status(wallet)
        if is_premium and expires_at:
            text += f"⭐ **Premium:** Active\n"
            text += f"📅 **Expires:** {expires_at.strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
        else:
            text += "⭐ **Premium:** Not active\n"
            text += "Use /subscribe to get premium access\n"
    else:
        text += "⭐ **Premium:** Connect wallet first\n"
    
    text += "\n"
    
    # Alerts status
    alerts_status = "enabled" if alerts_opt_in else "disabled"
    alerts_emoji = "✅" if alerts_opt_in else "❌"
    text += f"{alerts_emoji} **Alerts:** {alerts_status}\n"
    text += "Use /alerts on/off to toggle\n"
    
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
    
    # Get user from DB
    user = get_user(user_id)
    wallet = user[2] if user and user[2] else None
    
    if not wallet:
        await update.message.reply_text(
            "❌ Premium feature. Please connect wallet and subscribe.\n\n"
            "Use /connect <pubkey> to connect wallet"
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
    """Handle wallet address messages (fallback for /connect)"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    wallet_address = update.message.text.strip()
    
    # Basic validation (Solana addresses are base58, 32-44 chars)
    if len(wallet_address) < 32 or len(wallet_address) > 44:
        await update.message.reply_text(
            "❌ Invalid wallet address format.\n\n"
            "Please send a valid Solana wallet address (32-44 characters)\n"
            "Or use /connect <pubkey>"
        )
        return
    
    # Try to validate as base58
    try:
        base58.b58decode(wallet_address)
        Pubkey.from_string(wallet_address)
        
        # Save to database
        create_or_update_user(user_id, chat_id, wallet_pubkey=wallet_address)
        
        await update.message.reply_text(
            f"✅ Wallet connected!\n\n"
            f"Address: `{wallet_address}`\n\n"
            f"Use /subscribe to check premium status"
        )
    except Exception:
        await update.message.reply_text(
            "❌ Invalid wallet address. Please send a valid Solana address.\n"
            "Or use /connect <pubkey>"
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button callbacks"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "markets":
        # Trigger markets command
        update.message = query.message
        await markets_command(update, context)
    elif query.data == "help":
        # Trigger help command
        update.message = query.message
        await help_command(update, context)

async def background_signal_pusher(context: ContextTypes.DEFAULT_TYPE):
    """Background job to push signals to opted-in premium users every 10 minutes"""
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
    
    if not current_signals:
        logger.info("No strong signals found")
        return
    
    # Get opted-in premium users from DB
    users = get_opted_in_premium_users()
    sent_count = 0
    
    for user_id, chat_id, wallet in users:
        try:
            # Check if user has premium
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
                    chat_id=chat_id,
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
    
    # Initialize database
    init_database()
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("connect", connect_command))
    application.add_handler(CommandHandler("alerts", alerts_command))
    application.add_handler(CommandHandler("subscribe", subscribe_command))
    application.add_handler(CommandHandler("markets", markets_command))
    application.add_handler(CommandHandler("boost", boost_command))
    application.add_handler(CommandHandler("signals", signals_command))
    
    # Add callback handler for inline buttons
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Add message handler for wallet addresses (fallback)
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
