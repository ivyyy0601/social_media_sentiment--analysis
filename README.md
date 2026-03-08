# 📈 Finance Sentiment Analysis Dashboard

A full-stack financial sentiment analytics platform that analyzes Reddit discussions with FinBERT to surface market sentiment insights across stocks, industries, and sectors. The system combines Reddit data ingestion, financial NLP, ticker intelligence, stock metadata and price integration, export tools, and watchlist management through a Flask + React architecture.

---

## ✨ Features

### 🤖 AI-Powered Sentiment Analysis
- **FinBERT-based sentiment classification** for financial text using `ProsusAI/finbert`
- Classifies posts into **Positive**, **Neutral**, and **Negative**
- Returns confidence scores for more interpretable sentiment outputs
- Better understanding of finance-specific language than general-purpose sentiment models

### 📡 Reddit Market Data Collection
- Fetches discussions from multiple finance-related subreddits
- Uses **Reddit RSS feeds**, so **no API keys are required**
- Supports configurable subreddit sources and search queries
- Automatically deduplicates and stores fetched posts
- Supports both **recent fetches** and **historical fetches by date range**

### 🧹 Data Quality Improvements
- Filters out irrelevant Reddit content such as:
  - daily discussion threads
  - generic advice posts
  - career/networking questions
- Configurable regex-based filter rules in `config.json`
- Reduces noise before sentiment analysis and aggregation

### 🎯 Ticker Intelligence
- Extracts stock tickers from Reddit posts using pattern matching and validation
- Supports formats like `$AAPL`, `AAPL`, and comma-separated ticker mentions
- Filters out common false positives such as `CEO`, `PR`, `DD`, etc.
- Enriches ticker mentions with company, sector, and industry metadata

### 📊 Market Analytics
- **Market Pulse** overview for aggregated sentiment insights
- **Most Discussed Stocks** by post volume
- **Most Positive / Most Negative Stocks** by sentiment score
- **Industry and Sector Analysis** with aggregated sentiment breakdowns
- **Sentiment Heatmaps** for quick market mood exploration
- **Volume-Sentiment Correlation** analysis over time
- **Sentiment Comparison** across selected tickers

### 💹 Stock Data Integration
- Real-time stock price lookup
- Historical OHLCV price data
- Major market index support:
  - S&P 500
  - Nasdaq
  - Dow Jones
- Dynamic stock metadata population through external sources
- Caching for better performance and lower repeated fetch overhead

### 📤 Export & Power User Features
- Export filtered posts to **CSV** or **JSON**
- Export sentiment trends for external analysis
- Persistent **watchlists** for custom ticker tracking
- Apply watchlists directly to dashboard filters

### 🎨 Modern Dashboard Experience
- React-based responsive frontend
- Flask REST API backend
- Interactive charts built with Chart.js
- Date-aware daily and weekly trend visualization
- Filtering by ticker, industry, sector, sentiment, and date range
- Loading, empty, and error states for smoother UX

---

## 🆕 What’s New in This Version

This version includes 8 major enhancements:

- Added filtering for non-market Reddit posts
- Increased default fetch capacity from 10 to 100
- Added historical Reddit fetch with `start_date` and `end_date`
- Improved time display in trend charts
- Added dynamic stock metadata support via external sources
- Added real-time and historical stock price endpoints
- Added export functionality for posts and sentiment trends
- Added persistent watchlist support

---

## 🏗️ Architecture

### Backend Stack
- **Framework**: Flask 3.x with CORS support
- **AI / ML**: HuggingFace Transformers + PyTorch
- **Database**: SQLite with schema migrations
- **External Data Sources**:
  - Reddit RSS
  - yfinance
- **Caching**:
  - persisted stock metadata cache
  - requests-cache for price data
- **API**: RESTful v1 API with standardized success/error responses

### Frontend Stack
- **Framework**: React
- **Build Tool**: Vite
- **Charts**: Chart.js + `react-chartjs-2`
- **HTTP Client**: Axios
- **Styling**: modern CSS with responsive layout

### Core Data Flow

```text
Reddit RSS / Historical Fetch
          ↓
Content Filtering
          ↓
FinBERT Sentiment Analysis
          ↓
Ticker Extraction + Metadata Enrichment
          ↓
SQLite Storage
          ↓
Flask REST API
          ↓
React Dashboard / Export / Watchlists
```

---

## 🚀 Getting Started

