"""
AI Analyst Agent powered by Google Gemini REST API.
Uses requests directly — no SDK dependency.
"""

import json
import requests


GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = """You are an AI financial sentiment analyst assistant built into a stock sentiment dashboard.
You analyze Reddit/news sentiment data AND real stock price data to help users make informed decisions.

When given data, provide clear, concise analysis. For specific stock analysis, always end with:

📊 Decision Brief: [TICKER] - [Company Name]
• Sentiment Signal : [Bullish 📈 / Bearish 📉 / Neutral ➡️] (score: X.XX, X posts)
• Price Today      : $X.XX ([+/-]X.X%) | 7-day trend: [up/down/flat]
• vs 52-week range : Low $X — High $X (currently at X% of range)
• Market Cap       : $XB
• Sentiment/Price  : [Aligned ✅ / Diverging ⚠️ — brief note]
• Key Insight      : [1-2 sentences combining sentiment + price + trend]
⚠️ Based on social media sentiment & public market data — not financial advice.

Be concise and data-driven. Comment on whether price trend matches sentiment. If no data, say so clearly."""


class AgentService:
    def __init__(self, db, price_data_provider, api_key, model="llama-3.3-70b-versatile", stock_data_provider=None):
        self.db = db
        self.price_data_provider = price_data_provider
        self.stock_data_provider = stock_data_provider
        self.api_key = api_key
        self.model = model

    # ── Public methods ────────────────────────────────────────────────────────

    def chat(self, user_message, history=None):
        """
        Process a user message, fetch relevant data, and return AI response.
        Returns: (response_text, updated_history)
        """
        if history is None:
            history = []

        # Decide what data to fetch based on the message
        context = self._build_context(user_message)

        # Build the full prompt
        prompt = self._build_prompt(user_message, context, history)

        # Call Gemini
        response_text = self._call_groq(prompt)

        updated_history = history + [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": response_text}
        ]
        return response_text, updated_history

    def get_brief(self):
        """Generate an automatic market brief."""
        context = self._get_market_overview(days=30)
        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"Here is the latest market sentiment data:\n{json.dumps(context, default=str, indent=2)}\n\n"
            f"Give a concise market brief (under 150 words). Highlight the most interesting trends, "
            f"top movers, and overall market mood."
        )
        return self._call_groq(prompt)

    # ── Context building ──────────────────────────────────────────────────────

    def _build_context(self, message):
        """Fetch relevant data based on what the user is asking about."""
        msg_upper = message.upper()

        # Check if message mentions a specific ticker
        ticker = self._extract_ticker(msg_upper)

        if ticker:
            sentiment = self._get_stock_sentiment(ticker, days=30)
            price = self._get_full_price_data(ticker)
            posts = self._search_posts(ticker, limit=3)
            return {
                "query_type": "stock_analysis",
                "ticker": ticker,
                "sentiment": sentiment,
                "price_and_fundamentals": price,
                "recent_posts": posts,
            }
        else:
            return {
                "query_type": "market_overview",
                "market_data": self._get_market_overview(days=30),
                "market_indices": self._get_market_indices(),
            }

    def _build_prompt(self, user_message, context, history):
        """Build the full prompt with history and context."""
        parts = [SYSTEM_PROMPT, "\n\n"]

        # Add conversation history
        if history:
            parts.append("Previous conversation:\n")
            for msg in history[-6:]:  # last 3 turns
                role = "User" if msg["role"] == "user" else "Assistant"
                parts.append(f"{role}: {msg['content']}\n")
            parts.append("\n")

        # Add fetched data
        parts.append(f"Relevant data fetched for this query:\n{json.dumps(context, default=str, indent=2)}\n\n")
        parts.append(f"User: {user_message}\n\nAssistant:")

        return "".join(parts)

    def _extract_ticker(self, text):
        """Check if the message contains a known ticker symbol."""
        import os
        # Load known tickers
        try:
            tickers_path = os.path.join(os.path.dirname(__file__), 'known_tickers.json')
            with open(tickers_path) as f:
                known = set(json.load(f))
        except Exception:
            known = set()

        words = text.split()
        for word in words:
            clean = ''.join(c for c in word if c.isalpha())
            if clean in known:
                return clean
        return None

    # ── Gemini API call ───────────────────────────────────────────────────────

    def _call_groq(self, prompt):
        """Call Groq API (OpenAI-compatible) with retry on rate limit."""
        import time
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 1024,
            "temperature": 0.7,
        }
        for attempt in range(3):
            try:
                resp = requests.post(GROQ_URL, json=payload, headers=headers, timeout=30)
                if resp.status_code == 429:
                    time.sleep(2 ** attempt)
                    continue
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
            except requests.exceptions.Timeout:
                return "⏱️ Request timed out. Please try again."
            except Exception as e:
                if attempt == 2:
                    return f"❌ AI service error: {str(e)}"
                time.sleep(1)
        return "⏱️ AI is busy right now. Please wait a moment and try again."

    # ── Data fetchers ─────────────────────────────────────────────────────────

    def _get_market_overview(self, days=30):
        try:
            pulse = self.db.analytics.get_market_pulse()
            trends = self.db.analytics.get_sentiment_trends(days=days)

            total_pos = sum(t.get("positive", 0) for t in trends)
            total_neg = sum(t.get("negative", 0) for t in trends)
            total_neu = sum(t.get("neutral", 0) for t in trends)
            total = total_pos + total_neg + total_neu

            return {
                "period_days": days,
                "total_posts": total,
                "positive_pct": round(total_pos / total * 100, 1) if total > 0 else 0,
                "negative_pct": round(total_neg / total * 100, 1) if total > 0 else 0,
                "neutral_pct": round(total_neu / total * 100, 1) if total > 0 else 0,
                "most_discussed": pulse.get("most_discussed_stocks", [])[:5],
                "most_positive": pulse.get("most_positive_stocks", [])[:3],
                "most_negative": pulse.get("most_negative_stocks", [])[:3],
                "overall": pulse.get("overall_market_sentiment", {}),
            }
        except Exception as e:
            return {"error": str(e)}

    def _get_stock_sentiment(self, ticker, days=30):
        try:
            trends = self.db.analytics.get_sentiment_trends(days=days, ticker=ticker)
            total_pos = sum(t.get("positive", 0) for t in trends)
            total_neg = sum(t.get("negative", 0) for t in trends)
            total_neu = sum(t.get("neutral", 0) for t in trends)
            total = total_pos + total_neg + total_neu

            score = None
            label = "No data"
            if total > 0:
                score = round((total_pos - total_neg) / total, 3)
                label = "Bullish" if score > 0.1 else ("Bearish" if score < -0.1 else "Neutral")

            return {
                "ticker": ticker,
                "total_posts": total,
                "positive": total_pos,
                "negative": total_neg,
                "neutral": total_neu,
                "sentiment_score": score,
                "sentiment_label": label,
            }
        except Exception as e:
            return {"error": str(e)}

    def _get_full_price_data(self, ticker):
        """Fetch comprehensive price + fundamental data from yfinance."""
        from datetime import datetime, timedelta
        ticker = ticker.upper().strip()
        result = {}

        # Current price + daily change
        try:
            current = self.price_data_provider.get_current_price(ticker)
            if current:
                result["current_price"] = current.get("price")
                result["change_today_pct"] = round(current.get("change_percent") or 0, 2)
                result["market_state"] = current.get("market_state")
        except Exception as e:
            result["price_error"] = str(e)

        # 7-day price history → trend
        try:
            end = datetime.now().strftime("%Y-%m-%d")
            start = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
            history = self.price_data_provider.get_historical_prices(ticker, start, end)
            if history and len(history) >= 2:
                closes = [h["close"] for h in history]
                result["price_7d_history"] = [
                    {"date": h["date"], "close": round(h["close"], 2)} for h in history[-7:]
                ]
                result["price_7d_change_pct"] = round(
                    (closes[-1] - closes[0]) / closes[0] * 100, 2
                )
                result["price_trend"] = (
                    "uptrend" if closes[-1] > closes[0] else
                    "downtrend" if closes[-1] < closes[0] else "flat"
                )
        except Exception as e:
            result["history_error"] = str(e)

        # Fundamentals from yfinance
        try:
            import yfinance as yf
            info = yf.Ticker(ticker).info
            result["company_name"] = info.get("longName") or info.get("shortName", ticker)
            result["sector"] = info.get("sector")
            result["industry"] = info.get("industry")
            result["market_cap"] = info.get("marketCap")
            result["pe_ratio"] = info.get("trailingPE")
            result["52w_high"] = info.get("fiftyTwoWeekHigh")
            result["52w_low"] = info.get("fiftyTwoWeekLow")
            result["avg_volume"] = info.get("averageVolume")
            # Position within 52-week range
            hi = result.get("52w_high")
            lo = result.get("52w_low")
            price = result.get("current_price")
            if hi and lo and price and (hi - lo) > 0:
                result["52w_position_pct"] = round((price - lo) / (hi - lo) * 100, 1)
        except Exception as e:
            result["fundamentals_error"] = str(e)

        return result

    def _get_market_indices(self):
        """Fetch S&P 500, Nasdaq, Dow Jones from yfinance."""
        try:
            return self.price_data_provider.get_market_indices()
        except Exception as e:
            return {"error": str(e)}

    def _search_posts(self, ticker=None, limit=5):
        try:
            posts = self.db.posts.get_posts_filtered(
                ticker=ticker,
                limit=limit
            )
            return [
                {
                    "title": p.get("title", "")[:100],
                    "sentiment": p.get("sentiment_label"),
                    "subreddit": p.get("subreddit"),
                    "date": str(p.get("created_at", ""))[:10],
                }
                for p in posts
            ]
        except Exception as e:
            return {"error": str(e)}
