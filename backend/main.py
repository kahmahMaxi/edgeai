from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import requests
import os
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="$EDGEAI Prediction Booster API",
    description="Backend API for boosting prediction market probabilities using sentiment and price data",
    version="1.0.0"
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class Market(BaseModel):
    slug: str
    question: str
    yes_prob: float
    no_prob: float
    volume: float
    end_date: Optional[str] = None

class BoostedProb(BaseModel):
    market_slug: str
    market_prob: float
    boosted_prob: float
    signal: str
    sentiment_score: float
    price_momentum: float
    timestamp: str

# Constants
POLYMARKET_GAMMA_API = "https://gamma-api.polymarket.com"
PYTH_HTTP_API = "https://hermes.pyth.network/v2/updates/price/latest"

# Price feed IDs (Pyth Network)
PYTH_FEEDS = {
    "BTC": "0xe62df6c8b4a85fe1a67db44dc12de5db330f7ac66b72dc658afedf0f4a415b43",
    "ETH": "0xff61491a931112ddf1bd8147cd1b641375f79f5825126d665480874634fd0ace",
    "SOL": "0xef0d8b6fda2ceba41da15d4095d1da392a0d2f8ed0c6c7bc0f4cfac8c280b56d",
}

# Cache for price data (simple in-memory cache)
price_cache = {}
cache_timestamp = {}

def get_polymarket_markets(category: str = "crypto", limit: int = 50) -> List[dict]:
    """
    Fetch active markets from Polymarket Gamma API
    """
    try:
        url = f"{POLYMARKET_GAMMA_API}/markets"
        params = {
            "active": "true",
            "closed": "false",
            "limit": limit,
        }
        
        # Filter by category if provided
        if category:
            params["category"] = category
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        markets = []
        for market in data.get("data", []):
            # Extract key information
            slug = market.get("slug", "")
            question = market.get("question", "")
            
            # Get market prices (yes/no)
            outcomes = market.get("outcomes", [])
            yes_price = 0.0
            no_price = 0.0
            
            for outcome in outcomes:
                if outcome.get("title", "").lower() in ["yes", "true"]:
                    yes_price = float(outcome.get("price", 0))
                elif outcome.get("title", "").lower() in ["no", "false"]:
                    no_price = float(outcome.get("price", 0))
            
            # Calculate probabilities
            total = yes_price + no_price
            yes_prob = yes_price / total if total > 0 else 0.5
            no_prob = no_price / total if total > 0 else 0.5
            
            # Get volume
            volume = float(market.get("volume", 0))
            
            # Get end date
            end_date = market.get("endDate", None)
            
            # Filter for high volume markets (volume > 1000)
            if volume > 1000:
                markets.append({
                    "slug": slug,
                    "question": question,
                    "yes_prob": round(yes_prob, 4),
                    "no_prob": round(no_prob, 4),
                    "volume": volume,
                    "end_date": end_date
                })
        
        # Sort by volume descending
        markets.sort(key=lambda x: x["volume"], reverse=True)
        return markets[:limit]
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Polymarket data: {e}")
        raise HTTPException(status_code=503, detail="Failed to fetch market data from Polymarket")

def get_pyth_price(symbol: str) -> Optional[float]:
    """
    Fetch current price from Pyth Network
    Uses Pyth's public HTTP API
    """
    try:
        feed_id = PYTH_FEEDS.get(symbol.upper())
        if not feed_id:
            logger.warning(f"No Pyth feed ID for {symbol}")
            return None
        
        # Pyth HTTP API format
        url = f"{PYTH_HTTP_API}"
        params = {"ids[]": feed_id}
        headers = {"Accept": "application/json"}
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Parse Pyth response - structure may vary, try multiple formats
        if "parsed" in data and len(data["parsed"]) > 0:
            price_data = data["parsed"][0]
            if "price" in price_data:
                price_info = price_data["price"]
                price = float(price_info.get("price", 0))
                exponent = price_info.get("expo", -8)  # Default -8 for most feeds
                actual_price = price * (10 ** exponent)
                return actual_price
        
        # Alternative: try direct price field
        if "price" in data:
            price_info = data["price"]
            price = float(price_info.get("price", 0))
            exponent = price_info.get("expo", -8)
            actual_price = price * (10 ** exponent)
            return actual_price
        
        logger.warning(f"Could not parse Pyth response for {symbol}")
        return None
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Pyth price for {symbol}: {e}")
        # Fallback: return None, will use 0 momentum
        return None
    except (KeyError, ValueError, TypeError) as e:
        logger.error(f"Error parsing Pyth price for {symbol}: {e}")
        return None

def calculate_price_momentum(symbol: str) -> float:
    """
    Calculate price momentum (simplified: compare current price to cached price)
    Returns value between -1 and 1
    """
    current_price = get_pyth_price(symbol)
    if current_price is None:
        return 0.0
    
    # Check cache
    cache_key = f"{symbol}_price"
    if cache_key in price_cache and cache_key in cache_timestamp:
        # Check if cache is recent (within last hour)
        cache_age = (datetime.now().timestamp() - cache_timestamp[cache_key]) / 3600
        if cache_age < 1.0:
            previous_price = price_cache[cache_key]
            if previous_price > 0:
                momentum = (current_price - previous_price) / previous_price
                # Normalize to -1 to 1 range (clamp at ±10% change)
                momentum = max(-1.0, min(1.0, momentum * 10))
                return momentum
    
    # Update cache
    price_cache[cache_key] = current_price
    cache_timestamp[cache_key] = datetime.now().timestamp()
    
    return 0.0  # No previous data, return neutral

