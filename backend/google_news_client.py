"""
Google News RSS client — completely free, no API key needed.
Aggregates news from hundreds of sources for any stock ticker.
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import html


class GoogleNewsClient:
    RSS_URL = "https://news.google.com/rss/search"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; finance-sentiment-bot/1.0)"
        })

    def fetch_posts(self, ticker: str, limit: int = 30) -> list:
        ticker = ticker.upper().strip()
        # Search for stock-related news
        queries = [
            f"{ticker} stock",
            f"${ticker} earnings",
        ]
        all_posts = []
        seen_urls = set()

        for q in queries:
            params = {
                "q": q,
                "hl": "en-US",
                "gl": "US",
                "ceid": "US:en"
            }
            try:
                resp = self.session.get(self.RSS_URL, params=params, timeout=10)
                if resp.status_code != 200:
                    continue

                root = ET.fromstring(resp.content)
                channel = root.find("channel")
                if channel is None:
                    continue

                for item in channel.findall("item")[: limit // len(queries)]:
                    title = html.unescape((item.findtext("title") or "").strip())
                    link = (item.findtext("link") or "").strip()
                    pub_date = item.findtext("pubDate") or ""
                    guid = item.findtext("guid") or link

                    if not title or link in seen_urls:
                        continue
                    seen_urls.add(link)

                    try:
                        created_at = parsedate_to_datetime(pub_date).isoformat()
                    except Exception:
                        created_at = datetime.now(timezone.utc).isoformat()

                    all_posts.append({
                        "id": f"gn_{abs(hash(guid))}",
                        "reddit_id": None,
                        "url": link,
                        "subreddit": "google_news",
                        "title": title,
                        "text": title,
                        "author": "Google News",
                        "created_at": created_at,
                        "timezone": "UTC",
                        "source": "google_news",
                    })

            except Exception as e:
                print(f"[GoogleNews] Error for {ticker} query '{q}': {e}")

        return all_posts[:limit]
