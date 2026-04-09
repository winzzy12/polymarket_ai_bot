"""
Trade execution module
Handles on-chain transactions on Polygon network
"""

from web3 import Web3
from typing import Dict, Optional
import json
import time
from decimal import Decimal
from logger import trading_logger

class TradeExecutor:
    def __init__(self, config):
        """
        Initialize trade executor with Web3 connection
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.web3 = Web3(Web3.HTTPProvider(config.POLYGON_RPC_URL))
        
        if not self.web3.is_connected():
            raise ConnectionError("Failed to connect to Polygon network")
        
        # Setup wallet
        if not config.DRY_RUN_MODE and config.WALLET_PRIVATE_KEY:
            self.account = self.web3.eth.account.from_key(config.WALLET_PRIVATE_KEY)
            self.wallet_address = self.account.address
            trading_logger.info(f"Wallet connected: {self.wallet_address}")
        else:
            self.account = None
            self.wallet_address = config.WALLET_ADDRESS
            trading_logger.info("DRY RUN MODE - No actual trades will be executed")
        
        # Contract ABIs (simplified - you'll need actual Polymarket contract ABIs)
        self.ctf_exchange_abi = self.get_ctf_exchange_abi()
        
        # Initialize contract
        self.ctf_exchange = self.web3.eth.contract(
            address=Web3.to_checksum_address(config.CTF_EXCHANGE_ADDRESS),
            abi=self.ctf_exchange_abi
        )
        
    def get_ctf_exchange_abi(self) -> list:
        """
        Get CTF Exchange contract ABI
        This is a simplified version - you'll need the full ABI from Polymarket
        """
        # Simplified ABI for demonstration
        return [
            {
                "inputs": [
                    {"internalType": "address", "name": "market", "type": "address"},
                    {"internalType": "uint256", "name": "tokenId", "type": "uint256"},
                    {"internalType": "uint256", "name": "amount", "type": "uint256"}
                ],
                "name": "buy",
                "outputs": [],
                "stateMutability": "payable",
                "type": "function"
            }
        ]
    
    def get_balance(self) -> float:
        """
        Get wallet balance in USDC
        
        Returns:
            USDC balance
        """
        if self.config.DRY_RUN_MODE:
            # Simulate balance for dry run
            return 10000.0
        
        try:
            # USDC contract on Polygon
            usdc_address = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
            usdc_abi = [
                {"constant": True, "inputs": [{"name": "_owner", "type": "address"}],
                 "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}],
                 "type": "function"}
            ]
            
            usdc_contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(usdc_address),
                abi=usdc_abi
            )
            
            balance = usdc_contract.functions.balanceOf(self.wallet_address).call()
            return balance / 1e6  # USDC has 6 decimals
            
        except Exception as e:
            trading_logger.error(f"Error fetching balance: {e}")
            return 0.0
    
    def estimate_gas(self, transaction: Dict) -> int:
        """
        Estimate gas for a transaction
        
        Args:
            transaction: Transaction dictionary
            
        Returns:
            Estimated gas amount
        """
        try:
            estimated_gas = self.web3.eth.estimate_gas(transaction)
            # Add 20% buffer
            return int(estimated_gas * 1.2)
        except Exception as e:
            trading_logger.error(f"Gas estimation failed: {e}")
            return 200000  # Default gas limit
    
    def get_gas_price(self) -> int:
        """
        Get current gas price
        
        Returns:
            Gas price in wei
        """
        try:
            gas_price = self.web3.eth.gas_price
            # Add 10% for faster confirmation
            return int(gas_price * 1.1)
        except Exception as e:
            trading_logger.error(f"Error getting gas price: {e}")
            return 50 * 10**9  # Default 50 Gwei
    
    def place_yes_order(self, amount: float, token_id: str, market_address: str) -> Optional[Dict]:
        """
        Place a BUY YES order
        
        Args:
            amount: Amount in USDC to spend
            token_id: Token ID for YES position
            market_address: Market contract address
            
        Returns:
            Transaction receipt or None if failed
        """
        if self.config.DRY_RUN_MODE:
            trading_logger.info(f"DRY RUN: Would buy YES for {amount} USDC")
            return {
                'dry_run': True,
                'amount': amount,
                'token_id': token_id,
                'status': 'simulated'
            }
        
        try:
            amount_wei = self.web3.to_wei(amount, 'ether')
            
            # Build transaction
            transaction = self.ctf_exchange.functions.buy(
                Web3.to_checksum_address(market_address),
                int(token_id),
                amount_wei
            ).build_transaction({
                'from': self.wallet_address,
                'gas': self.estimate_gas({}),
                'gasPrice': self.get_gas_price(),
                'nonce': self.web3.eth.get_transaction_count(self.wallet_address),
                'value': 0  # USDC is ERC20, not native token
            })
            
            # Sign transaction
            signed_txn = self.account.sign_transaction(transaction)
            
            # Send transaction
            trading_logger.info(f"Sending YES order: {amount} USDC")
            tx_hash = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            # Wait for confirmation
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
            
            if receipt['status'] == 1:
                trading_logger.info(f"YES order successful: {tx_hash.hex()}")
                return {
                    'success': True,
                    'tx_hash': tx_hash.hex(),
                    'amount': amount,
                    'token_id': token_id,
                    'receipt': receipt
                }
            else:
                trading_logger.error(f"YES order failed: {tx_hash.hex()}")
                return None
                
        except Exception as e:
            trading_logger.error(f"Error placing YES order: {e}")
            return None
    
    def place_no_order(self, amount: float, token_id: str, market_address: str) -> Optional[Dict]:
        """
        Place a BUY NO order
        
        Args:
            amount: Amount in USDC to spend
            token_id: Token ID for NO position
            market_address: Market contract address
            
        Returns:
            Transaction receipt or None if failed
        """
        # Similar to place_yes_order but with NO token
        # For demonstration, using same implementation
        if self.config.DRY_RUN_MODE:
            trading_logger.info(f"DRY RUN: Would buy NO for {amount} USDC")
            return {
                'dry_run': True,
                'amount': amount,
                'token_id': token_id,
                'status': 'simulated'
            }
        
        try:
            # Implementation similar to place_yes_order
            # Different token_id for NO position
            return self.place_yes_order(amount, token_id, market_address)
            
        except Exception as e:
            trading_logger.error(f"Error placing NO order: {e}")
            return None
    
    def get_token_ids(self, market_id: str) -> Dict[str, str]:
        """
        Get YES and NO token IDs for a market
        
        Args:
            market_id: Market identifier
            
        Returns:
            Dictionary with yes_token_id and no_token_id
        """
        # This would require querying the Polymarket contract
        # Simplified for demonstration
        return {
            'yes_token_id': f"{market_id}_YES",
            'no_token_id': f"{market_id}_NO"
        }
    
    def check_allowance(self, token_address: str, spender_address: str) -> int:
        """
        Check USDC allowance for the exchange
        
        Args:
            token_address: USDC token address
            spender_address: Exchange contract address
            
        Returns:
            Allowance amount
        """
        if self.config.DRY_RUN_MODE:
            return 10**18  # Simulate sufficient allowance
        
        try:
            erc20_abi = [
                {"constant": True, "inputs": [{"name": "_owner", "type": "address"},
                                              {"name": "_spender", "type": "address"}],
                 "name": "allowance", "outputs": [{"name": "", "type": "uint256"}],
                 "type": "function"}
            ]
            
            token_contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=erc20_abi
            )
            
            allowance = token_contract.functions.allowance(
                self.wallet_address,
                Web3.to_checksum_address(spender_address)
            ).call()
            
            return allowance
            
        except Exception as e:
            trading_logger.error(f"Error checking allowance: {e}")
            return 0
    
    def approve_spending(self, token_address: str, spender_address: str, amount: int) -> bool:
        """
        Approve the exchange to spend USDC
        
        Args:
            token_address: USDC token address
            spender_address: Exchange contract address
            amount: Amount to approve
            
        Returns:
            Success status
        """
        if self.config.DRY_RUN_MODE:
            trading_logger.info(f"DRY RUN: Would approve {amount} spending")
            return True
        
        try:
            erc20_abi = [
                {"inputs": [{"name": "spender", "type": "address"},
                            {"name": "amount", "type": "uint256"}],
                 "name": "approve", "outputs": [{"name": "", "type": "bool"}],
                 "stateMutability": "nonpayable", "type": "function"}
            ]
            
            token_contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=erc20_abi
            )
            
            transaction = token_contract.functions.approve(
                Web3.to_checksum_address(spender_address),
                amount
            ).build_transaction({
                'from': self.wallet_address,
                'gas': 100000,
                'gasPrice': self.get_gas_price(),
                'nonce': self.web3.eth.get_transaction_count(self.wallet_address)
            })
            
            signed_txn = self.account.sign_transaction(transaction)
            tx_hash = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            return receipt['status'] == 1
            
        except Exception as e:
            trading_logger.error(f"Error approving spending: {e}")
            return False
