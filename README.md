# 📈 Finance Sentiment Analysis Dashboard

A full-stack financial sentiment analytics platform that collects posts from **67+ Reddit communities** and **8 financial news sources**, analyzes them with **FinBERT**, and surfaces real-time market sentiment insights through an interactive dashboard — with **Gemini AI** analysis and automatic data collection running every 30 minutes.

---

## ✨ Core Features

### 📡 Multi-Source Data Collection
Automatically fetches and analyzes content from:

| Source | Type | Volume |
|--------|------|--------|
| Reddit RSS (67 subreddits) | Social media | 100 posts/ticker |
| Yahoo Finance News | Financial news | 30 posts/ticker |
| Google News | General news | 40 posts/ticker |
| Nasdaq News | Financial news | 20 posts/ticker |
| Seeking Alpha | Investment analysis | 20 posts/ticker |
| CNBC News | Financial news | 20 posts/ticker |
| SEC EDGAR (8-K filings) | Official filings | 10 posts/ticker |
| Motley Fool | Investment analysis | 15 posts/ticker |
| Hacker News | Tech news | 20 posts/ticker |

**No API keys required** for most sources — uses public RSS and web feeds.

Reddit coverage includes 67 communities, from `r/wallstreetbets` and `r/stocks` to `r/algotrading`, `r/thetagang`, `r/SwingTrading`, and ticker-specific subreddits (e.g. `r/NVDA_Stock`, `r/teslainvestorsclub`).

### 🤖 FinBERT Sentiment Analysis
- Uses `ProsusAI/finbert` — a BERT model fine-tuned on financial text
- Classifies each post as **Positive**, **Neutral**, or **Negative**
- Computes `signed_score = P(positive) - P(negative)` ∈ [-1, 1] as the canonical sentiment score
- **Skip-if-exists optimization**: already-analyzed posts are skipped on re-fetch — no redundant FinBERT inference

### 🕐 Automatic Scheduling
- **Fetches new data every 30 minutes** via APScheduler background job
- **Cleans up posts older than 30 days** daily at 2:00 AM
- Cleanup also runs on every fetch cycle and on server startup
- All time windows use UTC-aligned calendar-day cutoffs

### 📊 Sentiment Leaderboard (`Leaderboard` tab)
- Ranks tracked tickers by sentiment score
- Configurable time window: **1天 / 2天 / 3天 / 7天 / 30天**
- Click any ticker to open the detailed analysis panel
- Fetch buttons for manual refresh per-ticker or all at once

### 🔍 Ticker Analysis Panel
Deep-dive panel for each stock, with period selector (1/2/3/7/30 days):
- Sentiment score breakdown (Positive / Neutral / Negative %)
- FinBERT `signed_score` trend chart
- Price chart via yfinance — period change % aligned to the same calendar window as sentiment
- 52-week range bar, Market Cap, P/E ratio
- Recent posts with source filter and date range filter
- 🤖 AI analysis powered by Gemini 2.5 Flash with follow-up chat

### 🤖 AI Analyst (`AI Analyst` tab)
- Manual period analysis: click **1天 / 2天 / 3天 / 7天 / 30天** to generate a full DB-backed report
- Report covers: sentiment trends, top tickers, source breakdown, sample posts
- Follow-up chat section for custom questions — maintains conversation history
- Powered by **Gemini 2.5 Flash** with direct API call + history passing

### 🔬 Sentiment Lab (`Sentiment Lab` tab)
Experimental analysis tools:
- **Method Comparison**: label-count method vs. avg_signed_score vs. weighted score
- **Backtest**: correlate historical sentiment scores with next-day price changes (Pearson correlation)
- **Distribution**: sentiment score distribution across all posts

### 💹 Market Data via yfinance
- Real-time current price and intraday change
- Historical OHLCV data with period-aligned change calculation:
  - `start_close` = last available close on or before `now - N calendar days` (matches sentiment window exactly)
  - `current_price` = real-time price from yfinance `.info`
- Period high/low using actual `High`/`Low` columns
- 52-week range and position

---

## 🏗️ Architecture

```
Reddit RSS (67 subs)  ─┐
Yahoo Finance News    ─┤
Google News           ─┤
Nasdaq / CNBC         ─┼─→  Content Filter  →  FinBERT Analysis  →  SQLite DB
Seeking Alpha         ─┤         ↑                    ↑
SEC EDGAR 8-K         ─┤    Skip if exists       signed_score
Motley Fool / HN      ─┘    (no re-analysis)
                                                        ↓
                                              Flask REST API (v1)
                                                        ↓
                                           React Dashboard (Vite)
                                    ┌──────────────────────────────┐
                                    │  Leaderboard  │  AI Analyst  │
                                    │  Ticker Panel │  Sentiment   │
                                    │  Overview     │  Lab         │
                                    └──────────────────────────────┘
```

### Backend Stack
- **Flask** 3.x + Flask-CORS
- **APScheduler** — background fetch (30 min interval) + daily cleanup
- **FinBERT** via HuggingFace Transformers + PyTorch
- **SQLite** with schema migrations (v1–v5)
- **yfinance** — real-time and historical price data
- **Gemini 2.5 Flash** — AI analysis via REST API

