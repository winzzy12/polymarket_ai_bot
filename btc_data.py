"""
Bitcoin price data module
Fetches real-time BTC price and historical data from Binance
"""

import requests
import pandas as pd
import pandas_ta as ta
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
import time
from logger import trading_logger

class BTCDataFetcher:
    def __init__(self, api_base_url: str = "https://api.binance.com"):
        """
        Initialize BTC data fetcher
        
        Args:
            api_base_url: Binance API base URL
        """
        self.api_base_url = api_base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Polymarket-BTC-Bot/1.0'
        })
        self.historical_data = None
        
    def get_current_price(self) -> Optional[float]:
        """
        Get current Bitcoin price from Binance
        
        Returns:
            Current BTC price in USDT
        """
        try:
            url = f"{self.api_base_url}/api/v3/ticker/price"
            params = {'symbol': 'BTCUSDT'}
            
            response = self.session.get(url, params=params, timeout=5)
            response.raise_for_status()
            
            data = response.json()
            price = float(data['price'])
            
            trading_logger.debug(f"Current BTC price: ${price:,.2f}")
            return price
            
        except requests.RequestException as e:
            trading_logger.error(f"Error fetching BTC price: {e}")
            return None
            
    def get_price_change(self, minutes: int = 1) -> Optional[Tuple[float, float]]:
        """
        Calculate price change over specified minutes
        
        Args:
            minutes: Number of minutes to look back
            
        Returns:
            Tuple of (price_change_percentage, price_change_absolute)
        """
        try:
            # Get kline/candlestick data
            url = f"{self.api_base_url}/api/v3/klines"
            params = {
                'symbol': 'BTCUSDT',
                'interval': '1m',
                'limit': minutes + 1
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            klines = response.json()
            
            if len(klines) >= 2:
                current_price = float(klines[-1][4])  # Close price
                past_price = float(klines[0][4])       # Close price from minutes ago
                
                price_change_abs = current_price - past_price
                price_change_percent = (price_change_abs / past_price) * 100
                
                return (price_change_percent, price_change_abs)
            else:
                return (0.0, 0.0)
                
        except requests.RequestException as e:
            trading_logger.error(f"Error calculating price change: {e}")
            return (0.0, 0.0)
            
    def get_historical_data(self, lookback_minutes: int = 100) -> Optional[pd.DataFrame]:
        """
        Fetch historical price data for technical analysis
        
        Args:
            lookback_minutes: Number of minutes of historical data
            
        Returns:
            DataFrame with OHLCV data
        """
        try:
            url = f"{self.api_base_url}/api/v3/klines"
            params = {
                'symbol': 'BTCUSDT',
                'interval': '1m',
                'limit': lookback_minutes
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            klines = response.json()
            
            # Convert to DataFrame
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            
            # Convert to numeric
            df['close'] = pd.to_numeric(df['close'])
            df['open'] = pd.to_numeric(df['open'])
            df['high'] = pd.to_numeric(df['high'])
            df['low'] = pd.to_numeric(df['low'])
            df['volume'] = pd.to_numeric(df['volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            df.set_index('timestamp', inplace=True)
            
            self.historical_data = df
            trading_logger.debug(f"Retrieved {len(df)} minutes of historical BTC data")
            return df
            
        except requests.RequestException as e:
            trading_logger.error(f"Error fetching historical data: {e}")
            return None
            
    def calculate_indicators(self, df: pd.DataFrame) -> Dict:
        """
        Calculate technical indicators using pandas-ta
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            Dictionary with latest indicator values
        """
        if df is None or len(df) < 50:
            trading_logger.warning("Insufficient data for indicator calculation")
            return {}
            
        try:
            # RSI (Relative Strength Index)
            rsi = ta.rsi(df['close'], length=14)
            current_rsi = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
            
            # MACD (Moving Average Convergence Divergence)
            macd = ta.macd(df['close'])
            current_macd = macd['MACD_12_26_9'].iloc[-1] if 'MACD_12_26_9' in macd.columns else 0
            current_macd_signal = macd['MACDs_12_26_9'].iloc[-1] if 'MACDs_12_26_9' in macd.columns else 0
            macd_histogram = current_macd - current_macd_signal
            
            # EMA (Exponential Moving Average)
            ema_9 = ta.ema(df['close'], length=9)
            ema_21 = ta.ema(df['close'], length=21)
            current_ema_9 = ema_9.iloc[-1] if not pd.isna(ema_9.iloc[-1]) else df['close'].iloc[-1]
            current_ema_21 = ema_21.iloc[-1] if not pd.isna(ema_21.iloc[-1]) else df['close'].iloc[-1]
            
            # Volatility (standard deviation of returns)
            returns = df['close'].pct_change()
            volatility = returns.std() * 100  # Percentage volatility
            current_volatility = volatility if not pd.isna(volatility) else 0
            
            # Momentum
            momentum = ta.mom(df['close'], length=10)
            current_momentum = momentum.iloc[-1] if not pd.isna(momentum.iloc[-1]) else 0
            
            # Bollinger Bands
            bb = ta.bbands(df['close'], length=20, std=2)
            current_bb_upper = bb['BBU_20_2.0'].iloc[-1] if 'BBU_20_2.0' in bb.columns else df['close'].iloc[-1]
            current_bb_lower = bb['BBL_20_2.0'].iloc[-1] if 'BBL_20_2.0' in bb.columns else df['close'].iloc[-1]
            bb_position = (df['close'].iloc[-1] - current_bb_lower) / (current_bb_upper - current_bb_lower)
            
            indicators = {
                'rsi': round(current_rsi, 2),
                'macd': round(current_macd, 4),
                'macd_signal': round(current_macd_signal, 4),
                'macd_histogram': round(macd_histogram, 4),
                'ema_9': round(current_ema_9, 2),
                'ema_21': round(current_ema_21, 2),
                'volatility': round(current_volatility, 4),
                'momentum': round(current_momentum, 4),
                'bb_position': round(bb_position, 3),
                'current_price': df['close'].iloc[-1]
            }
            
            return indicators
            
        except Exception as e:
            trading_logger.error(f"Error calculating indicators: {e}")
            return {}
            
    def get_complete_analysis(self) -> Dict:
        """
        Get complete BTC analysis including current price, changes, and indicators
        
        Returns:
            Dictionary with all BTC market data
        """
        # Get current price
        current_price = self.get_current_price()
        if not current_price:
            return {}
            
        # Get price changes
        change_1m_abs, change_1m_percent = self.get_price_change(1)
        change_5m_abs, change_5m_percent = self.get_price_change(5)
        
        # Get historical data and calculate indicators
        historical_df = self.get_historical_data(100)
        indicators = self.calculate_indicators(historical_df) if historical_df is not None else {}
        
        analysis = {
            'current_price': current_price,
            'change_1m_percent': round(change_1m_percent, 2),
            'change_1m_abs': round(change_1m_abs, 2),
            'change_5m_percent': round(change_5m_percent, 2),
            'change_5m_abs': round(change_5m_abs, 2),
            'timestamp': datetime.now().isoformat(),
            **indicators
        }
        
        return analysis
