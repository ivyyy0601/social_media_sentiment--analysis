"""
Export service for converting data to various formats (CSV, JSON).
"""

import csv
import json
from io import StringIO
from typing import List, Dict, Any
from datetime import datetime


class ExportService:
    """Handle data export to CSV and JSON formats"""

    @staticmethod
    def _extract_sentiment_fields(post: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make export resilient to different response shapes.

        Supported shapes:
        1) Flat:
            sentiment_label, sentiment_score, sentiment_signed_score
        2) Nested:
            sentiment: { label, score, signed_score }
        3) Alternate flat keys:
            label, score, signed_score
        """
        label = (
            post.get("sentiment_label")
            or post.get("label")
            or (post.get("sentiment") or {}).get("label")
            or ""
        )

        score = (
            post.get("sentiment_score")
            or post.get("score")
            or (post.get("sentiment") or {}).get("score")
            or ""
        )

        signed_score = (
            post.get("sentiment_signed_score")
            or post.get("signed_score")
            or (post.get("sentiment") or {}).get("signed_score")
            or (post.get("sentiment") or {}).get("signedScore")  # 防前端驼峰
            or ""
        )

        return {
            "sentiment_label": label,
            "sentiment_score": score,
            "sentiment_signed_score": signed_score,
        }

    @staticmethod
    def _tickers_to_string(post: Dict[str, Any]) -> str:
        """
        Convert tickers to a stable CSV string.
        - list -> "AAPL,TSLA"
        - str  -> as-is
        - None/missing -> ""
        """
        tickers_val = post.get("tickers", [])

        if tickers_val is None:
            return ""

        if isinstance(tickers_val, str):
            return tickers_val.strip()

        if isinstance(tickers_val, list):
            # list 里面可能是字符串，也可能是 dict（比如 {"symbol":"AAPL"}），都兼容
            out = []
            for x in tickers_val:
                if isinstance(x, str):
                    out.append(x.strip())
                elif isinstance(x, dict):
                    out.append(str(x.get("symbol") or x.get("ticker") or x.get("id") or "").strip())
            out = [t for t in out if t]
            return ",".join(out)

        # 其他类型兜底
        return str(tickers_val)

    @staticmethod
    def export_posts_to_csv(posts: List[Dict]) -> str:
        """
        Export posts to CSV format

        Args:
            posts: List of post dictionaries

        Returns:
            CSV string
        """
        if not posts:
            return ""

        output = StringIO()

        # ✅ 加上 sentiment_signed_score，否则你永远导不出 -0.09 那列
        headers = [
            "id",
            "reddit_id",
            "title",
            "text",
            "author",
            "subreddit",
            "url",
            "created_at",
            "timezone",
            "sentiment_label",
            "sentiment_score",
            "sentiment_signed_score",
            
        ]

        writer = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()

        for post in posts:
            sent = ExportService._extract_sentiment_fields(post)
            tickers_str = ExportService._tickers_to_string(post)

            row = {
                "id": post.get("id", ""),
                "reddit_id": post.get("reddit_id", ""),
                "title": post.get("title", ""),
                "text": (post.get("text", "") or "").replace("\n", " ").replace("\r", " "),
                "author": post.get("author", ""),
                "subreddit": post.get("subreddit", ""),
                "url": post.get("url", ""),
                "created_at": post.get("created_at", ""),
                "timezone": post.get("timezone", ""),
                "sentiment_label": sent["sentiment_label"],
                "sentiment_score": sent["sentiment_score"],
                "sentiment_signed_score": sent["sentiment_signed_score"],
                "tickers": tickers_str,
            }

            writer.writerow(row)

        return output.getvalue()

    @staticmethod
    def export_posts_to_json(posts: List[Dict]) -> str:
        """
        Export posts to JSON format

        Args:
            posts: List of post dictionaries

        Returns:
            JSON string
        """
        # 也顺便保证 JSON 里 sentiment/tickers 是一致的
        normalized_posts = []
        for post in posts or []:
            sent = ExportService._extract_sentiment_fields(post)
            tickers_str = ExportService._tickers_to_string(post)
            p = dict(post)
            # 统一字段输出
            p["sentiment_label"] = sent["sentiment_label"]
            p["sentiment_score"] = sent["sentiment_score"]
            p["sentiment_signed_score"] = sent["sentiment_signed_score"]
            p["tickers"] = tickers_str.split(",") if tickers_str else []
            normalized_posts.append(p)

        return json.dumps(
            {
                "posts": normalized_posts,
                "count": len(normalized_posts),
                "exported_at": datetime.utcnow().isoformat(),
            },
            indent=2,
            ensure_ascii=False,
        )

    @staticmethod
    def export_sentiment_trends_to_csv(trends: List[Dict]) -> str:
        """
        Export sentiment trends to CSV

        Args:
            trends: List of trend dictionaries

        Returns:
            CSV string
        """
        if not trends:
            return ""

        output = StringIO()

        headers = ["date", "positive", "negative", "neutral", "total"]
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()

        for trend in trends:
            total = trend.get("positive", 0) + trend.get("negative", 0) + trend.get("neutral", 0)
            row = {
                "date": trend.get("date", ""),
                "positive": trend.get("positive", 0),
                "negative": trend.get("negative", 0),
                "neutral": trend.get("neutral", 0),
                "total": total,
            }
            writer.writerow(row)

        return output.getvalue()

    @staticmethod
    def export_sentiment_trends_to_json(trends: List[Dict]) -> str:
        """
        Export sentiment trends to JSON format

        Args:
            trends: List of trend dictionaries

        Returns:
            JSON string
        """
        return json.dumps(
            {
                "trends": trends,
                "count": len(trends),
                "exported_at": datetime.utcnow().isoformat(),
            },
            indent=2,
            ensure_ascii=False,
        )

    @staticmethod
    def export_stats_to_json(stats: Dict) -> str:
        """
        Export statistics to JSON format

        Args:
            stats: Statistics dictionary

        Returns:
            JSON string
        """
        return json.dumps(
            {
                "stats": stats,
                "exported_at": datetime.utcnow().isoformat(),
            },
            indent=2,
            ensure_ascii=False,
        )
