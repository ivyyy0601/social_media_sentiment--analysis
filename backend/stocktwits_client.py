"""
StockTwits client — free public API, no credentials needed.
Fetches recent messages for a stock ticker.
"""

import requests
from datetime import datetime, timezone


class StockTwitsClient:
    BASE_URL = "https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"

    def __init__(self, limit=30):
        self.limit = limit
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "finance-sentiment-dashboard/1.0"})

    def fetch_posts(self, ticker: str, limit: int = None) -> list:
        """
        Fetch recent StockTwits messages for a ticker.
        Returns list of posts in the same schema as RedditRSSClient.
        """
        ticker = ticker.upper().strip()
        limit = limit or self.limit
        url = self.BASE_URL.format(ticker=ticker)

        try:
            resp = self.session.get(url, params={"limit": min(limit, 30)}, timeout=10)
            if resp.status_code == 429:
                print(f"[StockTwits] Rate limited for {ticker}")
                return []
            if resp.status_code != 200:
                print(f"[StockTwits] HTTP {resp.status_code} for {ticker}")
                return []

            data = resp.json()
            messages = data.get("messages", [])
            posts = []

            for msg in messages:
                body = msg.get("body", "").strip()
                if not body or len(body) < 10:
                    continue

                created_raw = msg.get("created_at", "")
                try:
                    created_at = datetime.fromisoformat(
                        created_raw.replace("Z", "+00:00")
                    ).isoformat()
                except Exception:
                    created_at = datetime.now(timezone.utc).isoformat()

                username = msg.get("user", {}).get("username", "unknown")
                msg_id = str(msg.get("id", ""))

                posts.append({
                    "id": f"st_{msg_id}",
                    "reddit_id": None,
                    "url": f"https://stocktwits.com/message/{msg_id}",
                    "subreddit": "stocktwits",
                    "title": f"${ticker}: {body[:80]}",
                    "text": body,
                    "author": username,
                    "created_at": created_at,
                    "timezone": "UTC",
                    "source": "stocktwits",
                })

            return posts

        except Exception as e:
            print(f"[StockTwits] Error fetching {ticker}: {e}")
            return []
