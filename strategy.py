"""
Trading strategy module
Combines AI decisions with additional logic and filters
"""

from typing import Dict, Tuple
from datetime import datetime, timedelta
from collections import deque
from logger import trading_logger

class TradingStrategy:
    def __init__(self, config):
        """
        Initialize trading strategy with risk rules
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.trade_history = deque(maxlen=100)
        self.hourly_trades = deque(maxlen=config.MAX_TRADES_PER_HOUR)
        self.daily_pnl = 0.0
        self.daily_trade_count = 0
        self.last_trade_time = None
        self.consecutive_losses = 0
        self.cooldown_until = None
        
    def check_risk_limits(self) -> Tuple[bool, str]:
        """
        Check all risk limits before trading
        
        Returns:
            (can_trade, reason) tuple
        """
        current_time = datetime.now()
        
        # Check cooldown period
        if self.cooldown_until and current_time < self.cooldown_until:
            remaining = (self.cooldown_until - current_time).seconds // 60
            return False, f"Cooldown active: {remaining} minutes remaining"
        
        # Check hourly trade limit
        self.clean_hourly_trades(current_time)
        if len(self.hourly_trades) >= self.config.MAX_TRADES_PER_HOUR:
            return False, f"Hourly trade limit reached ({self.config.MAX_TRADES_PER_HOUR})"
        
        # Check daily stop loss
        if self.daily_pnl <= -self.config.DAILY_STOP_LOSS_PERCENT * 10000:  # Assuming 10000 USDC starting balance
            return False, f"Daily stop loss reached: {self.daily_pnl:.2f} USDC"
        
        # Check daily profit target
        if self.daily_pnl >= self.config.DAILY_PROFIT_TARGET_PERCENT * 10000:
            return True, "Daily profit target reached - continuing with caution"
        
        # Check consecutive losses
        if self.consecutive_losses >= 3:
            return False, f"Too many consecutive losses ({self.consecutive_losses})"
        
        return True, "All risk limits OK"
    
    def clean_hourly_trades(self, current_time: datetime):
        """Remove trades older than 1 hour"""
        cutoff_time = current_time - timedelta(hours=1)
        self.hourly_trades = deque(
            [t for t in self.hourly_trades if t['timestamp'] > cutoff_time],
            maxlen=self.config.MAX_TRADES_PER_HOUR
        )
    
    def calculate_position_size(self, balance: float, confidence: float) -> float:
        """
        Calculate position size based on confidence and balance
        
        Args:
            balance: Current wallet balance in USDC
            confidence: AI confidence score (0-1)
            
        Returns:
            Position size in USDC
        """
        if confidence < self.config.CONFIDENCE_THRESHOLD_SKIP:
            return 0.0
        
        # Base position size
        if confidence > self.config.CONFIDENCE_THRESHOLD_HIGH:
            position_percent = self.config.HIGH_CONFIDENCE_TRADE_SIZE
        else:
            position_percent = self.config.DEFAULT_TRADE_SIZE_PERCENT
        
        position_size = balance * position_percent
        
        # Additional position sizing adjustments
        # Reduce size during high volatility
        # This will be set from outside
        return position_size
    
    def apply_safety_filters(self, btc_data: Dict, market_data: Dict) -> Tuple[bool, str]:
        """
        Apply additional safety filters before trading
        
        Args:
            btc_data: Bitcoin market data
            market_data: Polymarket market data
            
        Returns:
            (can_trade, reason) tuple
        """
        # Check volatility
        volatility = btc_data.get('volatility', 0)
        if volatility > self.config.MAX_VOLATILITY_THRESHOLD * 100:
            return False, f"Volatility too high: {volatility:.2f}% > {self.config.MAX_VOLATILITY_THRESHOLD*100}%"
        
        # Check spread
        spread = market_data.get('spread', 0)
        if spread > self.config.MAX_SPREAD_PERCENT:
            return False, f"Spread too wide: {spread:.3f} > {self.config.MAX_SPREAD_PERCENT}"
        
        # Check liquidity
        liquidity = market_data.get('liquidity', 0)
        if liquidity < 1000:  # Minimum liquidity threshold
            return False, f"Low liquidity: ${liquidity:,.0f}"
        
        # Check if price is too extreme (arbitrage check)
        yes_price = market_data.get('yes_price', 0.5)
        if yes_price > 0.95 or yes_price < 0.05:
            return False, f"Extreme price: {yes_price:.3f} (risk of market manipulation)"
        
        # Additional technical filters
        rsi = btc_data.get('rsi', 50)
        
        # Avoid buying when RSI is extremely overbought for YES
        if rsi > 85:
            return False, f"RSI extremely overbought: {rsi}"
        
        # Avoid buying NO when RSI is extremely oversold
        if rsi < 15:
            return False, f"RSI extremely oversold: {rsi}"
        
        return True, "Safety checks passed"
    
    def should_trade(self, ai_decision: Dict, btc_data: Dict, 
                     market_data: Dict, balance: float) -> Tuple[bool, str, float]:
        """
        Comprehensive decision on whether to trade
        
        Args:
            ai_decision: AI decision dictionary
            btc_data: Bitcoin market data
            market_data: Polymarket market data
            balance: Current wallet balance
            
        Returns:
            (should_trade, reason, position_size) tuple
        """
        # Check risk limits
        can_trade, reason = self.check_risk_limits()
        if not can_trade:
            return False, reason, 0.0
        
        # Check safety filters
        can_trade, reason = self.apply_safety_filters(btc_data, market_data)
        if not can_trade:
            return False, reason, 0.0
        
        # Check AI decision
        if ai_decision['decision'] == 'SKIP':
            return False, f"AI decided to skip: {ai_decision['reason']}", 0.0
        
        # Check confidence threshold
        confidence = ai_decision['confidence']
        if confidence < self.config.CONFIDENCE_THRESHOLD_SKIP:
            return False, f"Low confidence: {confidence:.2f} < {self.config.CONFIDENCE_THRESHOLD_SKIP}", 0.0
        
        # Calculate position size
        position_size = self.calculate_position_size(balance, confidence)
        if position_size == 0:
            return False, "Position size zero", 0.0
        
        # Additional logic: check if Polymarket price offers value
        yes_price = market_data.get('yes_price', 0.5)
        
        if ai_decision['decision'] == 'BUY_YES':
            expected_prob = confidence
            if expected_prob > yes_price + 0.05:  # 5% edge required
                return True, f"Value found: expected {expected_prob:.2%} > market {yes_price:.2%}", position_size
            else:
                return False, f"Poor value: expected {expected_prob:.2%} vs market {yes_price:.2%}", 0.0
        
        elif ai_decision['decision'] == 'BUY_NO':
            no_price = market_data.get('no_price', 0.5)
            expected_prob = 1 - confidence
            if expected_prob > no_price + 0.05:
                return True, f"Value found: expected {expected_prob:.2%} > market {no_price:.2%}", position_size
            else:
                return False, f"Poor value: expected {expected_prob:.2%} vs market {no_price:.2%}", 0.0
        
        return True, "All checks passed", position_size
    
    def update_after_trade(self, trade_result: Dict):
        """
        Update strategy state after a trade
        
        Args:
            trade_result: Trade result with PnL information
        """
        self.trade_history.append(trade_result)
        self.hourly_trades.append({
            'timestamp': datetime.now(),
            'result': trade_result
        })
        
        if 'pnl' in trade_result:
            self.daily_pnl += trade_result['pnl']
            self.daily_trade_count += 1
            
            if trade_result['pnl'] < 0:
                self.consecutive_losses += 1
            else:
                self.consecutive_losses = 0
        
        self.last_trade_time = datetime.now()
    
    def set_cooldown(self):
        """Activate cooldown after a loss"""
        self.cooldown_until = datetime.now() + timedelta(minutes=self.config.COOLDOWN_MINUTES_AFTER_LOSS)
        trading_logger.info(f"Cooldown activated until {self.cooldown_until}")
    
    def get_daily_metrics(self) -> Dict:
        """Get daily trading metrics"""
        return {
            'daily_pnl': self.daily_pnl,
            'daily_trades': self.daily_trade_count,
            'consecutive_losses': self.consecutive_losses,
            'hourly_trades_count': len(self.hourly_trades)
        }
