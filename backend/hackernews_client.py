"""
Hacker News client — free, no API key needed.
Uses Algolia HN Search API to find tech/finance discussions mentioning a ticker.
Great for gauging developer and tech-investor sentiment.
"""

import requests
from datetime import datetime, timezone

TICKER_KEYWORDS = {
    'AAPL':  ['Apple', 'AAPL', 'iPhone', 'Mac', 'iOS'],
    'MSFT':  ['Microsoft', 'MSFT', 'Azure', 'Windows', 'Copilot'],
    'GOOG':  ['Google', 'Alphabet', 'GOOG', 'Gemini', 'YouTube'],
    'GOOGL': ['Google', 'Alphabet', 'GOOGL', 'Gemini'],
    'AMZN':  ['Amazon', 'AMZN', 'AWS', 'Bezos'],
    'NVDA':  ['Nvidia', 'NVDA', 'CUDA', 'GPU', 'Jensen Huang'],
    'META':  ['Meta', 'Facebook', 'Instagram', 'Zuckerberg', 'Llama'],
    'TSLA':  ['Tesla', 'TSLA', 'Elon Musk', 'EV', 'Cybertruck'],
    'AVGO':  ['Broadcom', 'AVGO'],
    'TXN':   ['Texas Instruments', 'TXN'],
    'INTC':  ['Intel', 'INTC'],
    'ASML':  ['ASML', 'lithography', 'EUV'],
    'COHR':  ['Coherent', 'COHR'],
    'SNDK':  ['SanDisk', 'SNDK', 'Western Digital'],
}


class HackerNewsClient:
    SEARCH_URL = "https://hn.algolia.com/api/v1/search"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })

    def fetch_posts(self, ticker: str, limit: int = 20) -> list:
        ticker = ticker.upper().strip()
        keywords = TICKER_KEYWORDS.get(ticker, [ticker])
        # Use the most specific keyword for search
        query = keywords[0]

        try:
            resp = self.session.get(self.SEARCH_URL, params={
                "query": query,
                "tags": "story",
                "hitsPerPage": limit,
            }, timeout=10)

            if resp.status_code != 200:
                print(f"[HackerNews] HTTP {resp.status_code} for {ticker}")
                return []

            hits = resp.json().get("hits", [])
            posts = []

            for hit in hits:
                title = (hit.get("title") or "").strip()
                url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID','')}"
                created_raw = hit.get("created_at", "")
                hit_id = hit.get("objectID", "")
                points = hit.get("points", 0)
                num_comments = hit.get("num_comments", 0)

                if not title:
                    continue

                # Filter: must mention ticker or related keywords
                title_lower = title.lower()
                if not any(kw.lower() in title_lower for kw in keywords):
                    continue

                try:
                    dt = datetime.fromisoformat(created_raw.replace('Z', '+00:00'))
                    created_at = dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
                except Exception:
                    created_at = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')

                text = f"{title} [👍 {points} points, 💬 {num_comments} comments]"

                posts.append({
                    "id": f"hn_{hit_id}",
                    "reddit_id": None,
                    "url": url,
                    "subreddit": "hackernews",
                    "title": title,
                    "text": text,
                    "author": hit.get("author", "unknown"),
                    "created_at": created_at,
                    "timezone": "UTC",
                    "source": "hackernews",
                })

            return posts

        except Exception as e:
            print(f"[HackerNews] Error for {ticker}: {e}")
            return []
