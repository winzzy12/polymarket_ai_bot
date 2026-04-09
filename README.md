# polymarket_ai_bot
Happy Trading! 🚀


# Polymarket AI Trading Bot

An automated trading bot for Polymarket's "Bitcoin Up or Down – 5 Minutes" market, powered by AI analysis of real-time Bitcoin data.

## Features

- 🤖 **AI-Powered Decisions**: Uses GPT-4 to analyze market conditions and predict Bitcoin movements
- 📊 **Real-time Data**: Fetches live BTC prices and Polymarket odds
- 🔧 **Technical Analysis**: Calculates RSI, MACD, EMA, volatility, and momentum
- 💰 **Risk Management**: Dynamic position sizing, stop-loss, daily limits, and drawdown protection
- ⛓️ **On-chain Execution**: Direct Polygon network integration for trade execution
- 📝 **Comprehensive Logging**: Detailed logs for debugging and performance tracking
- 🛡️ **Safety Features**: Cooldown periods, volatility filters, and spread checks

## Prerequisites

- Python 3.11 or higher
- Polygon wallet with MATIC for gas fees
- USDC balance for trading
- OpenAI API key

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/winzzy12/polymarket_ai_bot.git
cd polymarket-ai-bot
```

python -m venv venv

# On Windows
```bash
venv\Scripts\activate
```
# On Linux/Mac
```bash
source venv/bin/activate
```
# Install dependencies
```bash
pip install -r requirements.txt
```
# Create a .env file in the project root
```bash
# Wallet Configuration
WALLET_PRIVATE_KEY=your_private_key_here
WALLET_ADDRESS=your_wallet_address_here

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
```

# Run the bot
```bash
python bot.py
```

# Monitor logs

# View live logs
```bash
tail -f logs/trading_log.txt
```

# On Windows
```Bash
Get-Content logs/trading_log.txt -Wait
```

# Risk Management Settings
```bash
DEFAULT_TRADE_SIZE_PERCENT = 0.02      # 2% of balance
HIGH_CONFIDENCE_TRADE_SIZE = 0.04       # 4% on high confidence
MAX_TRADES_PER_HOUR = 10                # Maximum hourly trades
DAILY_STOP_LOSS_PERCENT = 0.10          # 10% daily loss limit
DAILY_PROFIT_TARGET_PERCENT = 0.20      # 20% daily profit target
```



