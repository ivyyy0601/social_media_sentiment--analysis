import os
import time
import requests
from datetime import datetime, timezone

class AlphaVantageNewsClient:
    """
    Fetch AlphaVantage NEWS_SENTIMENT as unified 'post' objects
    """

    def __init__(self, api_key=None, sleep_sec=15.0):
        self.api_key = api_key or os.getenv("ALPHAVANTAGE_API_KEY")
        self.sleep_sec = float(sleep_sec)
        self.base_url = "https://www.alphavantage.co/query"

        if not self.api_key:
            raise ValueError("Missing AlphaVantage API key")

    def fetch_posts(self, tickers=None, limit=200):
        params = {
            "function": "NEWS_SENTIMENT",
            "apikey": self.api_key,
            "limit": min(int(limit), 200),
        }
        if tickers:
            params["tickers"] = tickers

        r = requests.get(self.base_url, params=params, timeout=30)
        data = r.json()

        feed = data.get("feed", [])
        posts = []

        for item in feed:
            title = item.get("title", "")
            summary = item.get("summary", "")
            url = item.get("url", "")
            source = item.get("source", "news")
            authors = item.get("authors", "")

            tp = item.get("time_published")
            try:
                created_at = datetime.strptime(tp, "%Y%m%dT%H%M%S").replace(
                    tzinfo=timezone.utc
                ).isoformat()
            except Exception:
                created_at = datetime.now(timezone.utc).isoformat()

            text = (title + "\n\n" + summary).strip()

            post = {
                "id": f"news_{abs(hash(url or title))}",
                "reddit_id": "",
                "url": url,
                "subreddit": "news",
                "title": title,
                "text": text,
                "author": authors or source,
                "author_id": authors or source,
                "created_at": created_at,
                "timezone": "UTC",
                "link": url,
                "metrics": {
                    "overall_sentiment_score": item.get("overall_sentiment_score"),
                    "overall_sentiment_label": item.get("overall_sentiment_label"),
                },
                "source": "news",
            }

            posts.append(post)

        time.sleep(self.sleep_sec)
        return posts
