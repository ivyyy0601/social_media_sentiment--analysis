"""
CNBC News RSS client — free, no API key needed.
Fetches general finance and markets headlines from CNBC.
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import html


class CNBCNewsClient:
    FEEDS = [
        "https://www.cnbc.com/id/10000664/device/rss/rss.html",   # Finance
        "https://www.cnbc.com/id/15839135/device/rss/rss.html",   # Earnings
    ]

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        })

    def fetch_posts(self, ticker: str, limit: int = 20) -> list:
        ticker = ticker.upper().strip()
        all_posts = []
        seen_urls = set()

        for feed_url in self.FEEDS:
            try:
                resp = self.session.get(feed_url, timeout=10)
                if resp.status_code != 200:
                    continue

                root = ET.fromstring(resp.content)

                for item in root.findall(".//item")[: limit // len(self.FEEDS)]:
                    title = html.unescape((item.findtext("title") or "").strip())
                    link = (item.findtext("link") or "").strip()
                    pub_date = item.findtext("pubDate") or ""
                    guid = item.findtext("guid") or link

                    if not title or link in seen_urls:
                        continue

                    # Only keep articles that mention the ticker
                    if ticker not in title.upper() and f"${ticker}" not in title.upper():
                        continue

                    seen_urls.add(link)

                    try:
                        created_at = parsedate_to_datetime(pub_date).astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
                    except Exception:
                        created_at = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')

                    all_posts.append({
                        "id": f"cnbc_{abs(hash(guid))}",
                        "reddit_id": None,
                        "url": link,
                        "subreddit": "cnbc_news",
                        "title": title,
                        "text": title,
                        "author": "CNBC",
                        "created_at": created_at,
                        "timezone": "UTC",
                        "source": "cnbc_news",
                    })

            except Exception as e:
                print(f"[CNBC] Error fetching feed: {e}")

        return all_posts[:limit]
