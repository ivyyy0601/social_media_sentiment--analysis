import os
import json
import time
import random
import requests
from datetime import datetime, timezone
from dateutil import parser

class XSearchClient:
    """Fetch tweets via X API v2 Recent Search.
    Output schema aligned with RedditRSSClient.
    """

    def __init__(self, config_path="config.json"):
        config = self._load_config(config_path)
        self.bearer_token = config.get("bearer_token") or os.getenv("X_BEARER_TOKEN")
        self.default_query = config.get("default_query", "stocks lang:en -is:retweet")
        self.json_page_limit = int(config.get("json_page_limit", 100))
        self.max_pages = int(config.get("max_pages", 10))
        self.sleep_sec = float(config.get("sleep_sec", 0.8))
        self.max_retries = int(config.get("max_retries", 5))

        self.base_url = "https://api.x.com/2/tweets/search/recent"  # 有些账号也可用 api.twitter.com

        if not self.bearer_token:
            raise ValueError("Missing X bearer token. Put it in config.json (x.bearer_token) or env X_BEARER_TOKEN")

    def _load_config(self, config_path):
        try:
            full_path = os.path.join(os.path.dirname(__file__), config_path)
            with open(full_path, "r") as f:
                data = json.load(f)
                return data.get("x", {})
        except Exception:
            return {}

    def _requests_get_with_backoff(self, url, headers, params, timeout=15):
        for attempt in range(self.max_retries):
            try:
                resp = requests.get(url, headers=headers, params=params, timeout=timeout)
                if resp.status_code in (429, 500, 502, 503, 504):
                    time.sleep((2 ** attempt) + random.random())
                    continue
                resp.raise_for_status()
                return resp
            except Exception:
                time.sleep((2 ** attempt) + random.random())
        resp = requests.get(url, headers=headers, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp

    def _in_date_range(self, created_at_iso, start_date=None, end_date=None):
        if not start_date and not end_date:
            return True
        try:
            d = parser.isoparse(created_at_iso).date().isoformat()
            if start_date and d < start_date:
                return False
            if end_date and d > end_date:
                return False
            return True
        except Exception:
            return True

    def fetch_posts(self, query=None, max_results=100, start_date=None, end_date=None):
        if max_results <= 0:
            return []

        q = query or self.default_query
        per_page = max(10, min(100, int(self.json_page_limit)))

        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "User-Agent": "finance-sentiment-x/1.0",
        }

        # tweet.fields + expansions + user.fields 用来拿 author 名字/时间/指标
        params = {
            "query": q,
            "max_results": per_page,
            "tweet.fields": "created_at,public_metrics,lang,author_id",
            "expansions": "author_id",
            "user.fields": "username,name",
        }

        collected = []
        seen_ids = set()
        next_token = None
        pages = 0

        while pages < self.max_pages and len(collected) < max_results:
            pages += 1
            if next_token:
                params["next_token"] = next_token
            else:
                params.pop("next_token", None)

            resp = self._requests_get_with_backoff(self.base_url, headers=headers, params=params, timeout=15)
            data = resp.json() or {}

            tweets = data.get("data") or []
            includes = data.get("includes") or {}
            users = {u["id"]: u for u in (includes.get("users") or []) if "id" in u}

            for t in tweets:
                tid = t.get("id")
                if not tid or tid in seen_ids:
                    continue

                created_at = t.get("created_at") or datetime.now(timezone.utc).isoformat()
                if not self._in_date_range(created_at, start_date, end_date):
                    continue

                author_id = t.get("author_id")
                u = users.get(author_id, {}) if author_id else {}
                author = u.get("username") or u.get("name") or "unknown"

                text = t.get("text") or ""
                url = f"https://x.com/{author}/status/{tid}" if author != "unknown" else f"https://x.com/i/web/status/{tid}"

                metrics = t.get("public_metrics") or {}
                post = {
                    "id": f"x_{tid}",
                    "reddit_id": None,          # 保持兼容：你也可以不放
                    "url": url,
                    "subreddit": None,          # 同上
                    "title": text[:80],
                    "text": text,
                    "author": author,
                    "author_id": author_id or author,
                    "created_at": created_at,
                    "timezone": "UTC",
                    "link": url,
                    "metrics": {
                        "like": metrics.get("like_count", 0),
                        "retweet": metrics.get("retweet_count", 0),
                        "reply": metrics.get("reply_count", 0),
                        "quote": metrics.get("quote_count", 0),
                    },
                    "source": "x",
                }

                seen_ids.add(tid)
                collected.append(post)
                if len(collected) >= max_results:
                    break

            meta = data.get("meta") or {}
            next_token = meta.get("next_token")
            if not next_token:
                break

            time.sleep(self.sleep_sec)

        return collected[:max_results]
