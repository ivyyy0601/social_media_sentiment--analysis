import json
import os


class IndustryClassifier:
    """Map tickers to industries and sectors based on configuration"""
    
    def __init__(self, mappings_file='ticker_mappings.json'):
        """
        Initialize the industry classifier
        
        Args:
            mappings_file: Path to JSON file containing ticker to industry/sector mappings
        """
        self.mappings = self._load_mappings(mappings_file)
    
    def _load_mappings(self, filename):
        """
        Load ticker to industry/sector mappings from JSON file
        
        Args:
            filename: Name of the JSON file containing mappings
            
        Returns:
            Dictionary mapping tickers to company/sector/industry info
        """
        try:
            file_path = os.path.join(os.path.dirname(__file__), filename)
            with open(file_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load ticker mappings from {filename}: {e}")
            return {}
    
    def get_ticker_info(self, ticker):
        """
        Get company, sector, and industry information for a ticker
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Dictionary with company, sector, and industry, or None if not found
        """
        return self.mappings.get(ticker)
    
    def get_sector(self, ticker):
        """
        Get sector for a ticker
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Sector name or None if not found
        """
        info = self.get_ticker_info(ticker)
        return info['sector'] if info else None
    
    def get_industry(self, ticker):
        """
        Get industry for a ticker
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Industry name or None if not found
        """
        info = self.get_ticker_info(ticker)
        return info['industry'] if info else None
    
    def get_company_name(self, ticker):
        """
        Get company name for a ticker
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Company name or None if not found
        """
        info = self.get_ticker_info(ticker)
        return info['company'] if info else None
    
    def get_tickers_by_sector(self, sector):
        """
        Get all tickers in a specific sector
        
        Args:
            sector: Sector name
            
        Returns:
            List of ticker symbols in the sector
        """
        return [
            ticker for ticker, info in self.mappings.items()
            if info.get('sector') == sector
        ]
    
    def get_tickers_by_industry(self, industry):
        """
        Get all tickers in a specific industry
        
        Args:
            industry: Industry name
            
        Returns:
            List of ticker symbols in the industry
        """
        return [
            ticker for ticker, info in self.mappings.items()
            if info.get('industry') == industry
        ]
    
    def get_all_sectors(self):
        """
        Get list of all unique sectors
        
        Returns:
            Sorted list of sector names
        """
        sectors = set(info['sector'] for info in self.mappings.values() if 'sector' in info)
        return sorted(list(sectors))
    
    def get_all_industries(self):
        """
        Get list of all unique industries
        
        Returns:
            Sorted list of industry names
        """
        industries = set(info['industry'] for info in self.mappings.values() if 'industry' in info)
        return sorted(list(industries))
    
    def classify_post_tickers(self, tickers):
        """
        Get all sectors and industries for a list of tickers
        
        Args:
            tickers: List of ticker symbols
            
        Returns:
            Dictionary with 'sectors' and 'industries' lists
        """
        sectors = set()
        industries = set()
        
        for ticker in tickers:
            info = self.get_ticker_info(ticker)
            if info:
                if 'sector' in info:
                    sectors.add(info['sector'])
                if 'industry' in info:
                    industries.add(info['industry'])
        
        return {
            'sectors': sorted(list(sectors)),
            'industries': sorted(list(industries))
        }
