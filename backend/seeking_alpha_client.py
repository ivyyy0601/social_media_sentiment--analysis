"""
Seeking Alpha RSS client — free, no API key needed.
Fetches stock-specific news and analysis for a ticker.
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import html


class SeekingAlphaClient:
    RSS_URL = "https://seekingalpha.com/api/sa/combined/{ticker}.xml"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        })

    def fetch_posts(self, ticker: str, limit: int = 20) -> list:
        ticker = ticker.upper().strip()
        url = self.RSS_URL.format(ticker=ticker)

        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                print(f"[SeekingAlpha] HTTP {resp.status_code} for {ticker}")
                return []

            root = ET.fromstring(resp.content)
            posts = []
            seen_urls = set()

            for item in root.findall(".//item")[:limit]:
                title = html.unescape((item.findtext("title") or "").strip())
                link = (item.findtext("link") or "").strip()
                pub_date = item.findtext("pubDate") or ""
                guid = item.findtext("guid") or link

                if not title or link in seen_urls:
                    continue
                seen_urls.add(link)

                try:
                    created_at = parsedate_to_datetime(pub_date).astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
                except Exception:
                    created_at = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')

                posts.append({
                    "id": f"sa_{abs(hash(guid))}",
                    "reddit_id": None,
                    "url": link,
                    "subreddit": "seeking_alpha",
                    "title": title,
                    "text": title,
                    "author": "Seeking Alpha",
                    "created_at": created_at,
                    "timezone": "UTC",
                    "source": "seeking_alpha",
                })

            return posts

        except Exception as e:
            print(f"[SeekingAlpha] Error for {ticker}: {e}")
            return []
