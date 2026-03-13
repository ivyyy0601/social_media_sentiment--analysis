"""
AI Analyst Agent powered by Google Gemini 2.0 Flash (free tier).
"""

import json
import requests


GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

SYSTEM_PROMPT = """You are a professional financial AI analyst assistant embedded in a stock sentiment dashboard.
You have access to real-time social media sentiment data (Reddit, StockTwits, news) and live stock price data.
Always be concise, data-driven, and structured. Never make explicit buy/sell recommendations.
End every response with: ⚠️ This is based on social media sentiment & public market data — not financial advice."""

MARKET_OVERVIEW_PROMPT = """You are a senior financial analyst. Provide a comprehensive market overview combining retail sentiment and official perspectives.

Based on the data below (sourced from Reddit communities like WSB/r/stocks/r/options, Hacker News, Yahoo Finance, CNBC, Seeking Alpha, Nasdaq News, SEC filings, and Motley Fool):

**1. Overall Market Mood**
Summarize the broad sentiment (bullish / bearish / mixed) with percentages and post volumes.

**2. 🗣️ What Retail Investors Are Saying**
What themes dominate Reddit and social discussions right now? Any viral narratives, sector rotations, or meme plays? What's the crowd excited or worried about?

**3. 📰 What Official Sources Are Reporting**
Key macro news, earnings beats/misses, analyst upgrades/downgrades, Fed/macro events influencing the market.

**4. 🏆 Most Discussed Stocks**
Which stocks are getting the most attention? Why — earnings, news, controversy, momentum?

**5. 📊 Sentiment vs. Price**
For the top movers, does sentiment align with recent price action?

**6. 🔮 Market Outlook (3–5 sentences)**
Your view on near-term market direction based on the combined retail + official picture.

Market Data:
{data}"""

STOCK_ANALYSIS_PROMPT = """You are a senior financial analyst. Provide a thorough, multi-dimensional analysis combining both official sources and retail/social sentiment.

Analyze {ticker} over the last {days} days using the data below, which includes Reddit communities (WSB, r/stocks, r/options, r/NVDA_Stock, etc.), Hacker News discussions, news articles (Yahoo Finance, CNBC, Nasdaq, Seeking Alpha, Motley Fool), and official SEC filings.

Write a detailed report with these sections:

**1. Overall Sentiment — Big Picture**
Is the overall market sentiment bullish, bearish, or mixed? Give the sentiment score and post volume. Note confidence level.

**2. 🗣️ Retail & Social Media Sentiment (Reddit / Hacker News)**
What is the crowd saying? Summarize the dominant narratives from Reddit communities and social platforms:
- What are WSB / options traders saying? (momentum plays, YOLO trades, catalysts)
- What are long-term investors in r/stocks / r/investing saying? (fundamentals, valuation)
- Are there any viral posts, memes, or high-engagement discussions?
- Overall retail mood: euphoric / optimistic / cautious / fearful / bearish?

**3. 📰 Official & Institutional Perspective (News / SEC / Analysts)**
What do official sources say?
- Key news headlines from CNBC, Yahoo Finance, Nasdaq, Seeking Alpha
- Any SEC 8-K filings (earnings, material events, leadership changes)?
- Analyst coverage or price target changes mentioned?
- Macro factors affecting this stock?

**4. 🔀 Divergence Analysis — Retail vs. Official**
Do retail investors and official sources agree or disagree?
- If retail is bullish but news is bearish (or vice versa), explain why this divergence matters
- Historical context: does retail sentiment lead or lag official news for this stock?

**5. 📈 Price vs. Sentiment**
Compare price movement with sentiment over {days} days. Aligned or diverging? Use specific numbers.

**6. 💡 Analyst Opinion & Outlook**
Your substantive view: what does the combined picture suggest about near-term direction? What are the key risks and catalysts to watch?

Data:
{data}

End with:
📊 Decision Brief: {ticker} (Last {days} days)
• Sentiment Signal   : [Bullish 📈 / Bearish 📉 / Neutral ➡️] (score: X.XX, X posts)
• Retail Mood        : [Euphoric / Optimistic / Cautious / Fearful / Bearish]
• Official Tone      : [Positive / Neutral / Negative] — one key headline
• Price Today        : $X.XX ([+/-]X.X%) | {days}-day trend: [up/down/flat] ([+/-]X.X%)
• 52-week Position   : Low $X — High $X (currently at X% of range)
• Retail vs Official : [Aligned ✅ / Diverging ⚠️] — one-line reason
• Key Insight        : 2–3 sentences with your most important finding
⚠️ Based on social media sentiment & public market data — not financial advice."""