### Prerequisites
- **Python 3.8+**
- **Node.js 16+**
- `pip` and `npm`
- Around **2GB disk space** for model files and dependencies

---

## Backend Setup

1. Go to the backend folder:

```bash
cd backend
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run database migrations:

```bash
python migrations.py
```

4. Start the backend server:

```bash
python app.py
```

The backend will run on:

```text
http://localhost:5000
```

### First Run Note
On the first run, the FinBERT model will be downloaded automatically from HuggingFace. This may take several minutes depending on network speed.

---

## Frontend Setup

1. Go to the frontend folder:

```bash
cd frontend
```

2. Install dependencies:

```bash
npm install
```

3. Start the development server:

```bash
npm run dev
```

The frontend will usually run on:

```text
http://localhost:5173
```

---

## Verify Installation

1. Open `http://localhost:5173`
2. Use **Fetch New Posts** to ingest Reddit data
3. Wait for posts to be analyzed and stored
4. Explore charts, filters, exports, and watchlists

---

## 📖 Usage Guide

### Fetching Posts
You can fetch new Reddit posts directly from the dashboard.

Supported workflows:
- **Recent fetch** for latest posts
- **Historical fetch** using `start_date` and `end_date`
- configurable maximum fetch size

Each fetched post goes through:
1. filtering
2. sentiment analysis
3. ticker extraction
4. database storage

---

### Dashboard Views

#### Overview
- Market Pulse summary
- Key sentiment distribution
- Top discussed and top sentiment stocks

#### Analytics
- Sentiment trend charts
- Stock sentiment comparison
- Industry heatmap
- Volume vs sentiment analysis

#### Posts
- Paginated list of analyzed Reddit posts
- Sentiment labels and scores
- Extracted tickers
- Direct Reddit links

---

### Filters
The dashboard supports filtering by:
- **Ticker**
- **Industry**
- **Sector**
- **Sentiment**
- **Date range**

These filters are applied across analytics and post exploration views.

---

### Watchlists
Users can:
- create a watchlist
- rename a watchlist
- delete a watchlist
- add/remove tickers
- apply a watchlist to analysis filters

---

### Export
You can export:
- filtered posts
- sentiment trend data

Supported formats:
- **CSV**
- **JSON**

This is useful for reporting, offline analysis, or external tools such as Excel, Python notebooks, or BI dashboards.

---

## ⚙️ Configuration

### `backend/config.json`

Example:

```json
{
  "reddit": {
    "subreddits": ["stocks", "StockMarket", "investing", "wallstreetbets", "finance", "options"],
    "user_agent": "finance-sentiment-dashboard/2.0",
    "default_query": "stocks OR finance OR investing OR trading",
    "filter_patterns": {
      "exclude_titles": [
        "daily.*discussion",
        "general.*discussion",
        "advice.*thread"
      ],
      "exclude_keywords": [
        "career advice",
        "resume",
        "job interview"
      ]
    }
  },
  "sentiment": {
    "model": "ProsusAI/finbert",
    "confidence_threshold": 0.6
  },
  "api": {
    "version": "v1",
    "default_page_size": 50,
    "max_page_size": 1000
  },
  "server": {
    "port": 5000,
    "debug": false
  }
}
```

### Key Settings
- `subreddits`: RSS sources to fetch from
- `default_query`: default Reddit search query
- `filter_patterns`: rules for removing irrelevant posts
- `confidence_threshold`: minimum confidence threshold for sentiment
- `default_page_size`: API pagination size

---

## 📁 Project Structure

```text
sentiment-analysis-finance-posts/
├── backend/
│   ├── app.py
│   ├── api_utils.py
│   ├── database.py
│   ├── migrations.py
│   ├── sentiment_analyzer.py
│   ├── ticker_extractor.py
│   ├── industry_classifier.py
│   ├── reddit_rss_client.py
│   ├── stock_data_provider.py
│   ├── price_data_provider.py
│   ├── export_service.py
│   ├── watchlist_repository.py
│   ├── config.json
│   ├── ticker_mappings.json
│   ├── known_tickers.json
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Dashboard.jsx
│   │   │   ├── MarketPulse.jsx
│   │   │   ├── SentimentChart.jsx
│   │   │   ├── StockComparisonChart.jsx
│   │   │   ├── IndustryHeatmap.jsx
│   │   │   ├── VolumeSentimentChart.jsx
│   │   │   ├── SentimentByStockChart.jsx
│   │   │   ├── PostsList.jsx
│   │   │   ├── FetchControls.jsx
│   │   │   ├── ExportMenu.jsx
│   │   │   ├── WatchlistPanel.jsx
│   │   │   ├── TickerFilter.jsx
│   │   │   ├── IndustryFilter.jsx
│   │   │   ├── SectorFilter.jsx
│   │   │   ├── DateRangeFilter.jsx
│   │   │   ├── LoadingSpinner.jsx
│   │   │   ├── ErrorMessage.jsx
│   │   │   ├── EmptyState.jsx
│   │   │   └── Tooltip.jsx
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── index.css
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
│
├── README.md
└── .gitignore
```

