"""
Polymarket market data module
Fetches real-time market information from Polymarket
"""

import requests
from typing import Dict, Optional, List, Tuple
from datetime import datetime
from logger import trading_logger

class PolymarketMarket:
    def __init__(self, api_base_url: str = "https://gamma-api.polymarket.com"):
        """
        Initialize Polymarket market connector
        
        Args:
            api_base_url: Base URL for Polymarket Gamma API
        """
        self.api_base_url = api_base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Polymarket-Trading-Bot/1.0'
        })
        
    def find_market(self, market_slug: str) -> Optional[Dict]:
        """
        Find a market by its slug name
        
        Args:
            market_slug: The market identifier (e.g., "bitcoin-up-or-down-5-minutes")
            
        Returns:
            Market data dictionary or None if not found
        """
        try:
            # Search for markets
            url = f"{self.api_base_url}/markets"
            params = {
                'slug': market_slug,
                'limit': 10,
                'active': 'true'
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            markets = response.json()
            
            if markets and len(markets) > 0:
                market = markets[0]
                trading_logger.info(f"Found market: {market.get('question')} (ID: {market.get('id')})")
                return market
            else:
                trading_logger.warning(f"Market not found: {market_slug}")
                return None
                
        except requests.RequestException as e:
            trading_logger.error(f"Error finding market: {e}")
            return None
            
    def get_market_prices(self, market_id: str) -> Optional[Dict]:
        """
        Get current YES/NO prices for a market
        
        Args:
            market_id: The market identifier
            
        Returns:
            Dictionary with YES price, NO price, liquidity, volume
        """
        try:
            # Get market prices from Polymarket
            url = f"{self.api_base_url}/markets/{market_id}"
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            market_data = response.json()
            
            # Extract prices from the market data
            # Note: Polymarket API structure may vary
            yes_price = float(market_data.get('yesPrice', 0.5))
            no_price = 1.0 - yes_price
            
            # Get additional market stats
            volume = float(market_data.get('volume', 0))
            liquidity = float(market_data.get('liquidity', 0))
            
            # Get bid/ask spreads if available
            spread = abs(yes_price - 0.5) * 2  # Approximate spread calculation
            
            result = {
                'yes_price': yes_price,
                'no_price': no_price,
                'volume': volume,
                'liquidity': liquidity,
                'spread': spread,
                'timestamp': datetime.now().isoformat()
            }
            
            trading_logger.debug(f"Market prices - YES: {yes_price:.3f}, NO: {no_price:.3f}")
            return result
            
        except requests.RequestException as e:
            trading_logger.error(f"Error fetching market prices: {e}")
            return None
            
    def get_order_book(self, market_id: str, token_id: str) -> Optional[Dict]:
        """
        Get order book for a specific token in a market
        
        Args:
            market_id: Market identifier
            token_id: Token identifier (YES or NO token)
            
        Returns:
            Order book data
        """
        try:
            url = f"{self.api_base_url}/markets/{market_id}/orderbook/{token_id}"
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            order_book = response.json()
            return order_book
            
        except requests.RequestException as e:
            trading_logger.error(f"Error fetching order book: {e}")
            return None
            
    def get_market_history(self, market_id: str, limit: int = 100) -> Optional[List[Dict]]:
        """
        Get historical price data for a market
        
        Args:
            market_id: Market identifier
            limit: Number of historical records to fetch
            
        Returns:
            List of historical price points
        """
        try:
            url = f"{self.api_base_url}/markets/{market_id}/prices"
            params = {'limit': limit}
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            history = response.json()
            return history
            
        except requests.RequestException as e:
            trading_logger.error(f"Error fetching market history: {e}")
            return None
            
    def get_available_markets(self, limit: int = 50) -> List[Dict]:
        """
        Get list of available markets for discovery
        
        Args:
            limit: Maximum number of markets to return
            
        Returns:
            List of market dictionaries
        """
        try:
            url = f"{self.api_base_url}/markets"
            params = {
                'active': 'true',
                'limit': limit,
                'sort': 'volume'
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            markets = response.json()
            trading_logger.info(f"Retrieved {len(markets)} active markets")
            return markets
            
        except requests.RequestException as e:
            trading_logger.error(f"Error fetching markets list: {e}")
            return []
