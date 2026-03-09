import os
import json
import re
import requests
import html
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from dateutil import parser, tz


class RedditRSSClient:
    """Fetch finance posts from subreddit RSS feeds without API credentials."""

    def __init__(self, config_path='config.json'):
        config = self._load_config(config_path)
        self.subreddits = config.get('subreddits', ['stocks', 'investing', 'wallstreetbets', 'finance'])
        self.user_agent = config.get('user_agent', 'finance-sentiment-rss/0.1')
        self.default_query = config.get('default_query', 'stocks OR finance OR investing')
        self.base_url = 'https://www.reddit.com'
        
        # Content filtering patterns
        self.filter_patterns = config.get('filter_patterns', {
            'exclude_titles': [
                r'daily.*discussion',
                r'general.*discussion',
                r'advice.*thread',
                r'what.*are.*your.*moves',
                r'weekend.*discussion',
                r'discussion.*thread',
                r'daily.*thread'
            ],
            'exclude_keywords': [
                'which niche',
                'wanted to talk to but',
                'career advice',
                'networking',
                'should i',
                'how do i become',
                'resume',
                'job interview'
            ]
        })

    def _load_config(self, config_path):
        """Load Reddit configuration from config.json"""
        try:
            full_path = os.path.join(os.path.dirname(__file__), config_path)
            with open(full_path, 'r') as f:
                data = json.load(f)
                return data.get('reddit', {})
        except Exception as e:
            print(f"Warning: Could not load config from {config_path}: {e}")
            return {}
    
    def _should_filter_post(self, title, text):
        """
        Determine if a post should be filtered out based on content.
        
        Args:
            title: Post title
            text: Post content
            
        Returns:
            True if post should be filtered out, False otherwise
        """
        title_lower = title.lower()
        text_lower = text.lower()
        combined = f"{title_lower} {text_lower}"
        
        # Check title patterns
        for pattern in self.filter_patterns.get('exclude_titles', []):
            if re.search(pattern, title_lower, re.IGNORECASE):
                return True
        
        # Check keywords in combined text
        for keyword in self.filter_patterns.get('exclude_keywords', []):
            if keyword.lower() in combined:
                return True
        
        return False
    
    def _filter_by_date_range(self, posts, start_date=None, end_date=None):
        """
        Filter posts by date range
        
        Args:
            posts: List of post dictionaries
            start_date: ISO format start date (YYYY-MM-DD)
            end_date: ISO format end date (YYYY-MM-DD)
            
        Returns:
            Filtered list of posts
        """
        if not start_date and not end_date:
            return posts
        
        filtered = []
        for post in posts:
            try:
                # Parse post creation date
                post_date = parser.isoparse(post.get('created_at', ''))
                post_date_str = post_date.date().isoformat()
                
                # Check against date range
                if start_date and post_date_str < start_date:
                    continue
                if end_date and post_date_str > end_date:
                    continue
                
                filtered.append(post)
            except Exception as e:
                # If date parsing fails, include the post
                filtered.append(post)
        
        return filtered

    def fetch_posts(self, query=None, max_results=10, start_date=None, end_date=None):
        """
        Fetch recent posts via RSS across configured subreddits.
        
        Args:
            query: Search query string
            max_results: Maximum number of posts to fetch
            start_date: ISO format start date (YYYY-MM-DD) for filtering
            end_date: ISO format end date (YYYY-MM-DD) for filtering
            
        Returns:
            List of post dictionaries
        """
        if max_results <= 0:
            return []

        search_query = query or self.default_query
        headers = {'User-Agent': self.user_agent}

        collected = []
        per_sub_limit = max(1, min(50, max_results // max(len(self.subreddits), 1) + 1))

        for sub in self.subreddits or ['stocks', 'investing']:
            if len(collected) >= max_results:
                break

            url = f"{self.base_url}/r/{sub}/search.rss"
            params = {
                'q': search_query,
                'restrict_sr': 'on',
                'sort': 'new',
                'limit': per_sub_limit,
            }
            
            # Add time filter if dates are specified
            if start_date or end_date:
                # Reddit RSS doesn't support exact date ranges via API
                # We'll fetch more posts and filter them on our side
                # Use 't' parameter for time windows
                params['t'] = 'all'  # Get posts from all time
                params['limit'] = min(100, per_sub_limit * 3)  # Fetch more to filter
            
            try:
                resp = requests.get(url, headers=headers, params=params, timeout=10)
                resp.raise_for_status()
                posts = self._parse_feed(resp.content, sub)
                
                # Filter by date range if specified
                if start_date or end_date:
                    posts = self._filter_by_date_range(posts, start_date, end_date)
                
                for post in posts:
                    # Apply content filtering
                    if self._should_filter_post(post.get('title', ''), post.get('text', '')):
                        continue
                    
                    if len(collected) >= max_results:
                        break
                    collected.append(post)
            except Exception as exc:
                print(f"Error fetching RSS for r/{sub}: {exc}")
                continue

        return collected[:max_results]

    def _parse_timestamp_with_timezone(self, timestamp_str):
        """
        Parse timestamp preserving timezone info
        
        Args:
            timestamp_str: ISO format timestamp string
            
        Returns:
            Tuple of (iso_timestamp, timezone_name)
        """
        try:
            dt = parser.isoparse(timestamp_str)
            # If no timezone info, assume UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=tz.UTC)
            
            # Get timezone name
            tzname = dt.tzname() or 'UTC'
            
            return dt.isoformat(), tzname
        except Exception:
            # Fallback to current UTC time
            now = datetime.now(tz.UTC)
            return now.isoformat(), 'UTC'
    
    def _parse_feed(self, content, subreddit):
        """
        Parse Atom/RSS entries from Reddit feed content with full metadata extraction
        
        Args:
            content: XML content from RSS feed
            subreddit: Subreddit name
            
        Returns:
            List of post dictionaries with complete metadata
        """
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        try:
            root = ET.fromstring(content)
        except ET.ParseError:
            return []

        entries = root.findall('.//atom:entry', ns)
        results = []
        for entry in entries:
            title_el = entry.find('atom:title', ns)
            summary_el = entry.find('atom:summary', ns)
            updated_el = entry.find('atom:updated', ns)
            published_el = entry.find('atom:published', ns)
            link_el = entry.find('atom:link', ns)
            author_el = entry.find('atom:author/atom:name', ns)
            id_el = entry.find('atom:id', ns)

            # Extract title
            title = html.unescape(title_el.text) if title_el is not None and title_el.text else ''
            
            # Extract summary/content
            summary_raw = summary_el.text or '' if summary_el is not None else ''
            summary = html.unescape(summary_raw)
            
            # Combine title and summary for text content
            text_parts = []
            if title.strip():
                text_parts.append(title.strip())
            if summary.strip():
                text_parts.append(summary.strip())
            text = '\n\n'.join(text_parts) if text_parts else '(no content)'

            # Extract and parse timestamp with timezone
            created_str = (updated_el.text if updated_el is not None else None) or \
                          (published_el.text if published_el is not None else None)
            
            if created_str:
                created_at, timezone = self._parse_timestamp_with_timezone(created_str)
            else:
                now = datetime.now(tz.UTC)
                created_at = now.isoformat()
                timezone = 'UTC'

            # Extract URL (original Reddit post link)
            url = link_el.attrib.get('href') if link_el is not None else ''
            
            # Extract author
            author = author_el.text if author_el is not None else 'unknown'

            # Extract Reddit post ID from entry ID or URL
            raw_id = id_el.text if id_el is not None else url
            
            # Try to extract Reddit ID from the URL or ID
            reddit_id = None
            if raw_id:
                # Reddit IDs are typically at the end of the URL
                parts = raw_id.split('/')
                for part in reversed(parts):
                    if part and part not in ['comments', 'r', subreddit]:
                        reddit_id = part
                        break
            
            if not reddit_id:
                reddit_id = f"post_{len(results)}"
            
            post_id = f'reddit_{reddit_id}'

            results.append({
                'id': post_id,
                'reddit_id': reddit_id,
                'url': url,
                'subreddit': subreddit,
                'title': title,
                'text': text,
                'author': author,
                'author_id': author,  # For backward compatibility
                'created_at': created_at,
                'timezone': timezone,
                'link': url,  # For backward compatibility
                'metrics': {},
            })
        return results
