import re
import json
import os


class TickerExtractor:
    """Extract and validate stock ticker symbols from text"""
    
    # Common false positives to exclude (common English words that look like tickers)
    EXCLUDED_WORDS = {
        'US', 'USA', 'IT', 'AT', 'ON', 'OR', 'AND', 'THE', 'TO', 'A', 'I', 
        'FOR', 'OF', 'IN', 'IS', 'BE', 'ARE', 'AS', 'BY', 'AN', 'IF', 'SO', 
        'DO', 'GO', 'NO', 'UP', 'OUT', 'NOW', 'ALL', 'NEW', 'OLD', 'SEE', 
        'TWO', 'MAY', 'BIG', 'HE', 'SHE', 'WE', 'WHO', 'WHAT', 'WHEN', 'WHERE',
        'WHY', 'HOW', 'CAN', 'WILL', 'HAS', 'HAD', 'WAS', 'WERE', 'BEEN',
        'HAVE', 'THIS', 'THAT', 'THESE', 'THOSE', 'BUT', 'FROM', 'WITH',
        'THEY', 'THEIR', 'THERE', 'THEN', 'THAN', 'THEM', 'SOME', 'ANY',
        'MANY', 'MUCH', 'MORE', 'MOST', 'SUCH', 'VERY', 'JUST', 'ONLY',
        'ALSO', 'EACH', 'BOTH', 'FEW', 'LESS', 'CEO', 'CFO', 'CTO', 'COO',
        'IPO', 'ETF', 'SEC', 'NYSE', 'NASDAQ', 'DOW', 'SP', 'WSB', 'DD',
        'YOLO', 'FOMO', 'FUD', 'IMO', 'TBH', 'ASAP', 'FYI', 'BTW', 'LOL',
        'OMG', 'WTF', 'IMHO', 'ELI', 'TL', 'DR', 'TLDR', 'ETA',
        'AMA', 'PSA', 'OC', 'NSFW', 'SFW', 'EDIT', 'UPDATE', 'PM', 'AM',
        'EST', 'PST', 'MST', 'CST', 'GMT', 'UTC', 'UK', 'EU', 'NA'
    }
    
    def __init__(self, known_tickers_file='known_tickers.json'):
        """
        Initialize the ticker extractor
        
        Args:
            known_tickers_file: Path to JSON file containing list of valid tickers
        """
        self.known_tickers = self._load_known_tickers(known_tickers_file)
    
    def _load_known_tickers(self, filename):
        """
        Load list of known valid tickers from JSON file
        
        Args:
            filename: Name of the JSON file containing ticker list
            
        Returns:
            Set of valid ticker symbols
        """
        try:
            file_path = os.path.join(os.path.dirname(__file__), filename)
            with open(file_path, 'r') as f:
                tickers = json.load(f)
                return set(tickers)
        except Exception as e:
            print(f"Warning: Could not load known tickers from {filename}: {e}")
            return set()
    
    def extract_tickers(self, text):
        if not text:
            return []

        tickers = set()

        # Pattern 1: Cashtags ($AAPL, $tsla)
        cashtag_pattern = r'\$([A-Za-z]{1,5})\b'
        cashtags = [c.upper() for c in re.findall(cashtag_pattern, text)]
        for sym in cashtags:
            if sym in self.known_tickers:
                tickers.add(sym)

        # Pattern 2: Words 1-5 letters (case-insensitive), validate via known_tickers
        word_pattern = r'\b([A-Za-z]{1,5})\b'
        candidates = re.findall(word_pattern, text)
        for c in candidates:
            sym = c.upper()
            # If it is a known ticker, accept it (known_tickers is the final authority)
            if sym in self.known_tickers:
                tickers.add(sym)

        # Pattern 3: Dot notation (BRK.B)
        dot_pattern = r'\b([A-Za-z]{2,4}\.[A-Za-z])\b'
        dot_tickers = [t.upper() for t in re.findall(dot_pattern, text)]
        for sym in dot_tickers:
            if sym in self.known_tickers:
                tickers.add(sym)

        return sorted(tickers)

    
    def extract_with_context(self, text, context_chars=20):
        """
        Extract tickers with surrounding context for verification
        
        Args:
            text: Input text to extract tickers from
            context_chars: Number of characters to include before/after ticker
            
        Returns:
            List of dictionaries with ticker and context
        """
        tickers = self.extract_tickers(text)
        results = []
        
        for ticker in tickers:
            # Find all occurrences of this ticker
            patterns = [
                rf'\${ticker}\b',  # Cashtag version
                rf'\b{ticker}\b'   # Standalone version
            ]
            
            for pattern in patterns:
                for match in re.finditer(pattern, text):
                    start = max(0, match.start() - context_chars)
                    end = min(len(text), match.end() + context_chars)
                    context = text[start:end]
                    
                    results.append({
                        'ticker': ticker,
                        'context': context,
                        'position': match.start()
                    })
                    break  # Only need one occurrence per pattern
        
        return results
