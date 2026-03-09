import os
import json
import re
import time
import random
import requests
import html
import xml.etree.ElementTree as ET
from datetime import datetime
from dateutil import parser, tz


class RedditRSSClient:
    """Fetch finance posts from subreddit RSS feeds without API credentials.
    Upgraded: search.json (paged) first, RSS fallback.
    """

    def __init__(self, config_path="config.json"):
        config = self._load_config(config_path)
        self.subreddits = config.get("subreddits", ["stocks", "investing", "wallstreetbets", "finance"])
        self.user_agent = config.get("user_agent", "finance-sentiment-rss/1.0")
        self.default_query = config.get("default_query", "stocks OR finance OR investing")
        self.base_url = "https://www.reddit.com"

        # Pagination / rate limit knobs (can be overridden in config)
        self.json_page_limit = int(config.get("json_page_limit", 100))          # max 100
        self.max_pages_per_sub = int(config.get("max_pages_per_sub", 10))      # increase for more data
        self.sleep_sec = float(config.get("sleep_sec", 0.8))                   # be nice to Reddit
        self.max_retries = int(config.get("max_retries", 5))

        # Content filtering patterns
        self.filter_patterns = config.get(
            "filter_patterns",
            {
                "exclude_titles": [
                    r"daily.*discussion",
                    r"general.*discussion",
                    r"advice.*thread",
                    r"what.*are.*your.*moves",
                    r"weekend.*discussion",
                    r"discussion.*thread",
                    r"daily.*thread",
                ],
                "exclude_keywords": [
                    "which niche",
                    "wanted to talk to but",
                    "career advice",
                    "networking",
                    "should i",
                    "how do i become",
                    "resume",
                    "job interview",
                ],
            },
        )

    def _load_config(self, config_path):
        """Load Reddit configuration from config.json"""
        try:
            full_path = os.path.join(os.path.dirname(__file__), config_path)
            with open(full_path, "r") as f:
                data = json.load(f)
                return data.get("reddit", {})
        except Exception as e:
            print(f"Warning: Could not load config from {config_path}: {e}")
            return {}

    def _should_filter_post(self, title, text):
        """Return True if post should be filtered out."""
        title_lower = (title or "").lower()
        text_lower = (text or "").lower()
        combined = f"{title_lower} {text_lower}"

        for pattern in self.filter_patterns.get("exclude_titles", []):
            if re.search(pattern, title_lower, re.IGNORECASE):
                return True

        for keyword in self.filter_patterns.get("exclude_keywords", []):
            if keyword.lower() in combined:
                return True

        return False

    def _in_date_range(self, created_at_iso: str, start_date: str | None, end_date: str | None) -> bool:
        """start_date/end_date: 'YYYY-MM-DD'"""
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
            # if parse fails, keep it
            return True

    def _requests_get_with_backoff(self, url, headers, params, timeout=15):
        """GET with basic 429/5xx retry + exponential backoff."""
        for attempt in range(self.max_retries):
            try:
                resp = requests.get(url, headers=headers, params=params, timeout=timeout)

                # Handle rate limit / server issues
                if resp.status_code in (429, 500, 502, 503, 504):
                    sleep = (2 ** attempt) + random.random()
                    time.sleep(sleep)
                    continue

                resp.raise_for_status()
                return resp
            except Exception:
                sleep = (2 ** attempt) + random.random()
                time.sleep(sleep)

        # last try (let it raise if still failing)
        resp = requests.get(url, headers=headers, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp

    # ---------------------------
    # NEW: JSON search (paged)
    # ---------------------------
    def _fetch_posts_json(self, query, max_results, start_date=None, end_date=None):
        """Fetch posts via search.json with pagination for larger volume."""
        headers = {"User-Agent": self.user_agent}
        collected = []
        seen_fullnames = set()

        # limit per page must be <= 100
        per_page = max(1, min(100, int(self.json_page_limit)))

        for sub in self.subreddits or ["stocks", "investing"]:
            if len(collected) >= max_results:
                break

            after = None
            pages = 0

            while pages < self.max_pages_per_sub and len(collected) < max_results:
                pages += 1
                url = f"{self.base_url}/r/{sub}/search.json"
                params = {
                    "q": query,
                    "restrict_sr": 1,
                    "sort": "new",
                    "t": "all",      # we filter by date ourselves; you can change to 'month' in config if you want
                    "limit": per_page,
                }
                if after:
                    params["after"] = after

                try:
                    resp = self._requests_get_with_backoff(url, headers=headers, params=params, timeout=15)
                    data = resp.json()
                except Exception as exc:
                    print(f"Error fetching JSON for r/{sub}: {exc}")
                    break

                children = (data.get("data", {}) or {}).get("children", []) or []
                if not children:
                    break

                for item in children:
                    p = item.get("data", {}) or {}
                    fullname = p.get("name")  # t3_xxx
                    if not fullname or fullname in seen_fullnames:
                        continue

                    title = p.get("title") or ""
                    selftext = p.get("selftext") or ""
                    created_utc = p.get("created_utc")
                    created_at = (
                        datetime.fromtimestamp(created_utc, tz=tz.UTC).isoformat()
                        if created_utc else datetime.now(tz.UTC).isoformat()
                    )

                    # content filter
                    if self._should_filter_post(title, selftext):
                        continue
                    # date filter
                    if not self._in_date_range(created_at, start_date, end_date):
                        continue

                    subreddit_name = p.get("subreddit") or sub
                    reddit_id = p.get("id") or fullname.replace("t3_", "")
                    permalink = p.get("permalink") or ""
                    url_post = f"{self.base_url}{permalink}" if permalink else (p.get("url") or "")

                    author = p.get("author") or "unknown"

                    post = {
                        "id": f"reddit_{reddit_id}",
                        "reddit_id": reddit_id,
                        "url": url_post,
                        "subreddit": subreddit_name,
                        "title": title,
                        "text": (title.strip() + "\n\n" + selftext.strip()).strip() if selftext else title,
                        "author": author,
                        "author_id": author,  # backward compatibility
                        "created_at": created_at,
                        "timezone": "UTC",
                        "link": url_post,  # backward compatibility
                        "metrics": {},
                    }

                    seen_fullnames.add(fullname)
                    collected.append(post)

                    if len(collected) >= max_results:
                        break

                after = (data.get("data", {}) or {}).get("after")
                if not after:
                    break

                time.sleep(self.sleep_sec)

        return collected[:max_results]

    # ---------------------------
    # Existing RSS flow (fallback)
    # ---------------------------
    def _filter_by_date_range(self, posts, start_date=None, end_date=None):
        if not start_date and not end_date:
            return posts

        filtered = []
        for post in posts:
            try:
                post_date = parser.isoparse(post.get("created_at", ""))
                post_date_str = post_date.date().isoformat()
                if start_date and post_date_str < start_date:
                    continue
                if end_date and post_date_str > end_date:
                    continue
                filtered.append(post)
            except Exception:
                filtered.append(post)
        return filtered

    def fetch_posts(self, query=None, max_results=10, start_date=None, end_date=None):
        """
        Fetch posts across subreddits.
        Now: JSON search first (bigger volume) -> RSS fallback.
        """
        if max_results <= 0:
            return []

        search_query = query or self.default_query

        # 1) JSON first (recommended)
        posts = self._fetch_posts_json(search_query, max_results, start_date=start_date, end_date=end_date)
        if posts:
            return posts

        # 2) RSS fallback (original behavior)
        headers = {"User-Agent": self.user_agent}
        collected = []
        per_sub_limit = max(1, min(50, max_results // max(len(self.subreddits), 1) + 1))

        for sub in self.subreddits or ["stocks", "investing"]:
            if len(collected) >= max_results:
                break

            url = f"{self.base_url}/r/{sub}/search.rss"
            params = {"q": search_query, "restrict_sr": "on", "sort": "new", "limit": per_sub_limit}

            if start_date or end_date:
                params["t"] = "all"
                params["limit"] = min(100, per_sub_limit * 3)

            try:
                resp = requests.get(url, headers=headers, params=params, timeout=10)
                resp.raise_for_status()
                posts = self._parse_feed(resp.content, sub)

                if start_date or end_date:
                    posts = self._filter_by_date_range(posts, start_date, end_date)

                for post in posts:
                    if self._should_filter_post(post.get("title", ""), post.get("text", "")):
                        continue
                    if len(collected) >= max_results:
                        break
                    collected.append(post)
            except Exception as exc:
                print(f"Error fetching RSS for r/{sub}: {exc}")
                continue

        return collected[:max_results]

    def _parse_timestamp_with_timezone(self, timestamp_str):
        try:
            dt = parser.isoparse(timestamp_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=tz.UTC)
            tzname = dt.tzname() or "UTC"
            return dt.isoformat(), tzname
        except Exception:
            now = datetime.now(tz.UTC)
            return now.isoformat(), "UTC"

    def _parse_feed(self, content, subreddit):
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        try:
            root = ET.fromstring(content)
        except ET.ParseError:
            return []

        entries = root.findall(".//atom:entry", ns)
        results = []
        for entry in entries:
            title_el = entry.find("atom:title", ns)
            summary_el = entry.find("atom:summary", ns)
            updated_el = entry.find("atom:updated", ns)
            published_el = entry.find("atom:published", ns)
            link_el = entry.find("atom:link", ns)
            author_el = entry.find("atom:author/atom:name", ns)
            id_el = entry.find("atom:id", ns)

            title = html.unescape(title_el.text) if title_el is not None and title_el.text else ""
            summary_raw = summary_el.text or "" if summary_el is not None else ""
            summary = html.unescape(summary_raw)

            text_parts = []
            if title.strip():
                text_parts.append(title.strip())
            if summary.strip():
                text_parts.append(summary.strip())
            text = "\n\n".join(text_parts) if text_parts else "(no content)"

            created_str = (updated_el.text if updated_el is not None else None) or (
                published_el.text if published_el is not None else None
            )

            if created_str:
                created_at, timezone = self._parse_timestamp_with_timezone(created_str)
            else:
                now = datetime.now(tz.UTC)
                created_at = now.isoformat()
                timezone = "UTC"

            url = link_el.attrib.get("href") if link_el is not None else ""
            author = author_el.text if author_el is not None else "unknown"
            raw_id = id_el.text if id_el is not None else url

            reddit_id = None
            if raw_id:
                parts = raw_id.split("/")
                for part in reversed(parts):
                    if part and part not in ["comments", "r", subreddit]:
                        reddit_id = part
                        break
            if not reddit_id:
                reddit_id = f"post_{len(results)}"

            post_id = f"reddit_{reddit_id}"

            results.append(
                {
                    "id": post_id,
                    "reddit_id": reddit_id,
                    "url": url,
                    "subreddit": subreddit,
                    "title": title,
                    "text": text,
                    "author": author,
                    "author_id": author,
                    "created_at": created_at,
                    "timezone": timezone,
                    "link": url,
                    "metrics": {},
                }
            )
        return results
