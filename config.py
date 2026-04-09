"""
Configuration file for Polymarket AI Trading Bot
All settings are centralized here for easy management
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    # ===== WALLET CONFIGURATION =====
    # Polygon network configuration
    POLYGON_RPC_URL = "https://polygon-rpc.com"
    POLYGON_CHAIN_ID = 137
    
    # Your wallet private key (store in .env file for security)
    WALLET_PRIVATE_KEY = os.getenv("WALLET_PRIVATE_KEY", "")
    WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "")
    
    # ===== AI MODEL CONFIGURATION =====
    # OpenAI configuration (or other LLM)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    AI_MODEL = "gpt-4"  # or "gpt-3.5-turbo"
    AI_TEMPERATURE = 0.3
    
    # ===== TRADING CONFIGURATION =====
    # Position sizing
    DEFAULT_TRADE_SIZE_PERCENT = 0.02  # 2% of wallet balance
    HIGH_CONFIDENCE_TRADE_SIZE = 0.04   # 4% of wallet balance
    CONFIDENCE_THRESHOLD_HIGH = 0.7
    CONFIDENCE_THRESHOLD_SKIP = 0.55
    
    # Risk management
    MAX_TRADES_PER_HOUR = 10
    DAILY_STOP_LOSS_PERCENT = 0.10      # 10% daily loss limit
    DAILY_PROFIT_TARGET_PERCENT = 0.20  # 20% daily profit target
    
    # Safety features
    MAX_VOLATILITY_THRESHOLD = 0.05     # 5% max volatility
    MAX_SPREAD_PERCENT = 0.02           # 2% max spread
    COOLDOWN_MINUTES_AFTER_LOSS = 5
    
    # ===== API ENDPOINTS =====
    POLYMARKET_GAMMA_API = "https://gamma-api.polymarket.com"
    POLYMARKET_CLOB_API = "https://clob.polymarket.com"
    BINANCE_API_URL = "https://api.binance.com"
    
    # Polymarket contract addresses (mainnet)
    CTF_EXCHANGE_ADDRESS = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
    NEG_RISK_ADAPTER_ADDRESS = "0xd91E80cF2E7be2e162c4653eA01dF06E3dAeF963"
    
    # ===== MARKET IDENTIFIERS =====
    # You may need to update these IDs periodically
    # "Bitcoin Up or Down – 5 Minutes" market
    MARKET_SLUG = "bitcoin-up-or-down-5-minutes"
    
    # ===== BOT CONFIGURATION =====
    BOT_LOOP_INTERVAL_SECONDS = 30
    ENABLE_AI_DECISION = True
    DRY_RUN_MODE = False  # If True, simulate trades without execution
    
    # ===== LOGGING =====
    LOG_FILE_PATH = "logs/trading_log.txt"
    LOG_LEVEL = "INFO"
    
    @classmethod
    def validate(cls):
        """Validate critical configuration"""
        if not cls.WALLET_PRIVATE_KEY and not cls.DRY_RUN_MODE:
            raise ValueError("WALLET_PRIVATE_KEY not set in environment variables")
        if not cls.OPENAI_API_KEY and cls.ENABLE_AI_DECISION:
            raise ValueError("OPENAI_API_KEY not set in environment variables")
        return True
