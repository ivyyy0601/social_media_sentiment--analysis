"""
Stock data provider for fetching ticker information from external sources.
Supports yfinance for comprehensive US stock data.
"""

import yfinance as yf
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional


class StockDataProvider:
    """Provides stock ticker data from yfinance"""
    
    def __init__(self, cache_file='stock_data_cache.json', cache_duration_days=7):
        """
        Initialize stock data provider
        
        Args:
            cache_file: Path to cache file for storing stock data
            cache_duration_days: Number of days to cache stock data before refresh
        """
        self.cache_file = cache_file
        self.cache_duration_days = cache_duration_days
        self.cache = self._load_cache()
    
    def _load_cache(self) -> Dict:
        """Load cached stock data from file"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    cache = json.load(f)
                    # Check if cache is still valid
                    cache_date = datetime.fromisoformat(cache.get('updated_at', '2000-01-01'))
                    if datetime.now() - cache_date < timedelta(days=self.cache_duration_days):
                        return cache
        except Exception as e:
            print(f"Error loading cache: {e}")
        
        return {'updated_at': datetime.now().isoformat(), 'stocks': {}}
    
    def _save_cache(self):
        """Save stock data cache to file"""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            print(f"Error saving cache: {e}")
    
    def get_ticker_info(self, ticker: str) -> Optional[Dict]:
        """
        Get information for a specific ticker
        
        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL')
            
        Returns:
            Dictionary with ticker info or None if not found
        """
        ticker = ticker.upper()
        
        # Check cache first
        if ticker in self.cache.get('stocks', {}):
            return self.cache['stocks'][ticker]
        
        # Fetch from yfinance
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # Extract relevant information
            ticker_data = {
                'ticker': ticker,
                'company': info.get('longName') or info.get('shortName', ticker),
                'sector': info.get('sector', 'Unknown'),
                'industry': info.get('industry', 'Unknown'),
                'market_cap': info.get('marketCap'),
                'exchange': info.get('exchange', 'Unknown'),
                'currency': info.get('currency', 'USD')
            }
            
            # Cache the data
            if 'stocks' not in self.cache:
                self.cache['stocks'] = {}
            self.cache['stocks'][ticker] = ticker_data
            self.cache['updated_at'] = datetime.now().isoformat()
            self._save_cache()
            
            return ticker_data
            
        except Exception as e:
            print(f"Error fetching data for {ticker}: {e}")
            return None
    
    def fetch_popular_stocks(self, limit: int = 500) -> List[Dict]:
        """
        Fetch popular US stocks
        
        Args:
            limit: Maximum number of stocks to fetch
            
        Returns:
            List of stock dictionaries
        """
        # List of popular tickers across different sectors
        popular_tickers = [
            # Technology
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA', 'AMD', 'INTC', 'ORCL',
            'CSCO', 'ADBE', 'CRM', 'AVGO', 'QCOM', 'TXN', 'NFLX', 'PYPL', 'UBER', 'ABNB',
            # Finance
            'JPM', 'BAC', 'WFC', 'GS', 'MS', 'C', 'BLK', 'SCHW', 'AXP', 'COF',
            # Healthcare
            'JNJ', 'UNH', 'PFE', 'ABBV', 'MRK', 'TMO', 'ABT', 'DHR', 'BMY', 'AMGN',
            'CVS', 'CI', 'HUM', 'ELV', 'LLY',
            # Consumer
            'WMT', 'HD', 'MCD', 'NKE', 'SBUX', 'TGT', 'LOW', 'COST', 'TJX', 'DG',
            # Energy
            'XOM', 'CVX', 'COP', 'SLB', 'EOG', 'PSX', 'VLO', 'MPC', 'OXY', 'HAL',
            # Industrial
            'BA', 'HON', 'UPS', 'CAT', 'GE', 'MMM', 'LMT', 'RTX', 'DE', 'FDX',
            # Telecom
            'T', 'VZ', 'TMUS', 'DIS', 'CMCSA',
            # Retail
            'AMZN', 'WMT', 'COST', 'TGT', 'BBY', 'ETSY', 'EBAY',
            # Automotive
            'TSLA', 'F', 'GM', 'RIVN', 'LCID',
            # Semiconductors
            'NVDA', 'AMD', 'INTC', 'TSM', 'QCOM', 'AVGO', 'MU', 'AMAT', 'ADI', 'MRVL',
            # Software
            'MSFT', 'ORCL', 'CRM', 'ADBE', 'NOW', 'WDAY', 'TEAM', 'SNOW', 'DDOG', 'ZS',
            # Banks
            'JPM', 'BAC', 'WFC', 'C', 'USB', 'PNC', 'TFC', 'GS', 'MS', 'BK',
            # Pharma
            'PFE', 'JNJ', 'MRK', 'ABBV', 'LLY', 'BMY', 'GILD', 'AMGN', 'BIIB', 'REGN',
            # E-commerce
            'AMZN', 'SHOP', 'EBAY', 'ETSY', 'W',
            # Social Media
            'META', 'SNAP', 'PINS', 'TWTR',
            # Streaming
            'NFLX', 'DIS', 'PARA', 'WBD',
            # Cloud
            'AMZN', 'MSFT', 'GOOGL', 'ORCL', 'IBM',
            # Cybersecurity
            'CRWD', 'PANW', 'ZS', 'FTNT', 'S',
            # Payment
            'V', 'MA', 'PYPL', 'SQ', 'AXP',
            # Biotech
            'MRNA', 'BNTX', 'VRTX', 'ILMN', 'INCY',
            # Real Estate
            'AMT', 'PLD', 'CCI', 'EQIX', 'SPG',
            # Utilities
            'NEE', 'DUK', 'SO', 'D', 'AEP',
            # Materials
            'LIN', 'APD', 'ECL', 'SHW', 'NEM',
            # Consumer Staples
            'PG', 'KO', 'PEP', 'COST', 'WMT', 'MDLZ', 'CL', 'KMB', 'GIS', 'K'
        ]
        
        # Remove duplicates and limit
        unique_tickers = list(dict.fromkeys(popular_tickers))[:limit]
        
        stocks = []
        for ticker in unique_tickers:
            info = self.get_ticker_info(ticker)
            if info:
                stocks.append(info)
        
        return stocks
    
    def refresh_cache(self):
        """Force refresh of cached stock data"""
        self.cache = {'updated_at': datetime.now().isoformat(), 'stocks': {}}
        self._save_cache()
        print("Stock data cache cleared")
    
    def get_cache_info(self) -> Dict:
        """Get information about the cache"""
        return {
            'updated_at': self.cache.get('updated_at'),
            'stock_count': len(self.cache.get('stocks', {})),
            'cache_file': self.cache_file
        }