# $EDGEAI Prediction Booster Backend

FastAPI backend for boosting prediction market probabilities using sentiment analysis and price momentum data.

## Features

- **Market Data**: Fetch active markets from Polymarket Gamma API
- **Boosted Probabilities**: Calculate enhanced probabilities using:
  - Market base probability
  - Sentiment analysis (keyword-based)
  - Price momentum from Pyth Network
- **Signals**: Generate buy/sell/neutral signals based on boosted probabilities

## Setup

### Prerequisites

Make sure you have Python 3.11+ and pip installed. On Debian/Ubuntu:

```bash
sudo apt install python3 python3-pip python3-venv
```

### Install Dependencies

**Option 1: Using the run script (recommended)**
```bash
./run.sh
```

**Option 2: Manual setup**
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Environment Variables

Copy `.env.example` to `.env` and configure if needed:

```bash
cp .env.example .env
```

Currently, no API keys are required for MVP (using public APIs).

## Running Locally

```bash
# Development mode with auto-reload
uvicorn main:app --reload

# Production mode
uvicorn main:app --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

## API Endpoints

### `GET /`
Health check endpoint

### `GET /markets?category=crypto&limit=50`
Fetch active markets from Polymarket

**Query Parameters:**
- `category` (optional): Market category filter (default: "crypto")
- `limit` (optional): Maximum number of markets (default: 50, max: 100)

**Response:**
```json
[
  {
    "slug": "will-btc-hit-100k-by-2024",
    "question": "Will BTC hit $100k by 2024?",
    "yes_prob": 0.65,
    "no_prob": 0.35,
    "volume": 50000.0,
    "end_date": "2024-12-31T23:59:59Z"
  }
]
```

### `GET /boost_prob?market_slug=...&market_prob=0.65`
Calculate boosted probability for a market

**Query Parameters:**
- `market_slug` (required): Polymarket market slug
- `market_prob` (optional): Market yes probability (if not provided, fetched from API)

**Response:**
```json
{
  "market_slug": "will-btc-hit-100k-by-2024",
  "market_prob": 0.65,
  "boosted_prob": 0.72,
  "signal": "buy_yes",
  "sentiment_score": 0.3,
  "price_momentum": 0.15,
  "timestamp": "2024-01-27T12:00:00"
}
```

### `GET /price/{symbol}`
Get current price from Pyth Network (BTC, ETH, SOL)

**Response:**
```json
{
  "symbol": "BTC",
  "price": 42000.50,
  "timestamp": "2024-01-27T12:00:00"
}
```

## API Documentation

Once the server is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Boosted Probability Formula

```
boosted_prob = market_prob + (sentiment * 0.15) + (price_momentum * 0.1)
```

Where:
- `market_prob`: Base probability from Polymarket (0-1)
- `sentiment`: Sentiment score from keyword analysis (-1 to 1)
- `price_momentum`: Price change momentum from Pyth Network (-1 to 1)

The result is clamped between 0 and 1.

## Signal Logic

- `buy_yes`: boosted_prob > market_prob + 0.05
- `sell_yes`: boosted_prob < market_prob - 0.05
- `neutral`: Otherwise

## Future Enhancements

- [ ] ML-based sentiment analysis (Hugging Face transformers)
- [ ] Historical price data for better momentum calculation
- [ ] Caching layer (Redis)
- [ ] Rate limiting
- [ ] Authentication/API keys
- [ ] WebSocket support for real-time updates
- [ ] Integration with $EDGEAI Solana program

## Deployment

### Vercel
```bash
vercel deploy
```

### Railway
```bash
railway up
```

### Docker
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```
