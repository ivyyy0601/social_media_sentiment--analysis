"""
Motley Fool RSS client — free, no API key needed.
Fetches financial analysis articles, filtered by ticker mention.
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import html

# Company names to help match articles (supplement ticker symbol search)
TICKER_COMPANY_NAMES = {
    'AAPL': ['Apple'],
    'MSFT': ['Microsoft'],
    'GOOG': ['Alphabet', 'Google'],
    'GOOGL': ['Alphabet', 'Google'],
    'AMZN': ['Amazon'],
    'NVDA': ['Nvidia', 'NVIDIA'],
    'META': ['Meta', 'Facebook'],
    'TSLA': ['Tesla'],
    'AVGO': ['Broadcom'],
    'TXN': ['Texas Instruments'],
    'INTC': ['Intel'],
    'ASML': ['ASML'],
    'COHR': ['Coherent', 'II-VI'],
    'SNDK': ['SanDisk', 'Western Digital'],
}

FEED_URL = "https://www.fool.com/feeds/index.aspx?id=fool-headlines"


class MotleyFoolClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        })

    def fetch_posts(self, ticker: str, limit: int = 15) -> list:
        ticker = ticker.upper().strip()
        keywords = [ticker] + TICKER_COMPANY_NAMES.get(ticker, [])

        try:
            resp = self.session.get(FEED_URL, timeout=10, allow_redirects=True)
            if resp.status_code != 200:
                print(f"[MotleyFool] HTTP {resp.status_code}")
                return []

            root = ET.fromstring(resp.content)
            posts = []
            seen_urls = set()

            for item in root.findall('.//item'):
                title = html.unescape((item.findtext('title') or '').strip())
                link = (item.findtext('link') or '').strip()
                pub_date = item.findtext('pubDate') or ''
                guid = item.findtext('guid') or link

                if not title or link in seen_urls:
                    continue

                # Filter: only keep articles mentioning the ticker or company name
                title_upper = title.upper()
                if not any(kw.upper() in title_upper for kw in keywords):
                    continue

                seen_urls.add(link)

                try:
                    created_at = parsedate_to_datetime(pub_date).astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
                except Exception:
                    created_at = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')

                posts.append({
                    "id": f"mf_{abs(hash(guid))}",
                    "reddit_id": None,
                    "url": link,
                    "subreddit": "motley_fool",
                    "title": title,
                    "text": title,
                    "author": "Motley Fool",
                    "created_at": created_at,
                    "timezone": "UTC",
                    "source": "motley_fool",
                })

                if len(posts) >= limit:
                    break

            return posts

        except Exception as e:
            print(f"[MotleyFool] Error for {ticker}: {e}")
            return []
