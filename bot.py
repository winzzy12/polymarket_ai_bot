"""
Main Polymarket AI Trading Bot
Orchestrates all modules and runs the main trading loop
"""

import time
import signal
import sys
from datetime import datetime
from typing import Dict, Optional

from config import Config
from logger import trading_logger
from market import PolymarketMarket
from btc_data import BTCDataFetcher
from ai_engine import AIDecisionEngine
from strategy import TradingStrategy
from trade_executor import TradeExecutor
from risk_manager import RiskManager

class PolymarketTradingBot:
    def __init__(self):
        """Initialize the trading bot with all components"""
        trading_logger.info("=" * 60)
        trading_logger.info("Initializing Polymarket AI Trading Bot")
        trading_logger.info("=" * 60)
        
        # Validate configuration
        try:
            Config.validate()
        except ValueError as e:
            trading_logger.error(f"Configuration error: {e}")
            sys.exit(1)
        
        # Initialize modules
        self.config = Config
        self.market = PolymarketMarket(Config.POLYMARKET_GAMMA_API)
        self.btc_fetcher = BTCDataFetcher(Config.BINANCE_API_URL)
        self.ai_engine = AIDecisionEngine(
            Config.OPENAI_API_KEY,
            Config.AI_MODEL,
            Config.AI_TEMPERATURE
        )
        self.strategy = TradingStrategy(Config)
        self.executor = TradeExecutor(Config)
        self.risk_manager = RiskManager(Config)
        
        # Bot state
        self.running = True
        self.current_market = None
        self.market_data = None
        self.daily_reset_time = datetime.now().date()
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)
        
        # Initialize market
        self.initialize_market()
        
        # Initialize balance tracking
        initial_balance = self.executor.get_balance()
        self.risk_manager.initialize_balance(initial_balance)
        
        trading_logger.info("Bot initialization complete")
        
    def initialize_market(self):
        """Find and initialize the target market"""
        trading_logger.info(f"Searching for market: {Config.MARKET_SLUG}")
        
        market = self.market.find_market(Config.MARKET_SLUG)
        
        if market:
            self.current_market = market
            trading_logger.info(f"Market found: {market.get('question', 'Unknown')}")
            trading_logger.info(f"Market ID: {market.get('id', 'Unknown')}")
        else:
            trading_logger.warning("Target market not found, will retry in next cycle")
    
    def fetch_all_data(self) -> tuple:
        """
        Fetch all required data for decision making
        
        Returns:
            Tuple of (btc_data, market_data) or (None, None) if failed
        """
        trading_logger.debug("Fetching market data...")
        
        # Fetch Polymarket data
        if not self.current_market:
            market = self.market.find_market(Config.MARKET_SLUG)
            if market:
                self.current_market = market
            else:
                trading_logger.warning("Market still not available")
                return None, None
        
        market_id = self.current_market.get('id')
        if not market_id:
            trading_logger.warning("No market ID available")
            return None, None
            
        market_data = self.market.get_market_prices(market_id)
        
        if not market_data:
            trading_logger.warning("Failed to fetch market data")
            return None, None
        
        # Fetch BTC data
        trading_logger.debug("Fetching BTC data...")
        btc_data = self.btc_fetcher.get_complete_analysis()
        
        if not btc_data:
            trading_logger.warning("Failed to fetch BTC data")
            return None, None
        
        return btc_data, market_data
    
    def check_daily_reset(self):
        """Reset daily counters if needed"""
        today = datetime.now().date()
        
        if today != self.daily_reset_time:
            trading_logger.info("Daily reset - resetting counters")
            self.daily_reset_time = today
            self.strategy.daily_pnl = 0
            self.strategy.daily_trade_count = 0
            self.strategy.consecutive_losses = 0
            self.risk_manager.daily_pnl = 0
    
    def execute_trade(self, decision: Dict, position_size: float, market_data: Dict):
        """
        Execute the trade based on AI decision
        
        Args:
            decision: AI decision dictionary
            position_size: Size of position to take
            market_data: Current market data
        """
        market_id = self.current_market.get('id')
        
        # Get token IDs for the market
        token_ids = self.executor.get_token_ids(market_id)
        
        if decision['decision'] == 'BUY_YES':
            trading_logger.info(f"Executing BUY YES order for ${position_size:.2f}")
            
            trade_result = self.executor.place_yes_order(
                amount=position_size,
                token_id=token_ids['yes_token_id'],
                market_address=self.current_market.get('address', '')
            )
            
            if trade_result:
                trading_logger.log_trade_execution({
                    'type': 'BUY_YES',
                    'amount': position_size,
                    'confidence': decision['confidence'],
                    'reason': decision['reason'],
                    'tx_hash': trade_result.get('tx_hash', 'dry_run')
                })
                
        elif decision['decision'] == 'BUY_NO':
            trading_logger.info(f"Executing BUY NO order for ${position_size:.2f}")
            
            trade_result = self.executor.place_no_order(
                amount=position_size,
                token_id=token_ids['no_token_id'],
                market_address=self.current_market.get('address', '')
            )
            
            if trade_result:
                trading_logger.log_trade_execution({
                    'type': 'BUY_NO',
                    'amount': position_size,
                    'confidence': decision['confidence'],
                    'reason': decision['reason'],
                    'tx_hash': trade_result.get('tx_hash', 'dry_run')
                })
        
        # Update strategy after trade
        self.strategy.update_after_trade({
            'pnl': 0,  # Will be updated when position closes
            'position_size': position_size,
            'timestamp': datetime.now()
        })
    
    def run_trading_cycle(self):
        """Execute one complete trading cycle"""
        trading_logger.info("-" * 40)
        trading_logger.info("Starting new trading cycle")
        
        # Check daily reset
        self.check_daily_reset()
        
        # Fetch all market data
        btc_data, market_data = self.fetch_all_data()
        
        if not btc_data or not market_data:
            trading_logger.warning("Insufficient data for trading cycle, skipping")
            return
        
        # Get AI decision
        if Config.ENABLE_AI_DECISION:
            ai_decision = self.ai_engine.make_decision(btc_data, market_data)
        else:
            # Fallback to simple strategy
            ai_decision = {
                'decision': 'SKIP',
                'confidence': 0.5,
                'reason': 'AI disabled, using fallback',
                'timestamp': datetime.now().isoformat()
            }
        
        # Check if we should trade
        balance = self.executor.get_balance()
        should_trade, reason, position_size = self.strategy.should_trade(
            ai_decision, btc_data, market_data, balance
        )
        
        if not should_trade:
            trading_logger.log_skip_reason(reason)
            return
        
        # Final risk check
        can_trade, risk_reason = self.risk_manager.check_daily_limits()
        if not can_trade:
            trading_logger.log_skip_reason(f"Risk limit: {risk_reason}")
            return
        
        # Execute the trade
        trading_logger.info(f"Decision: {ai_decision['decision']} with {ai_decision['confidence']:.2%} confidence")
        trading_logger.info(f"Position size: ${position_size:.2f}")
        trading_logger.info(f"Reason: {ai_decision['reason']}")
        
        self.execute_trade(ai_decision, position_size, market_data)
        
        # Update balance after trade
        new_balance = self.executor.get_balance()
        self.risk_manager.update_balance(new_balance)
        
        # Log performance metrics
        metrics = self.risk_manager.get_risk_metrics()
        trading_logger.log_performance_metrics(metrics)
    
    def run(self):
        """Main bot loop"""
        trading_logger.info("Starting main trading loop")
        
        cycle_count = 0
        
        while self.running:
            try:
                cycle_start = time.time()
                cycle_count += 1
                
                trading_logger.info(f"\n=== CYCLE #{cycle_count} ===")
                
                # Run trading cycle
                self.run_trading_cycle()
                
                # Calculate sleep time
                elapsed = time.time() - cycle_start
                sleep_time = max(0, Config.BOT_LOOP_INTERVAL_SECONDS - elapsed)
                
                trading_logger.info(f"Cycle completed in {elapsed:.2f}s, sleeping for {sleep_time:.2f}s")
                
                # Sleep until next cycle
                for _ in range(int(sleep_time)):
                    if not self.running:
                        break
                    time.sleep(1)
                
            except KeyboardInterrupt:
                trading_logger.info("Keyboard interrupt received")
                self.shutdown()
                break
            except Exception as e:
                trading_logger.error(f"Unexpected error in main loop: {e}")
                trading_logger.error(f"Error details: {sys.exc_info()}")
                
                # Wait before retrying
                time.sleep(10)
    
    def shutdown(self, signum=None, frame=None):
        """Gracefully shutdown the bot"""
        trading_logger.info("Shutting down bot...")
        self.running = False
        
        # Log final metrics
        final_balance = self.executor.get_balance()
        metrics = self.risk_manager.get_risk_metrics()
        
        trading_logger.info("=" * 60)
        trading_logger.info("FINAL BOT STATUS")
        trading_logger.info(f"Final Balance: ${final_balance:,.2f}")
        trading_logger.info(f"Total Trades: {metrics['total_trades']}")
        trading_logger.info(f"Win Rate: {metrics['win_rate']:.2%}")
        trading_logger.info(f"Current Drawdown: {metrics['current_drawdown']:.2%}")
        trading_logger.info("=" * 60)
        
        trading_logger.info("Bot shutdown complete")
        sys.exit(0)

def main():
    """Main entry point"""
    bot = PolymarketTradingBot()
    
    try:
        bot.run()
    except Exception as e:
        trading_logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