def get_sentiment_score(market_slug: str, question: str) -> float:
    """
    Calculate sentiment score for a market
    Simple keyword-based approach (can be replaced with ML model later)
    Returns value between -1 and 1
    """
    # Positive keywords
    positive_keywords = [
        "pump", "surge", "rally", "bullish", "up", "rise", "gain",
        "breakout", "moon", "soar", "climb", "increase", "growth"
    ]
    
    # Negative keywords
    negative_keywords = [
        "dump", "crash", "bearish", "down", "fall", "drop", "decline",
        "plunge", "tank", "sink", "decrease", "loss", "correction"
    ]
    
    text = (market_slug + " " + question).lower()
    
    positive_count = sum(1 for keyword in positive_keywords if keyword in text)
    negative_count = sum(1 for keyword in negative_keywords if keyword in text)
    
    # Calculate sentiment (-1 to 1)
    if positive_count + negative_count == 0:
        return 0.0
    
    sentiment = (positive_count - negative_count) / max(positive_count + negative_count, 1)
    
    # Normalize to -1 to 1 range
    return max(-1.0, min(1.0, sentiment))

def calculate_boosted_probability(
    market_slug: str,
    question: str,
    market_yes_prob: float
) -> dict:
    """
    Calculate boosted probability using sentiment and price momentum
    """
    # Extract asset symbol from market (simple heuristic)
    symbol = "BTC"  # default
    if "btc" in market_slug.lower() or "bitcoin" in question.lower():
        symbol = "BTC"
    elif "eth" in market_slug.lower() or "ethereum" in question.lower():
        symbol = "ETH"
    elif "sol" in market_slug.lower() or "solana" in question.lower():
        symbol = "SOL"
    
    # Get sentiment score
    sentiment_score = get_sentiment_score(market_slug, question)
    
    # Get price momentum
    price_momentum = calculate_price_momentum(symbol)
    
    # Calculate boosted probability
    # Formula: market_prob + (sentiment * 0.15) + (price_momentum * 0.1)
    boosted_prob = market_yes_prob + (sentiment_score * 0.15) + (price_momentum * 0.1)
    
    # Clamp between 0 and 1
    boosted_prob = max(0.0, min(1.0, boosted_prob))
    
    # Determine signal
    if boosted_prob > market_yes_prob + 0.05:
        signal = "buy_yes"
    elif boosted_prob < market_yes_prob - 0.05:
        signal = "sell_yes"
    else:
        signal = "neutral"
    
    return {
        "market_prob": round(market_yes_prob, 4),
        "boosted_prob": round(boosted_prob, 4),
        "signal": signal,
        "sentiment_score": round(sentiment_score, 4),
        "price_momentum": round(price_momentum, 4),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "$EDGEAI Prediction Booster API",
        "version": "1.0.0"
    }

@app.get("/markets", response_model=List[Market])
async def get_markets(
    category: str = Query("crypto", description="Market category filter"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of markets to return")
):
    """
    Fetch active markets from Polymarket
    
    - **category**: Filter by category (default: crypto)
    - **limit**: Maximum number of markets (default: 50, max: 100)
    
    Returns list of markets with slug, question, yes/no probabilities, and volume
    """
    try:
        markets = get_polymarket_markets(category=category, limit=limit)
        return [Market(**market) for market in markets]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in /markets: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/boost_prob", response_model=BoostedProb)
async def get_boosted_probability(
    market_slug: str = Query(..., description="Polymarket market slug"),
    market_prob: Optional[float] = Query(None, ge=0.0, le=1.0, description="Market yes probability (if not provided, will fetch from Polymarket)")
):
    """
    Calculate boosted probability for a market
    
    - **market_slug**: Polymarket market slug
    - **market_prob**: Optional market probability (if not provided, fetched from API)
    
    Returns boosted probability with signal recommendation
    """
    try:
        # If market_prob not provided, fetch from Polymarket
        if market_prob is None:
            markets = get_polymarket_markets(category="crypto", limit=100)
            market_data = next((m for m in markets if m["slug"] == market_slug), None)
            
            if not market_data:
                raise HTTPException(
                    status_code=404,
                    detail=f"Market '{market_slug}' not found"
                )
            
            market_prob = market_data["yes_prob"]
            question = market_data["question"]
        else:
            # Fetch question from market
            markets = get_polymarket_markets(category="crypto", limit=100)
            market_data = next((m for m in markets if m["slug"] == market_slug), None)
            question = market_data.get("question", "") if market_data else ""
        
        # Calculate boosted probability
        result = calculate_boosted_probability(market_slug, question, market_prob)
        
        return BoostedProb(
            market_slug=market_slug,
            **result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in /boost_prob: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/price/{symbol}")
async def get_price(symbol: str):
    """
    Get current price for a symbol (BTC, ETH, SOL) from Pyth Network
    """
    price = get_pyth_price(symbol.upper())
    if price is None:
        raise HTTPException(status_code=404, detail=f"Price not found for {symbol}")
    return {"symbol": symbol.upper(), "price": price, "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
