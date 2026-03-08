"""
Export service for converting data to various formats (CSV, JSON).
"""

import csv
import json
from io import StringIO
from typing import List, Dict
from datetime import datetime


class ExportService:
    """Handle data export to CSV and JSON formats"""
    
    @staticmethod
    def export_posts_to_csv(posts: List[Dict]) -> str:
        """
        Export posts to CSV format
        
        Args:
            posts: List of post dictionaries
            
        Returns:
            CSV string
        """
        if not posts:
            return ""
        
        output = StringIO()
        
        # Define CSV headers
        headers = [
            'id', 'title', 'text', 'author', 'subreddit', 
            'url', 'created_at', 'sentiment_label', 'sentiment_score',
            'tickers'
        ]
        
        writer = csv.DictWriter(output, fieldnames=headers, extrasaction='ignore')
        writer.writeheader()
        
        for post in posts:
            # Prepare post data for CSV
            row = {
                'id': post.get('id', ''),
                'title': post.get('title', ''),
                'text': post.get('text', '').replace('\n', ' ').replace('\r', ''),
                'author': post.get('author', ''),
                'subreddit': post.get('subreddit', ''),
                'url': post.get('url', ''),
                'created_at': post.get('created_at', ''),
                'sentiment_label': post.get('sentiment_label', ''),
                'sentiment_score': post.get('sentiment_score', ''),
                'tickers': ','.join(post.get('tickers', []))
            }
            writer.writerow(row)
        
        return output.getvalue()
    
    @staticmethod
    def export_posts_to_json(posts: List[Dict]) -> str:
        """
        Export posts to JSON format
        
        Args:
            posts: List of post dictionaries
            
        Returns:
            JSON string
        """
        return json.dumps({
            'posts': posts,
            'count': len(posts),
            'exported_at': datetime.utcnow().isoformat()
        }, indent=2)
    
    @staticmethod
    def export_sentiment_trends_to_csv(trends: List[Dict]) -> str:
        """
        Export sentiment trends to CSV
        
        Args:
            trends: List of trend dictionaries
            
        Returns:
            CSV string
        """
        if not trends:
            return ""
        
        output = StringIO()
        
        headers = ['date', 'positive', 'negative', 'neutral', 'total']
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        
        for trend in trends:
            total = trend.get('positive', 0) + trend.get('negative', 0) + trend.get('neutral', 0)
            row = {
                'date': trend.get('date', ''),
                'positive': trend.get('positive', 0),
                'negative': trend.get('negative', 0),
                'neutral': trend.get('neutral', 0),
                'total': total
            }
            writer.writerow(row)
        
        return output.getvalue()
    
    @staticmethod
    def export_sentiment_trends_to_json(trends: List[Dict]) -> str:
        """
        Export sentiment trends to JSON
        
        Args:
            trends: List of trend dictionaries
            
        Returns:
            JSON string
        """
        return json.dumps({
            'trends': trends,
            'count': len(trends),
            'exported_at': datetime.utcnow().isoformat()
        }, indent=2)
    
    @staticmethod
    def export_stats_to_json(stats: Dict) -> str:
        """
        Export statistics to JSON
        
        Args:
            stats: Statistics dictionary
            
        Returns:
            JSON string
        """
        return json.dumps({
            'stats': stats,
            'exported_at': datetime.utcnow().isoformat()
        }, indent=2)
