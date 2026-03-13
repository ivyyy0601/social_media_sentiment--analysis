"""
SEC EDGAR client — free, no API key needed.
Fetches official 8-K filings (earnings, material events) for a specific ticker.
8-K filings are the highest-quality signal: earnings results, major announcements, leadership changes.
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone


# Map common tickers to their SEC CIK numbers
TICKER_TO_CIK = {
    'AAPL':  '0000320193',
    'MSFT':  '0000789019',
    'GOOG':  '0001652044',
    'GOOGL': '0001652044',
    'AMZN':  '0001018724',
    'NVDA':  '0001045810',
    'META':  '0001326801',
    'TSLA':  '0001318605',
    'AVGO':  '0001730168',
    'TXN':   '0000097476',
    'INTC':  '0000050863',
    'ASML':  '0000937556',
    'COHR':  '0000021510',
    'SNDK':  '0001000180',
}

ATOM_NS = 'http://www.w3.org/2005/Atom'


class SECEdgarClient:
    BASE_URL = "https://www.sec.gov/cgi-bin/browse-edgar"

    def __init__(self):
        self.session = requests.Session()
        # SEC requires a descriptive User-Agent
        self.session.headers.update({
            "User-Agent": "FinanceSentimentBot/1.0 (research@example.com)"
        })

    def fetch_posts(self, ticker: str, limit: int = 10) -> list:
        ticker = ticker.upper().strip()
        cik = TICKER_TO_CIK.get(ticker)
        if not cik:
            return []

        try:
            resp = self.session.get(self.BASE_URL, params={
                "action": "getcompany",
                "CIK": cik,
                "type": "8-K",
                "dateb": "",
                "owner": "include",
                "count": limit,
                "output": "atom",
            }, timeout=10)

            if resp.status_code != 200:
                print(f"[SEC EDGAR] HTTP {resp.status_code} for {ticker}")
                return []

            root = ET.fromstring(resp.content)
            ns = {'atom': ATOM_NS}
            posts = []

            for entry in root.findall('atom:entry', ns):
                title = (entry.findtext('atom:title', '', ns) or '').strip()
                link_el = entry.find('atom:link', ns)
                link = link_el.attrib.get('href', '') if link_el is not None else ''
                updated = entry.findtext('atom:updated', '', ns)
                entry_id = entry.findtext('atom:id', '', ns)

                if not title:
                    continue

                try:
                    dt = datetime.fromisoformat(updated.replace('Z', '+00:00'))
                    created_at = dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
                except Exception:
                    created_at = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')

                text = f"{ticker} SEC Filing: {title}"

                posts.append({
                    "id": f"sec_{abs(hash(entry_id or link))}",
                    "reddit_id": None,
                    "url": link,
                    "subreddit": "sec_edgar",
                    "title": f"[SEC 8-K] {ticker}: {title}",
                    "text": text,
                    "author": "SEC EDGAR",
                    "created_at": created_at,
                    "timezone": "UTC",
                    "source": "sec_edgar",
                })

            return posts

        except Exception as e:
            print(f"[SEC EDGAR] Error for {ticker}: {e}")
            return []
