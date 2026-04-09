"""
AI Decision Engine
Uses OpenAI GPT to analyze market data and make trading decisions
"""

import json
from typing import Dict, Optional
import openai
from datetime import datetime
from logger import trading_logger

class AIDecisionEngine:
    def __init__(self, api_key: str, model: str = "gpt-4", temperature: float = 0.3):
        """
        Initialize AI decision engine
        
        Args:
            api_key: OpenAI API key
            model: OpenAI model to use
            temperature: Randomness in responses (0-1)
        """
        openai.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.decision_history = []
        
    def create_analysis_prompt(self, btc_data: Dict, market_data: Dict) -> str:
        """
        Create a structured prompt for AI analysis
        
        Args:
            btc_data: Bitcoin market data and indicators
            market_data: Polymarket data including YES/NO prices
            
        Returns:
            Formatted prompt string
        """
        prompt = f"""You are an expert cryptocurrency trader specializing in short-term Bitcoin price movements.

MARKET CONTEXT:
You are trading on Polymarket for the "Bitcoin Up or Down – 5 Minutes" market.
You can buy YES (bet on Bitcoin going UP) or NO (bet on Bitcoin going DOWN) shares.

CURRENT MARKET DATA:

Bitcoin Price Data:
- Current Price: ${btc_data.get('current_price', 'N/A'):,.2f}
- 1-Minute Change: {btc_data.get('change_1m_percent', 0):+.2f}%
- 5-Minute Change: {btc_data.get('change_5m_percent', 0):+.2f}%

Technical Indicators:
- RSI (14): {btc_data.get('rsi', 50)} (Overbought >70, Oversold <30)
- MACD: {btc_data.get('macd', 0):.4f}
- MACD Signal: {btc_data.get('macd_signal', 0):.4f}
- MACD Histogram: {btc_data.get('macd_histogram', 0):.4f}
- EMA 9: ${btc_data.get('ema_9', 0):,.2f}
- EMA 21: ${btc_data.get('ema_21', 0):,.2f}
- Volatility: {btc_data.get('volatility', 0):.2f}%
- Momentum: {btc_data.get('momentum', 0):.2f}
- Bollinger Band Position: {btc_data.get('bb_position', 0.5):.2f} (0=lower, 1=upper)

Polymarket Data:
- YES Price: {market_data.get('yes_price', 0.5):.3f} USDC
- NO Price: {market_data.get('no_price', 0.5):.3f} USDC
- Market Volume: ${market_data.get('volume', 0):,.0f}
- Liquidity: ${market_data.get('liquidity', 0):,.0f}
- Bid-Ask Spread: {market_data.get('spread', 0):.3f}

ANALYSIS TASK:
Predict the probability that Bitcoin's price will be HIGHER in 5 minutes compared to now.

Consider:
1. Current price action and momentum
2. Technical indicator signals (RSI, MACD, EMA crossovers)
3. Market structure (volatility, Bollinger Bands)
4. Polymarket implied probability (YES price)
5. Short-term market sentiment

RESPONSE FORMAT:
Return ONLY valid JSON (no additional text) in this exact format:

{{
    "decision": "BUY_YES | BUY_NO | SKIP",
    "confidence": 0.75,
    "reason": "Brief explanation of your analysis",
    "expected_move_percent": 0.5,
    "key_factors": ["factor1", "factor2"]
}}

Decision Guidelines:
- BUY_YES: When you predict Bitcoin will go UP (>55% probability)
- BUY_NO: When you predict Bitcoin will go DOWN (>55% probability)
- SKIP: When uncertain or market conditions are unfavorable

Confidence should be between 0 and 1:
- >0.7: High confidence trade
- 0.55-0.7: Standard confidence trade
- <0.55: Skip trade

Be conservative and risk-aware. Focus on high-probability setups.
"""
        return prompt
    
    def parse_ai_response(self, response_text: str) -> Dict:
        """
        Parse and validate AI response
        
        Args:
            response_text: Raw response from OpenAI
            
        Returns:
            Parsed and validated decision dictionary
        """
        try:
            # Clean the response text (remove any markdown or extra spaces)
            response_text = response_text.strip()
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            # Parse JSON
            decision = json.loads(response_text)
            
            # Validate required fields
            required_fields = ['decision', 'confidence', 'reason']
            for field in required_fields:
                if field not in decision:
                    raise ValueError(f"Missing required field: {field}")
            
            # Validate decision value
            if decision['decision'] not in ['BUY_YES', 'BUY_NO', 'SKIP']:
                raise ValueError(f"Invalid decision: {decision['decision']}")
            
            # Validate confidence range
            confidence = float(decision['confidence'])
            if not 0 <= confidence <= 1:
                raise ValueError(f"Confidence out of range: {confidence}")
            
            decision['confidence'] = confidence
            
            # Add timestamp
            decision['timestamp'] = datetime.now().isoformat()
            decision['model'] = self.model
            
            return decision
            
        except json.JSONDecodeError as e:
            trading_logger.error(f"Failed to parse AI response as JSON: {e}")
            trading_logger.error(f"Raw response: {response_text}")
            return self.get_default_decision("JSON parsing failed")
        except Exception as e:
            trading_logger.error(f"Error parsing AI response: {e}")
            return self.get_default_decision(f"Parse error: {str(e)}")
    
    def get_default_decision(self, reason: str) -> Dict:
        """
        Return default decision when AI fails
        
        Args:
            reason: Reason for using default decision
            
        Returns:
            Default decision dictionary
        """
        return {
            'decision': 'SKIP',
            'confidence': 0.0,
            'reason': f"Default skip - {reason}",
            'timestamp': datetime.now().isoformat(),
            'model': 'default',
            'is_default': True
        }
    
    def make_decision(self, btc_data: Dict, market_data: Dict) -> Dict:
        """
        Make trading decision using AI
        
        Args:
            btc_data: Bitcoin market data and indicators
            market_data: Polymarket data
            
        Returns:
            Decision dictionary
        """
        try:
            # Create prompt
            prompt = self.create_analysis_prompt(btc_data, market_data)
            
            # Call OpenAI API
            trading_logger.info("Requesting AI decision...")
            
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional cryptocurrency trader. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=300
            )
            
            # Extract response text
            response_text = response.choices[0].message.content
            
            # Parse decision
            decision = self.parse_ai_response(response_text)
            
            # Log decision
            trading_logger.log_ai_decision(decision)
            
            # Store in history
            self.decision_history.append({
                **decision,
                'btc_data': btc_data,
                'market_data': market_data
            })
            
            # Keep only last 100 decisions
            if len(self.decision_history) > 100:
                self.decision_history = self.decision_history[-100:]
            
            return decision
            
        except Exception as e:
            trading_logger.error(f"AI decision error: {e}")
            return self.get_default_decision(f"API error: {str(e)}")
    
    def get_decision_accuracy(self) -> Optional[float]:
        """
        Calculate historical decision accuracy (if tracking PnL)
        
        Returns:
            Accuracy percentage or None if insufficient data
        """
        if len(self.decision_history) < 10:
            return None
            
        # This would need to be linked with actual PnL data
        # For now, return placeholder
        return 0.65