---

## 🛠️ Technologies Used

### Core
- Python
- Flask
- React
- SQLite
- Vite

### AI / ML
- HuggingFace Transformers
- PyTorch
- FinBERT
- NumPy

### Backend
- Flask-CORS
- requests
- requests-cache
- pandas
- yfinance
- python-dateutil

### Frontend
- Axios
- Chart.js
- react-chartjs-2

---

## 🗄️ Database Schema

### Main Tables

#### `posts`
Stores Reddit post content and sentiment analysis results:
- title
- body/content
- subreddit
- author
- reddit URL
- created time
- sentiment label
- sentiment score

#### `tickers`
Stores ticker-level metadata:
- symbol
- company name
- sector
- industry

#### `industries`
Stores industry categories.

#### `sectors`
Stores sector categories.

#### `post_tickers`
Junction table for many-to-many post/ticker relationships.

#### `watchlists`
Stores user-created watchlists.

#### `watchlist_tickers`
Stores ticker membership inside watchlists.

### Indexing
Indexes are used to improve performance for:
- sentiment filtering
- date filtering
- ticker lookups
- join-heavy analytics queries

---

## 💻 Development

### Run Backend in Development Mode
```bash
cd backend
FLASK_ENV=development python app.py
```

### Run Frontend in Development Mode
```bash
cd frontend
npm run dev
```

### Recommended Manual Testing
- Fetch recent posts from multiple subreddits
- Test historical fetch using a date range
- Verify sentiment labels on obviously positive/negative samples
- Check ticker extraction on multi-ticker posts
- Test export in both CSV and JSON
- Create, edit, and apply watchlists
- Validate stock price and stock history endpoints

---

## 🐛 Troubleshooting

### FinBERT model download issues
Try manual download:

```bash
python -c "from transformers import AutoTokenizer, AutoModelForSequenceClassification; AutoTokenizer.from_pretrained('ProsusAI/finbert'); AutoModelForSequenceClassification.from_pretrained('ProsusAI/finbert')"
```

### Database locked
- Make sure only one backend instance is writing to SQLite
- Close any external SQLite browser sessions
- Check file permissions for the database file

### No posts fetched
- Check internet connectivity
- Verify subreddit names in `config.json`
- Reddit RSS availability may vary
- Retry after a short delay if rate-limited

### CORS issues
- Confirm CORS is enabled in Flask
- Ensure frontend is calling the correct backend URL

### Ticker not detected
- Add or refresh ticker metadata
- verify it exists in mapping / validation sources
- restart the backend if config files are cached on startup

---

## ⚠️ Known Limitations

- Reddit RSS historical availability is limited by source retention
- Date filtering may depend on the timestamps available in fetched RSS items
- `yfinance` is an unofficial data source and may change over time
- SQLite is sufficient for local or small-scale deployment, but larger-scale production setups would likely require a more robust database
- Current UX uses standard browser interaction patterns in a few places that could be polished further

---

## 🚀 Future Enhancements

- User authentication and multi-user watchlists
- Real-time alerts based on sentiment or price thresholds
- Sentiment-price correlation and predictive analytics
- WebSocket-based live dashboard updates
- Advanced LLM summarization and theme extraction
- Additional social/news data sources beyond Reddit
- Broker or portfolio integration
- Deployment hardening, monitoring, and rate limiting

---

## 📌 Summary

This project extends a basic financial sentiment dashboard into a more complete analytics platform by combining:
- Reddit market discussion ingestion
- FinBERT-based financial sentiment analysis
- ticker and market metadata enrichment
- stock price context
- export functionality
- persistent watchlists
- interactive analytics through a full-stack web application

It is well suited for experimentation, portfolio demonstration, and further extension into a larger financial intelligence system.