class AgentService:
    def __init__(self, db, price_data_provider, api_key, model="gemini-2.5-flash", stock_data_provider=None):
        self.db = db
        self.price_data_provider = price_data_provider
        self.stock_data_provider = stock_data_provider
        self.api_key = api_key
        self.model = model

    # ── Public methods ────────────────────────────────────────────────────────

    def chat(self, user_message, history=None):
        """Process a user message and return AI response."""
        if history is None:
            history = []

        context = self._build_context(user_message)
        prompt = self._build_prompt(user_message, context, history)
        response_text = self._call_gemini(prompt)

        updated_history = history + [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": response_text}
        ]
        return response_text, updated_history

    def get_brief(self):
        """Generate an automatic market overview brief."""
        context = self._get_market_overview(days=7)
        indices = self._get_market_indices()
        context["market_indices"] = indices

        prompt = MARKET_OVERVIEW_PROMPT.format(
            data=json.dumps(context, default=str, indent=2)
        )
        return self._call_gemini(prompt)

    def get_stock_analysis(self, ticker, days=7):
        """Generate a full analysis for a specific stock."""
        ticker = ticker.upper().strip()
        sentiment = self._get_stock_sentiment(ticker, days=days)
        price = self._get_full_price_data(ticker, days=days)
        posts = self._search_posts(ticker, limit=10)

        data = {
            "sentiment": sentiment,
            "price_and_fundamentals": price,
            "recent_posts_sample": posts,
        }

        prompt = STOCK_ANALYSIS_PROMPT.format(
            ticker=ticker,
            days=days,
            data=json.dumps(data, default=str, indent=2)
        )
        return self._call_gemini(prompt)

    # ── Context building ──────────────────────────────────────────────────────

    def _build_context(self, message):
        msg_upper = message.upper()
        ticker = self._extract_ticker(msg_upper)

        if ticker:
            return {
                "query_type": "stock_analysis",
                "ticker": ticker,
                "sentiment": self._get_stock_sentiment(ticker, days=7),
                "price_and_fundamentals": self._get_full_price_data(ticker),
                "recent_posts": self._search_posts(ticker, limit=10),
            }
        else:
            return {
                "query_type": "market_overview",
                "market_data": self._get_market_overview(days=7),
                "market_indices": self._get_market_indices(),
            }

    def _build_prompt(self, user_message, context, history):
        parts = [SYSTEM_PROMPT, "\n\n"]

        if history:
            parts.append("Previous conversation:\n")
            for msg in history[-6:]:
                role = "User" if msg["role"] == "user" else "Assistant"
                parts.append(f"{role}: {msg['content']}\n")
            parts.append("\n")

        query_type = context.get("query_type", "")
        if query_type == "stock_analysis":
            ticker = context.get("ticker", "")
            days_ctx = context.get("sentiment", {}).get("period_days", 7)
            parts.append(STOCK_ANALYSIS_PROMPT.format(
                ticker=ticker,
                days=days_ctx,
                data=json.dumps(context, default=str, indent=2)
            ))
        else:
            parts.append(MARKET_OVERVIEW_PROMPT.format(
                data=json.dumps(context, default=str, indent=2)
            ))

        parts.append(f"\n\nUser question: {user_message}\n\nAssistant:")
        return "".join(parts)

    def _extract_ticker(self, text):
        import os
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

    def _call_gemini(self, prompt):
        """Call Gemini 2.0 Flash API."""
        import time
        url = f"{GEMINI_URL}?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 3000,
            }
        }
        for attempt in range(4):
            try:
                resp = requests.post(url, json=payload, timeout=60)
                if resp.status_code == 429:
                    wait = [5, 15, 30, 60][attempt]
                    print(f"[Gemini] Rate limited, waiting {wait}s (attempt {attempt+1})")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                candidates = resp.json().get("candidates", [])
                if candidates:
                    return candidates[0]["content"]["parts"][0]["text"]
                return "❌ No response from Gemini."
            except requests.exceptions.Timeout:
                return "⏱️ Request timed out. Please try again."
            except Exception as e:
                if attempt == 3:
                    return f"❌ AI service error: {str(e)}"
                time.sleep(2)
        return "⏱️ Rate limit reached. Please wait 1 minute and try again."

    # ── Data fetchers ─────────────────────────────────────────────────────────

    def _get_market_overview(self, days=7):
        try:
            pulse = self.db.analytics.get_market_pulse()
            trends = self.db.analytics.get_sentiment_trends(days=days)

            total_pos = sum(t.get("positive", 0) for t in trends)
            total_neg = sum(t.get("negative", 0) for t in trends)
            total_neu = sum(t.get("neutral", 0) for t in trends)
            total = total_pos + total_neg + total_neu

            return {
                "period_days": days,
                "total_posts_analyzed": total,
                "sentiment_breakdown": {
                    "positive_pct": round(total_pos / total * 100, 1) if total > 0 else 0,
                    "negative_pct": round(total_neg / total * 100, 1) if total > 0 else 0,
                    "neutral_pct": round(total_neu / total * 100, 1) if total > 0 else 0,
                },
                "most_discussed": pulse.get("most_discussed_stocks", [])[:5],
                "most_bullish": pulse.get("most_positive_stocks", [])[:3],
                "most_bearish": pulse.get("most_negative_stocks", [])[:3],
                "overall_market_sentiment": pulse.get("overall_market_sentiment", {}),
            }
        except Exception as e:
            return {"error": str(e)}

    def _get_stock_sentiment(self, ticker, days=7):
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
                "period_days": days,
                "total_posts": total,
                "positive": total_pos,
                "negative": total_neg,
                "neutral": total_neu,
                "sentiment_score": score,
                "sentiment_label": label,
                "daily_trend": trends,
            }
        except Exception as e:
            return {"error": str(e)}

    def _get_full_price_data(self, ticker, days=7):
        from datetime import datetime, timedelta
        ticker = ticker.upper().strip()
        result = {}

        try:
            current = self.price_data_provider.get_current_price(ticker)
            if current:
                result["current_price"] = current.get("price")
                result["change_today_pct"] = round(current.get("change_percent") or 0, 2)
                result["market_state"] = current.get("market_state")
        except Exception as e:
            result["price_error"] = str(e)

        try:
            end = datetime.now().strftime("%Y-%m-%d")
            start = (datetime.now() - timedelta(days=days + 5)).strftime("%Y-%m-%d")
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

        try:
            import yfinance as yf
            info = yf.Ticker(ticker).info
            result["company_name"] = info.get("longName") or info.get("shortName", ticker)
            result["sector"] = info.get("sector")
            result["market_cap"] = info.get("marketCap")
            result["pe_ratio"] = info.get("trailingPE")
            result["52w_high"] = info.get("fiftyTwoWeekHigh")
            result["52w_low"] = info.get("fiftyTwoWeekLow")
            hi = result.get("52w_high")
            lo = result.get("52w_low")
            price = result.get("current_price")
            if hi and lo and price and (hi - lo) > 0:
                result["52w_position_pct"] = round((price - lo) / (hi - lo) * 100, 1)
        except Exception as e:
            result["fundamentals_error"] = str(e)

        return result

    def _get_market_indices(self):
        try:
            return self.price_data_provider.get_market_indices()
        except Exception as e:
            return {"error": str(e)}

    def _search_posts(self, ticker=None, limit=10):
        try:
            posts = self.db.posts.get_posts_filtered(ticker=ticker, limit=limit)
            return [
                {
                    "title": p.get("title", "")[:120],
                    "sentiment": p.get("sentiment_label"),
                    "source": p.get("subreddit"),
                    "date": str(p.get("created_at", ""))[:10],
                }
                for p in posts
            ]
        except Exception as e:
            return {"error": str(e)}
