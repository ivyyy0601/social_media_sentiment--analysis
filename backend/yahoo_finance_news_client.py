"""
Yahoo Finance News RSS client — completely free, no API key needed.
Fetches financial news headlines for a stock ticker.
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


class YahooFinanceNewsClient:
    RSS_URL = "https://feeds.finance.yahoo.com/rss/2.0/headline"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "finance-sentiment-dashboard/1.0"})

    def fetch_posts(self, ticker: str, limit: int = 20) -> list:
        """
        Fetch Yahoo Finance news headlines for a ticker via RSS.
        Returns list of posts in the same schema as RedditRSSClient.
        """
        ticker = ticker.upper().strip()
        params = {"s": ticker, "region": "US", "lang": "en-US"}

        try:
            resp = self.session.get(self.RSS_URL, params=params, timeout=10)
            if resp.status_code != 200:
                print(f"[YahooNews] HTTP {resp.status_code} for {ticker}")
                return []

            root = ET.fromstring(resp.content)
            channel = root.find("channel")
            if channel is None:
                return []

            items = channel.findall("item")[:limit]
            posts = []

            for item in items:
                title = (item.findtext("title") or "").strip()
                description = (item.findtext("description") or "").strip()
                link = (item.findtext("link") or "").strip()
                pub_date = item.findtext("pubDate") or ""
                guid = item.findtext("guid") or link

                if not title:
                    continue

                # Parse publish date
                try:
                    created_at = parsedate_to_datetime(pub_date).astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
                except Exception:
                    created_at = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')

                # Combine title + description as text
                text = title
                if description and description != title:
                    text = f"{title}. {description}"

                posts.append({
                    "id": f"yf_{abs(hash(guid))}",
                    "reddit_id": None,
                    "url": link,
                    "subreddit": "yahoo_finance_news",
                    "title": title,
                    "text": text,
                    "author": "Yahoo Finance",
                    "created_at": created_at,
                    "timezone": "UTC",
                    "source": "yahoo_finance",
                })

            return posts

        except Exception as e:
            print(f"[YahooNews] Error fetching {ticker}: {e}")
            return []
