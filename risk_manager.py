"""
Risk management module
Handles position sizing, drawdown protection, and risk calculations
"""

from typing import Dict, Optional
from datetime import datetime, timedelta
from collections import deque
import numpy as np
from logger import trading_logger

class RiskManager:
    def __init__(self, config):
        """
        Initialize risk manager
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.positions = {}
        self.trade_history = deque(maxlen=1000)
        self.daily_pnl = 0.0
        self.starting_balance = None
        self.current_balance = None
        self.peak_balance = None
        self.drawdown = 0.0
        
    def initialize_balance(self, balance: float):
        """Initialize starting balance for tracking"""
        self.starting_balance = balance
        self.current_balance = balance
        self.peak_balance = balance
        trading_logger.info(f"Risk Manager initialized with balance: ${balance:,.2f}")
    
    def update_balance(self, new_balance: float):
        """Update current balance and calculate drawdown"""
        self.current_balance = new_balance
        
        if new_balance > self.peak_balance:
            self.peak_balance = new_balance
        
        # Calculate drawdown from peak
        if self.peak_balance > 0:
            self.drawdown = (self.peak_balance - new_balance) / self.peak_balance
        
    def calculate_kelly_criterion(self, win_probability: float, win_loss_ratio: float) -> float:
        """
        Calculate Kelly Criterion for optimal position sizing
        
        Args:
            win_probability: Probability of winning (0-1)
            win_loss_ratio: Average win / average loss
            
        Returns:
            Kelly fraction (0-1)
        """
        if win_loss_ratio <= 0:
            return 0
        
        # Kelly formula: f* = (p * b - q) / b
        # where p = win probability, q = loss probability (1-p), b = win/loss ratio
        kelly = (win_probability * win_loss_ratio - (1 - win_probability)) / win_loss_ratio
        
        # Conservative Kelly (use fraction of Kelly)
        conservative_kelly = max(0, min(0.25, kelly * 0.5))  # Max 25% of portfolio, half Kelly
        
        return conservative_kelly
    
    def calculate_var(self, returns: list, confidence_level: float = 0.95) -> float:
        """
        Calculate Value at Risk (VaR)
        
        Args:
            returns: List of historical returns
            confidence_level: Confidence level for VaR (e.g., 0.95 for 95%)
            
        Returns:
            VaR value
        """
        if len(returns) < 10:
            return 0.05  # Default 5% VaR
        
        returns_array = np.array(returns)
        var = np.percentile(returns_array, (1 - confidence_level) * 100)
        return abs(var)
    
    def calculate_max_position_size(self, balance: float, volatility: float) -> float:
        """
        Calculate maximum position size based on volatility
        
        Args:
            balance: Current wallet balance
            volatility: Current market volatility
            
        Returns:
            Maximum position size in USDC
        """
        # Risk per trade as percentage of balance
        risk_per_trade = 0.02  # 2% risk per trade
        
        # Adjust for volatility
        if volatility > 0:
            volatility_adjustment = min(1.0, 0.05 / volatility)  # Lower position in high volatility
        else:
            volatility_adjustment = 1.0
        
        max_position = balance * risk_per_trade * volatility_adjustment
        
        # Absolute maximum position (e.g., $1000)
        absolute_max = min(max_position, 1000)
        
        return absolute_max
    
    def check_daily_limits(self) -> tuple:
        """
        Check if daily trading limits are hit
        
        Returns:
            (can_trade, reason) tuple
        """
        # Check daily stop loss
        if self.starting_balance:
            daily_loss_pct = (self.starting_balance - self.current_balance) / self.starting_balance
            if daily_loss_pct >= self.config.DAILY_STOP_LOSS_PERCENT:
                return False, f"Daily stop loss reached: {daily_loss_pct:.2%} loss"
        
        # Check daily profit target
        if self.starting_balance:
            daily_profit_pct = (self.current_balance - self.starting_balance) / self.starting_balance
            if daily_profit_pct >= self.config.DAILY_PROFIT_TARGET_PERCENT:
                return False, f"Daily profit target reached: {daily_profit_pct:.2%} profit"
        
        # Check maximum drawdown
        if self.drawdown >= 0.15:  # 15% maximum drawdown
            return False, f"Maximum drawdown reached: {self.drawdown:.2%}"
        
        return True, "Daily limits OK"
    
    def calculate_position_risk(self, position_size: float, balance: float, 
                                 stop_loss_pct: float = 0.02) -> float:
        """
        Calculate risk for a specific position
        
        Args:
            position_size: Size of position in USDC
            balance: Current wallet balance
            stop_loss_pct: Stop loss percentage
            
        Returns:
            Risk amount in USDC
        """
        risk_amount = position_size * stop_loss_pct
        risk_to_balance_pct = risk_amount / balance if balance > 0 else 0
        
        return risk_amount
    
    def should_close_position(self, position_id: str, current_price: float, 
                               entry_price: float) -> tuple:
        """
        Determine if a position should be closed based on stop loss or take profit
        
        Args:
            position_id: Position identifier
            current_price: Current market price
            entry_price: Entry price of the position
            
        Returns:
            (should_close, reason) tuple
        """
        if position_id not in self.positions:
            return False, "Position not found"
        
        position = self.positions[position_id]
        pnl_pct = (current_price - entry_price) / entry_price
        
        # Check stop loss
        if pnl_pct <= -position.get('stop_loss_pct', 0.02):
            return True, f"Stop loss triggered: {pnl_pct:.2%}"
        
        # Check take profit
        if pnl_pct >= position.get('take_profit_pct', 0.05):
            return True, f"Take profit triggered: {pnl_pct:.2%}"
        
        # Time-based exit (e.g., hold for maximum 1 hour)
        entry_time = position.get('entry_time')
        if entry_time and datetime.now() - entry_time > timedelta(hours=1):
            return True, "Maximum hold time reached"
        
        return False, "Hold position"
    
    def record_trade(self, trade_data: Dict):
        """
        Record a completed trade for risk analysis
        
        Args:
            trade_data: Trade information including PnL
        """
        self.trade_history.append(trade_data)
        
        if 'pnl' in trade_data:
            self.daily_pnl += trade_data['pnl']
            
        trading_logger.log_pnl(trade_data.get('pnl', 0), self.daily_pnl)
    
    def get_risk_metrics(self) -> Dict:
        """
        Get current risk metrics
        
        Returns:
            Dictionary of risk metrics
        """
        returns = [trade.get('return_pct', 0) for trade in self.trade_history if 'return_pct' in trade]
        
        metrics = {
            'current_drawdown': self.drawdown,
            'daily_pnl': self.daily_pnl,
            'total_trades': len(self.trade_history),
            'current_balance': self.current_balance,
            'peak_balance': self.peak_balance,
            'var_95': self.calculate_var(returns) if returns else 0,
            'sharpe_ratio': self.calculate_sharpe_ratio(returns) if returns else 0,
            'win_rate': self.calculate_win_rate()
        }
        
        return metrics
    
    def calculate_sharpe_ratio(self, returns: list, risk_free_rate: float = 0.02) -> float:
        """
        Calculate Sharpe ratio
        
        Args:
            returns: List of returns
            risk_free_rate: Annual risk-free rate
            
        Returns:
            Sharpe ratio
        """
        if not returns or len(returns) < 2:
            return 0
        
        returns_array = np.array(returns)
        excess_returns = returns_array - (risk_free_rate / 252)  # Daily risk-free rate
        sharpe = np.mean(excess_returns) / (np.std(returns_array) + 1e-10)
        
        return sharpe * np.sqrt(252)  # Annualized
    
    def calculate_win_rate(self) -> float:
        """Calculate win rate from trade history"""
        if not self.trade_history:
            return 0
        
        winning_trades = sum(1 for trade in self.trade_history if trade.get('pnl', 0) > 0)
        return winning_trades / len(self.trade_history)