### Frontend Stack
- **React** + **Vite**
- **Chart.js** + `react-chartjs-2`
- **Axios** for API calls

---

## 🚀 Getting Started

### Prerequisites
- Python 3.8+
- Node.js 16+
- ~2 GB disk space (for FinBERT model)
- Gemini API key (for AI analysis features)

### 1. Backend Setup

```bash
cd backend
pip install -r requirements.txt
python migrations.py   # initializes the DB schema
python app.py          # starts on http://localhost:5000
```

On first run, FinBERT (~440 MB) downloads automatically from HuggingFace.

### 2. Environment Variables

Create `backend/.env`:

```env
GEMINI_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here        # optional
WHATSAPP_PHONE=your_phone                  # optional, for daily digest
WHATSAPP_APIKEY=your_callmebot_key         # optional
```

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev   # starts on http://localhost:5173
```

---

## ⚙️ Configuration (`backend/config.json`)

Key settings:

```json
{
  "auto_fetch": {
    "interval_hours": 0.5,
    "tickers": ["NVDA", "AAPL", "MSFT", "GOOG", "AMZN", "META", "TSLA", "AVGO", "TXN", "COHR", "INTC", "ASML", "SNDK"]
  },
  "reddit": {
    "subreddits": ["stocks", "wallstreetbets", "investing", ...],
    "ticker_subreddits": {
      "NVDA": ["nvidia", "NVDA_Stock", "NVIDIAStock"],
      "TSLA": ["teslamotors", "teslainvestorsclub", "TSLA_Stock"]
    }
  },
  "sentiment": {
    "model": "ProsusAI/finbert",
    "confidence_threshold": 0.6
  },
  "gemini": {
    "model": "gemini-2.5-flash"
  }
}
```

---

## 📁 Project Structure

```
├── backend/
│   ├── app.py                    # Flask app, routes, scheduler
│   ├── database.py               # SQLite repositories
│   ├── migrations.py             # Schema migrations (v1–v5)
│   ├── sentiment_analyzer.py     # FinBERT wrapper
│   ├── ticker_extractor.py       # Ticker mention extraction
│   ├── red_client.py             # Reddit RSS client
│   ├── yahoo_finance_news_client.py
│   ├── google_news_client.py
│   ├── nasdaq_news_client.py
│   ├── seeking_alpha_client.py
│   ├── cnbc_news_client.py
│   ├── sec_edgar_client.py
│   ├── motley_fool_client.py
│   ├── hackernews_client.py
│   ├── price_data_provider.py    # yfinance integration
│   ├── agent_service.py          # Gemini AI service
│   ├── config.json
│   └── requirements.txt
│
├── frontend/
│   └── src/
│       ├── App.jsx
│       └── components/
│           ├── TickerBoard.jsx           # Leaderboard
│           ├── TickerAnalysisPanel.jsx   # Per-stock deep dive
│           ├── AIAnalyst.jsx             # AI period analysis + chat
│           ├── SentimentLab.jsx          # Backtest & method comparison
│           ├── TickerBoardGemini.jsx     # Gemini-scored leaderboard
│           ├── TickerBoardAI.jsx         # DB ai_score leaderboard
│           └── ...
│
├── .gitignore
└── README.md
```

---

## 🗄️ Database Schema

| Table | Purpose |
|-------|---------|
| `posts` | Post content, FinBERT scores (`sentiment_signed_score`), source, timestamps |
| `tickers` | Symbol, company name, sector, industry |
| `post_tickers` | Many-to-many: posts ↔ tickers |
| `post_industries` | Many-to-many: posts ↔ industries |
| `post_sectors` | Many-to-many: posts ↔ sectors |
| `watchlists` | User watchlists |
| `watchlist_tickers` | Tickers in each watchlist |

Posts older than **30 days** are automatically deleted daily.

---

## 📊 Sentiment Score

The canonical sentiment metric is:

```
signed_score = P(positive) - P(negative)   ∈ [-1, 1]
```

Aggregated per ticker/period as `avg_signed_score` (weighted by post count per day).

Thresholds:
- `score > 0.1` → **Bullish**
- `score < -0.1` → **Bearish**
- otherwise → **Neutral**

---

## ⚠️ Limitations

- Reddit RSS returns only the latest ~25 posts per subreddit — frequent polling needed to avoid missing posts
- `yfinance` is unofficial and may change without notice
- SQLite is suitable for local/personal use; larger deployments should consider PostgreSQL
- Gemini API calls require an active API key and are rate-limited

---

## 🛠️ Troubleshooting

**FinBERT won't download**
```bash
python -c "from transformers import pipeline; pipeline('text-classification', model='ProsusAI/finbert')"
```

**No posts appearing**
- Check Reddit RSS availability (may be temporarily rate-limited)
- Verify subreddit names in `config.json`
- Check backend logs for per-source error messages

**AI analysis not working**
- Confirm `GEMINI_API_KEY` is set in `backend/.env`
- Check backend logs for Gemini API errors
