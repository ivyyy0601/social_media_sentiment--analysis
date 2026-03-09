"""
Price data provider for fetching real-time and historical stock prices.
Uses yfinance for comprehensive price data.
"""

import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import requests_cache
from requests import Session


class PriceDataProvider:
    """Provides stock price data from yfinance with caching"""
    
    def __init__(self, cache_expire_minutes=15):
        """
        Initialize price data provider with caching
        
        Args:
            cache_expire_minutes: Minutes to cache price data (default 15)
        """
        self.cache_expire_minutes = cache_expire_minutes
        
        # Setup caching for requests
        self.session = requests_cache.CachedSession(
            'price_cache',
            backend='memory',
            expire_after=timedelta(minutes=cache_expire_minutes)
        )
    
    def get_current_price(self, ticker: str) -> Optional[Dict]:
        """
        Get current price for a ticker
        
        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL')
            
        Returns:
            Dictionary with current price data or None
        """
        try:
            stock = yf.Ticker(ticker, session=self.session)
            info = stock.info
            
            # Get fast info for current price
            current_price = info.get('currentPrice') or info.get('regularMarketPrice')
            previous_close = info.get('previousClose')
            
            if not current_price:
                return None
            
            change = None
            change_percent = None
            if previous_close and current_price:
                change = current_price - previous_close
                change_percent = (change / previous_close) * 100
            
            return {
                'ticker': ticker.upper(),
                'price': current_price,
                'previous_close': previous_close,
                'change': change,
                'change_percent': change_percent,
                'currency': info.get('currency', 'USD'),
                'market_state': info.get('marketState', 'UNKNOWN'),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"Error fetching current price for {ticker}: {e}")
            return None
    
    def get_historical_prices(
        self, 
        ticker: str, 
        start_date: str, 
        end_date: str,
        interval: str = '1d'
    ) -> Optional[List[Dict]]:
        """
        Get historical price data
        
        Args:
            ticker: Stock ticker symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            interval: Data interval (1d, 1wk, 1mo)
            
        Returns:
            List of historical price dictionaries or None
        """
        try:
            stock = yf.Ticker(ticker, session=self.session)
            hist = stock.history(start=start_date, end=end_date, interval=interval)
            
            if hist.empty:
                return None
            
            # Convert to list of dictionaries
            history = []
            for date, row in hist.iterrows():
                history.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'open': float(row['Open']),
                    'high': float(row['High']),
                    'low': float(row['Low']),
                    'close': float(row['Close']),
                    'volume': int(row['Volume'])
                })
            
            return history
            
        except Exception as e:
            print(f"Error fetching historical prices for {ticker}: {e}")
            return None
    
    def get_market_indices(self) -> Dict:
        """
        Get current values for major market indices
        
        Returns:
            Dictionary with index data
        """
        indices = {
            'sp500': '^GSPC',
            'nasdaq': '^IXIC',
            'dow': '^DJI'
        }
        
        result = {}
        for name, symbol in indices.items():
            price_data = self.get_current_price(symbol)
            if price_data:
                result[name] = {
                    'value': price_data['price'],
                    'change': price_data.get('change'),
                    'change_percent': price_data.get('change_percent'),
                    'timestamp': price_data['timestamp']
                }
        
        return result
    
    def get_price_at_date(self, ticker: str, date: str) -> Optional[float]:
        """
        Get closing price for a specific date
        
        Args:
            ticker: Stock ticker symbol
            date: Date (YYYY-MM-DD)
            
        Returns:
            Closing price or None
        """
        try:
            # Get data for the specific date (may need a range due to weekends/holidays)
            start = datetime.strptime(date, '%Y-%m-%d')
            end = start + timedelta(days=5)
            
            stock = yf.Ticker(ticker, session=self.session)
            hist = stock.history(start=start.strftime('%Y-%m-%d'), end=end.strftime('%Y-%m-%d'))
            
            if not hist.empty:
                # Get the first available close price
                return float(hist.iloc[0]['Close'])
            
            return None
            
        except Exception as e:
            print(f"Error fetching price for {ticker} at {date}: {e}")
            return None
    
    def clear_cache(self):
        """Clear the price data cache"""
        try:
            self.session.cache.clear()
            print("Price cache cleared")
        except Exception as e:
            print(f"Error clearing cache: {e}")
