from flask import Flask, jsonify, request, Response, send_from_directory
from flask_cors import CORS
from sentiment_analyzer import SentimentAnalyzer
from reddit_rss_client import RedditRSSClient
from database import Database
from ticker_extractor import TickerExtractor
from industry_classifier import IndustryClassifier
from migrations import DatabaseMigration
from stock_data_provider import StockDataProvider
from price_data_provider import PriceDataProvider
from export_service import ExportService
from watchlist_repository import WatchlistRepository
from agent_service import AgentService
from api_utils import (
    success_response, error_response, paginated_response,
    validate_pagination_params, validate_date_param, validate_enum_param
)
import os
import json
import requests
from datetime import datetime, timedelta, timezone

# Load .env file into environment variables
try:
    _env_path = os.path.join(os.path.dirname(__file__), '.env')
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _v = _line.split('=', 1)
                os.environ.setdefault(_k.strip(), _v.strip())
except Exception:
    pass
from alphavantage_news_client import AlphaVantageNewsClient
from yahoo_finance_news_client import YahooFinanceNewsClient
from google_news_client import GoogleNewsClient
from nasdaq_news_client import NasdaqNewsClient
from seeking_alpha_client import SeekingAlphaClient
from cnbc_news_client import CNBCNewsClient
from sec_edgar_client import SECEdgarClient
from motley_fool_client import MotleyFoolClient
from hackernews_client import HackerNewsClient
from apscheduler.schedulers.background import BackgroundScheduler
from whatsapp_service import WhatsAppService


# Configure Flask to serve static files from frontend build
static_folder = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'dist')
app = Flask(__name__, static_folder=static_folder, static_url_path='')

# Load configuration
def load_config():
    try:
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        with open(config_path, 'r') as f:
            raw = f.read()
        # Replace ${ENV_VAR} placeholders with actual environment variables
        import re
        def replace_env(match):
            var = match.group(1)
            return os.environ.get(var, match.group(0))
        raw = re.sub(r'\$\{(\w+)\}', replace_env, raw)
        return json.loads(raw)
    except Exception as e:
        print(f"Warning: Could not load config.json: {e}")
        return {'server': {'port': 5000, 'debug': True, 'cors_origins': ['http://localhost:5173', 'http://localhost:3000']}}

config = load_config()

# Configure CORS with allowed origins
cors_origins = config.get('server', {}).get('cors_origins', ['http://localhost:5173', 'http://localhost:3000'])
CORS(app, resources={r"/api/*": {"origins": cors_origins}})

# Run database migrations on startup
print("Checking database schema...")
migration = DatabaseMigration()
if migration.needs_migration():
    print("Running database migrations...")
    migration.run_migrations()
else:
    print("Database schema is up to date")

# Initialize components
sentiment_analyzer = SentimentAnalyzer()
reddit_client = RedditRSSClient()
try:
    news_client = AlphaVantageNewsClient()
except Exception as e:
    print(f"[WARN] News client disabled: {e}")
    news_client = None

db = Database()
ticker_extractor = TickerExtractor()
industry_classifier = IndustryClassifier()
stock_data_provider = StockDataProvider()
price_data_provider = PriceDataProvider()
export_service = ExportService()
watchlist_repo = WatchlistRepository()
yahoo_news_client = YahooFinanceNewsClient()
google_news_client = GoogleNewsClient()
nasdaq_news_client = NasdaqNewsClient()
seeking_alpha_client = SeekingAlphaClient()
cnbc_news_client = CNBCNewsClient()
sec_edgar_client = SECEdgarClient()
motley_fool_client = MotleyFoolClient()
hackernews_client = HackerNewsClient()

# WhatsApp service
wa_cfg = config.get('whatsapp', {})
whatsapp_service = None
if wa_cfg.get('enabled') and wa_cfg.get('phone') and wa_cfg.get('api_key'):
    whatsapp_service = WhatsAppService(wa_cfg['phone'], wa_cfg['api_key'])
    print(f"[WhatsApp] Notifications enabled → {wa_cfg['phone']}")

# AI Agent (Gemini 2.0 Flash)
gemini_cfg = config.get('gemini', {})
gemini_api_key = gemini_cfg.get('api_key', '')
gemini_model = gemini_cfg.get('model', 'gemini-2.0-flash')
agent_service = None
if gemini_api_key:
    try:
        agent_service = AgentService(db, price_data_provider, gemini_api_key, gemini_model, stock_data_provider)
        print("AI Agent initialized (Gemini 2.0 Flash)")
    except Exception as e:
        print(f"[WARN] AI Agent disabled: {e}")

# ── Auto-fetch scheduler ──────────────────────────────────────────────────────
AUTO_FETCH_TICKERS = config.get('auto_fetch', {}).get(
    'tickers',
    ['NVDA', 'AAPL', 'MSFT', 'GOOG', 'AMZN', 'META', 'TSLA',
     'AVGO', 'TXN', 'COHR', 'INTC', 'ASML', 'SNDK']
)
AUTO_FETCH_INTERVAL_HOURS = config.get('auto_fetch', {}).get('interval_hours', 4)
_last_auto_fetch = None
_next_auto_fetch = None


GEMINI_POST_SCORE_PROMPT = """Rate the investment sentiment for {tickers} in this post.
Score: -1.0 (very bearish) to +1.0 (very bullish) for {tickers} specifically.
Focus on what the author thinks about {tickers} as an investment, not general market mood.
Reply with ONLY a number like: 0.35"""

def _gemini_score_post(text, tickers):
    """Call Gemini to score a single post's sentiment for given tickers. Returns float or None."""
    if not gemini_api_key or not tickers:
        return None
    try:
        ticker_str = ', '.join(tickers[:3])
        content = text[:600]
        prompt = GEMINI_POST_SCORE_PROMPT.format(tickers=ticker_str, content=content)
        # Add the actual post content to the prompt
        full_prompt = prompt + f"\n\nPost: {content}"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_api_key}"
        payload = {
            "contents": [{"parts": [{"text": full_prompt}]}],
            "generationConfig": {"temperature": 0.0, "maxOutputTokens": 20}
        }
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        candidates = data.get('candidates', [])
        if not candidates:
            return None
        parts = candidates[0].get('content', {}).get('parts', [])
        if not parts:
            return None
        raw = parts[0].get('text', '').strip()
        # Extract number from response
        import re as _re
        match = _re.search(r'-?\d+\.?\d*', raw)
        if match:
            score = float(match.group())
            return max(-1.0, min(1.0, score))
    except Exception as e:
        print(f"[GeminiScore] Error: {e}")
    return None


def _process_and_save_post(post, force_ticker=None):
    """Analyze sentiment and save a single post to DB. Skips if already exists."""
    if db.posts.exists(post['id']):
        return
    sentiment = sentiment_analyzer.analyze(post['text'])
    post['sentiment'] = sentiment
    post_id = db.posts.save_post(post)
    tickers_found = ticker_extractor.extract_tickers(post['text'])
    # Always include the ticker we fetched for, even if not found in text
    if force_ticker and force_ticker not in tickers_found:
        tickers_found.append(force_ticker)
    classification = industry_classifier.classify_post_tickers(tickers_found)
    for t in tickers_found:
        info = industry_classifier.get_ticker_info(t) or {}
        db.tickers.save_ticker(t, info.get('company'), info.get('sector'), info.get('industry'))
    if tickers_found:
        db.tickers.link_post_to_tickers(post_id, tickers_found)
        db.tickers.link_post_to_industries_and_sectors(
            post_id, classification['industries'], classification['sectors']
        )


def send_whatsapp_digest():
    """Send daily WhatsApp digest with sentiment + price + AI analysis."""
    if not whatsapp_service:
        return
    try:
        import yfinance as yf
        from datetime import datetime as dt

        today = dt.now().strftime('%b %d, %Y')

        # 1. Build sentiment board for all tickers
        board = []
        for ticker in AUTO_FETCH_TICKERS:
            trends = db.analytics.get_sentiment_trends(days=7, ticker=ticker)
            pos = sum(t.get('positive', 0) for t in trends)
            neg = sum(t.get('negative', 0) for t in trends)
            neu = sum(t.get('neutral', 0) for t in trends)
            total = pos + neg + neu
            score = round((pos - neg) / total, 3) if total > 0 else None
            label = 'no_data' if score is None else ('bullish' if score > 0.1 else ('bearish' if score < -0.1 else 'neutral'))
            info = industry_classifier.get_ticker_info(ticker) or {}

            # Get price from yfinance
            price = None
            change = None
            try:
                p = price_data_provider.get_current_price(ticker)
                if p:
                    price = p.get('price')
                    change = p.get('change_percent')
            except: pass

            board.append({
                'ticker': ticker,
                'company': info.get('company', ticker),
                'score': score,
                'label': label,
                'total_posts': total,
                'price': price,
                'change': change,
            })

        board.sort(key=lambda x: (x['score'] is None, -(x['score'] or 0)))
        has_data = [t for t in board if t['total_posts'] > 0]
        no_data  = [t for t in board if t['total_posts'] == 0]

        # 2. Get AI market brief (one call for overall analysis)
        ai_brief = ''
        if agent_service:
            try:
                ai_brief = agent_service.get_brief()
                # Trim to keep WhatsApp message short
                if len(ai_brief) > 500:
                    ai_brief = ai_brief[:497] + '...'
            except: pass

        # 3. Format WhatsApp message
        lines = [f"📊 *Sentiment Digest — {today}*", ""]

        # AI brief
        if ai_brief:
            lines.append("*🤖 AI Market Brief:*")
            lines.append(ai_brief)
            lines.append("")

        # Top movers (bullish)
        bullish = [t for t in has_data if t['label'] == 'bullish'][:3]
        if bullish:
            lines.append("*🟢 Top Bullish:*")
            for t in bullish:
                price_str = f"${t['price']:.2f}" if t['price'] else 'N/A'
                change_str = f"({t['change']:+.1f}%)" if t['change'] is not None else ''
                lines.append(f"  {t['ticker']} {price_str} {change_str} | score: {t['score']:+.3f} | {t['total_posts']} posts")
            lines.append("")

        # Top movers (bearish)
        bearish = [t for t in has_data if t['label'] == 'bearish'][:3]
        if bearish:
            lines.append("*🔴 Top Bearish:*")
            for t in bearish:
                price_str = f"${t['price']:.2f}" if t['price'] else 'N/A'
                change_str = f"({t['change']:+.1f}%)" if t['change'] is not None else ''
                lines.append(f"  {t['ticker']} {price_str} {change_str} | score: {t['score']:+.3f} | {t['total_posts']} posts")
            lines.append("")

        # Neutral
        neutral = [t for t in has_data if t['label'] == 'neutral']
        if neutral:
            lines.append("*➡️ Neutral:* " + ', '.join(t['ticker'] for t in neutral))
            lines.append("")

        # No data
        if no_data:
            lines.append("*⚪ No data:* " + ', '.join(t['ticker'] for t in no_data))
            lines.append("")

        lines.append("_Your Sentiment Dashboard_")

        message = '\n'.join(lines)
        whatsapp_service.send(message)
        print("[WhatsApp] Daily digest sent")
    except Exception as e:
        print(f"[WhatsApp] Digest failed: {e}")


def auto_fetch_all_tickers():
    """Background job: fetch Reddit + StockTwits + Yahoo News for all focus tickers."""
    global _last_auto_fetch, _next_auto_fetch
    print(f"[Scheduler] Auto-fetch started for {len(AUTO_FETCH_TICKERS)} tickers")
    total_new = 0

    for ticker in AUTO_FETCH_TICKERS:
        posts = []
        # Reddit
        try:
            posts += reddit_client.fetch_posts(ticker, max_results=100)
        except Exception as e:
            print(f"[Scheduler] Reddit {ticker}: {e}")
        # Yahoo Finance News
        try:
            posts += yahoo_news_client.fetch_posts(ticker, limit=30)
        except Exception as e:
            print(f"[Scheduler] YahooNews {ticker}: {e}")
        # Google News
        try:
            posts += google_news_client.fetch_posts(ticker, limit=40)
        except Exception as e:
            print(f"[Scheduler] GoogleNews {ticker}: {e}")
        # Nasdaq News
        try:
            posts += nasdaq_news_client.fetch_posts(ticker, limit=20)
        except Exception as e:
            print(f"[Scheduler] NasdaqNews {ticker}: {e}")
        # Seeking Alpha
        try:
            posts += seeking_alpha_client.fetch_posts(ticker, limit=20)
        except Exception as e:
            print(f"[Scheduler] SeekingAlpha {ticker}: {e}")
        # CNBC
        try:
            posts += cnbc_news_client.fetch_posts(ticker, limit=20)
        except Exception as e:
            print(f"[Scheduler] CNBC {ticker}: {e}")
        # SEC EDGAR 8-K filings
        try:
            posts += sec_edgar_client.fetch_posts(ticker, limit=10)
        except Exception as e:
            print(f"[Scheduler] SEC EDGAR {ticker}: {e}")
        # Motley Fool
        try:
            posts += motley_fool_client.fetch_posts(ticker, limit=15)
        except Exception as e:
            print(f"[Scheduler] MotleyFool {ticker}: {e}")
        # Hacker News
        try:
            posts += hackernews_client.fetch_posts(ticker, limit=20)
        except Exception as e:
            print(f"[Scheduler] HackerNews {ticker}: {e}")

        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        for post in posts:
            try:
                raw_ts = post.get('created_at', '')
                try:
                    post_dt = datetime.fromisoformat(raw_ts.replace('Z', '+00:00'))
                    if post_dt.tzinfo is None:
                        post_dt = post_dt.replace(tzinfo=timezone.utc)
                    if post_dt < cutoff:
                        continue
                except Exception:
                    pass
                _process_and_save_post(post, force_ticker=ticker)
                total_new += 1
            except Exception:
                pass

    _last_auto_fetch = datetime.now(timezone.utc).isoformat()
    _next_auto_fetch = (
        datetime.now(timezone.utc) + timedelta(hours=AUTO_FETCH_INTERVAL_HOURS)
    ).isoformat()
    print(f"[Scheduler] Done — processed {total_new} posts")
    cleanup_old_posts()


def cleanup_old_posts(keep_days=30):
    """Delete posts older than keep_days from the database."""
    try:
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cutoff = (datetime.now(timezone.utc) - timedelta(days=keep_days)).strftime('%Y-%m-%dT%H:%M:%S')
            cursor.execute("DELETE FROM post_tickers WHERE post_id IN (SELECT id FROM posts WHERE created_at < ?)", (cutoff,))
            cursor.execute("DELETE FROM post_industries WHERE post_id IN (SELECT id FROM posts WHERE created_at < ?)", (cutoff,))
            cursor.execute("DELETE FROM post_sectors WHERE post_id IN (SELECT id FROM posts WHERE created_at < ?)", (cutoff,))
            cursor.execute("DELETE FROM posts WHERE created_at < ?", (cutoff,))
            deleted = cursor.rowcount
            if deleted > 0:
                print(f"[Cleanup] Removed {deleted} posts older than {keep_days} days")
    except Exception as e:
        print(f"[Cleanup] Error: {e}")


# Start the scheduler (skip in testing environments)
_scheduler = None
if not os.environ.get('DISABLE_SCHEDULER'):
    try:
        _scheduler = BackgroundScheduler(daemon=True)
        _scheduler.add_job(
            auto_fetch_all_tickers,
            'interval',
            hours=AUTO_FETCH_INTERVAL_HOURS,
            id='auto_fetch',
            replace_existing=True
        )
        # Daily cleanup — keep only last 30 days
        _scheduler.add_job(
            cleanup_old_posts,
            'cron',
            hour=2,
            minute=0,
            id='daily_cleanup',
            replace_existing=True
        )
        # Daily WhatsApp digest
        digest_hour = config.get('whatsapp', {}).get('digest_hour', 8)
        _scheduler.add_job(
            send_whatsapp_digest,
            'cron',
            hour=digest_hour,
            minute=0,
            id='whatsapp_digest',
            replace_existing=True
        )
        _scheduler.start()
        print(f"[Scheduler] Auto-fetch every {AUTO_FETCH_INTERVAL_HOURS}h | WhatsApp digest at {digest_hour}:00")
    except Exception as e:
        print(f"[WARN] Scheduler disabled: {e}")

# V1 API Endpoints
@app.route('/api/v1/health', methods=['GET'])
def health_check_v1():
    """Health check endpoint"""
    return jsonify(success_response({
        'status': 'healthy',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'version': 'v1'
    }))

@app.route('/api/v1/analyze', methods=['POST'])
def analyze_text():
    """Analyze sentiment of provided text"""
    data = request.get_json()
    if not data:
        response, status_code = error_response('INVALID_JSON', 'Invalid JSON')
        return jsonify(response), status_code

    text = data.get('text', '')
    if not text:
        response, status_code = error_response('NO_TEXT', 'No text provided')
        return jsonify(response), status_code

    sentiment = sentiment_analyzer.analyze(text)

    # Extract tickers from text
    tickers = ticker_extractor.extract_tickers(text)

    return jsonify(success_response({
        'sentiment': sentiment,
        'tickers': tickers
    }))

@app.route('/api/v1/fetch-posts', methods=['GET'])
def fetch_posts():
    """Fetch and analyze finance posts from Reddit via RSS"""
    query = request.args.get('query', 'stocks OR finance OR investing')

    # Validate max_results parameter
    max_results_param = request.args.get('max_results', '100')
    try:
        max_results = int(max_results_param)
        max_results = max(1, min(max_results, 500))
    except (ValueError, TypeError):
        max_results = 100  # Use default if invalid

    # Get optional date range parameters
    try:
        start_date = validate_date_param(request.args.get('start_date'), 'start_date')
        end_date = validate_date_param(request.args.get('end_date'), 'end_date')
    except ValueError as e:
        return jsonify(*error_response('INVALID_PARAM', str(e)))

    try:
        posts = []

        # 1️⃣ Reddit（永远都抓）
        reddit_posts = reddit_client.fetch_posts(
            query, max_results, start_date, end_date
        )
        posts.extend(reddit_posts)

        # 2️⃣ News（只在 query 像 ticker 时才抓）
        if news_client:
            q = (query or "").strip().upper()

            # 判断是不是股票代码，例如 NVDA / AAPL / NVDA,TSLA
            looks_like_ticker = (
                "," in q or
                (q.isalnum() and 1 <= len(q) <= 5)
            )

            if looks_like_ticker:
                try:
                    news_posts = news_client.fetch_posts(
                        tickers=q,
                        limit=min(200, max_results)
                    )
                    posts.extend(news_posts)
                except Exception as e:
                    print(f"[WARN] News fetch failed: {e}")

        # 3️⃣ Yahoo Finance News + others（只在 query 像单个 ticker 时才抓）
        q = (query or "").strip().upper()
        is_single_ticker = q.isalnum() and 1 <= len(q) <= 5

        if is_single_ticker:
            # Yahoo Finance News
            try:
                yf_posts = yahoo_news_client.fetch_posts(q, limit=30)
                posts.extend(yf_posts)
                print(f"[YahooNews] {len(yf_posts)} posts for {q}")
            except Exception as e:
                print(f"[WARN] Yahoo Finance News fetch failed: {e}")

            # Google News
            try:
                gn_posts = google_news_client.fetch_posts(q, limit=40)
                posts.extend(gn_posts)
                print(f"[GoogleNews] {len(gn_posts)} posts for {q}")
            except Exception as e:
                print(f"[WARN] Google News fetch failed: {e}")

            # Nasdaq News
            try:
                nd_posts = nasdaq_news_client.fetch_posts(q, limit=20)
                posts.extend(nd_posts)
                print(f"[NasdaqNews] {len(nd_posts)} posts for {q}")
            except Exception as e:
                print(f"[WARN] Nasdaq News fetch failed: {e}")

            # Seeking Alpha
            try:
                sa_posts = seeking_alpha_client.fetch_posts(q, limit=20)
                posts.extend(sa_posts)
                print(f"[SeekingAlpha] {len(sa_posts)} posts for {q}")
            except Exception as e:
                print(f"[WARN] Seeking Alpha fetch failed: {e}")

            # CNBC
            try:
                cnbc_posts = cnbc_news_client.fetch_posts(q, limit=20)
                posts.extend(cnbc_posts)
                print(f"[CNBC] {len(cnbc_posts)} posts for {q}")
            except Exception as e:
                print(f"[WARN] CNBC fetch failed: {e}")

            # SEC EDGAR 8-K filings
            try:
                sec_posts = sec_edgar_client.fetch_posts(q, limit=10)
                posts.extend(sec_posts)
                print(f"[SEC EDGAR] {len(sec_posts)} filings for {q}")
            except Exception as e:
                print(f"[WARN] SEC EDGAR fetch failed: {e}")

            # Motley Fool
            try:
                mf_posts = motley_fool_client.fetch_posts(q, limit=15)
                posts.extend(mf_posts)
                print(f"[MotleyFool] {len(mf_posts)} posts for {q}")
            except Exception as e:
                print(f"[WARN] Motley Fool fetch failed: {e}")

            # Hacker News
            try:
                hn_posts = hackernews_client.fetch_posts(q, limit=20)
                posts.extend(hn_posts)
                print(f"[HackerNews] {len(hn_posts)} posts for {q}")
            except Exception as e:
                print(f"[WARN] Hacker News fetch failed: {e}")

        # 4) 去重（按 url 优先）
        seen = set()
        deduped = []
        for p in posts:
            key = p.get("url") or p.get("id")
            if not key:
                continue
            if key in seen:
                continue
            seen.add(key)
            deduped.append(p)

        posts = deduped[:max_results]

        # Filter out posts older than 30 days before saving
        fetch_cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        filtered_posts = []
        for p in posts:
            try:
                raw_ts = p.get('created_at', '')
                post_dt = datetime.fromisoformat(raw_ts.replace('Z', '+00:00'))
                if post_dt.tzinfo is None:
                    post_dt = post_dt.replace(tzinfo=timezone.utc)
                if post_dt < fetch_cutoff:
                    continue
            except Exception:
                pass  # if date unparseable, skip the post entirely
            filtered_posts.append(p)
        posts = filtered_posts

        analyzed_posts = []

        skipped = 0
        for post in posts:
            # Skip posts already in DB — no need to re-run FinBERT
            if db.posts.exists(post['id']):
                skipped += 1
                continue

            # Analyze sentiment
            sentiment = sentiment_analyzer.analyze(post['text'])

            # Add sentiment to post data
            post['sentiment'] = sentiment

            # Save post to database
            post_id = db.posts.save_post(post)

            # Extract tickers from text
            tickers = ticker_extractor.extract_tickers(post['text'])

            # Get industry/sector classification for tickers
            classification = industry_classifier.classify_post_tickers(tickers)

            # Save tickers and their metadata
            for ticker in tickers:
                ticker_info = industry_classifier.get_ticker_info(ticker)
                if ticker_info:
                    db.tickers.save_ticker(
                        ticker,
                        ticker_info.get('company'),
                        ticker_info.get('sector'),
                        ticker_info.get('industry')
                    )

            # Link post to tickers
            if tickers:
                db.tickers.link_post_to_tickers(post_id, tickers)
                db.tickers.link_post_to_industries_and_sectors(
                    post_id,
                    classification['industries'],
                    classification['sectors']
                )

            analyzed_posts.append({
                'id': post['id'],
                'text': post['text'],
                'title': post.get('title', ''),
                'url': post.get('url', ''),
                'subreddit': post.get('subreddit', ''),
                'author': post.get('author', 'unknown'),
                'created_at': post['created_at'],
                'sentiment': sentiment,
                'tickers': tickers
            })

        print(f"[fetch-posts] new={len(analyzed_posts)} skipped={skipped} (already in DB)")
        return jsonify(success_response({
            'posts': analyzed_posts,
            'count': len(analyzed_posts),
            'skipped': skipped
        }))
    except Exception as e:
        print(f"Error fetching posts: {e}")
        import traceback
        traceback.print_exc()
        return jsonify(*error_response('FETCH_ERROR', str(e), 500))

@app.route('/api/v1/posts', methods=['GET'])
def get_posts():
    """Get stored posts from database with filtering and pagination"""
    try:
        # Validate pagination
        page = request.args.get('page', 1)
        limit = request.args.get('limit', 50)
        page, limit = validate_pagination_params(page, limit)
        offset = (page - 1) * limit

        # Get filter parameters
        ticker = request.args.get('ticker')
        industry = request.args.get('industry')
        sector = request.args.get('sector')
        sentiment = validate_enum_param(
            request.args.get('sentiment'),
            ['positive', 'negative', 'neutral'],
            'sentiment'
        )
        start_date = validate_date_param(request.args.get('start_date'), 'start_date')
        end_date = validate_date_param(request.args.get('end_date'), 'end_date')

        # Get filtered posts
        posts = db.posts.get_posts_filtered(
            ticker=ticker,
            industry=industry,
            sector=sector,
            sentiment=sentiment,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset
        )

        # Get total count for pagination
        total = db.posts.count_posts_filtered(
            ticker=ticker,
            industry=industry,
            sector=sector,
            sentiment=sentiment,
            start_date=start_date,
            end_date=end_date
        )

        return jsonify(paginated_response(posts, page, limit, total))

    except ValueError as e:
        return jsonify(*error_response('INVALID_PARAM', str(e)))
    except Exception as e:
        print(f"Error getting posts: {e}")
        import traceback
        traceback.print_exc()
        return jsonify(*error_response('DATABASE_ERROR', str(e), 500))

@app.route('/api/v1/tickers', methods=['GET'])
def get_tickers():
    """Get all unique tickers"""
    try:
        tickers = db.tickers.get_tickers()
        return jsonify(success_response({'tickers': tickers}))
    except Exception as e:
        return jsonify(*error_response('DATABASE_ERROR', str(e), 500))

@app.route('/api/v1/industries', methods=['GET'])
def get_industries():
    """Get all industries"""
    try:
        industries = db.industries.get_industries()
        return jsonify(success_response({'industries': industries}))
    except Exception as e:
        return jsonify(*error_response('DATABASE_ERROR', str(e), 500))

@app.route('/api/v1/sectors', methods=['GET'])
def get_sectors():
    """Get all sectors"""
    try:
        sectors = db.industries.get_sectors()
        return jsonify(success_response({'sectors': sectors}))
    except Exception as e:
        return jsonify(*error_response('DATABASE_ERROR', str(e), 500))

@app.route('/api/v1/stats', methods=['GET'])
def get_stats():
    """Get sentiment statistics with optional filtering"""
    try:
        ticker = request.args.get('ticker')
        industry = request.args.get('industry')
        sector = request.args.get('sector')
        start_date = validate_date_param(request.args.get('start_date'))
        end_date = validate_date_param(request.args.get('end_date'))

        stats = db.analytics.get_sentiment_stats(
            ticker=ticker,
            industry=industry,
            sector=sector,
            start_date=start_date,
            end_date=end_date
        )

        return jsonify(success_response(stats))
    except ValueError as e:
        return jsonify(*error_response('INVALID_PARAM', str(e)))
    except Exception as e:
        return jsonify(*error_response('DATABASE_ERROR', str(e), 500))

@app.route('/api/v1/trends', methods=['GET'])
def get_trends():
    """Get sentiment trends over time with filtering"""
    try:
        days = int(request.args.get('days', 7))
        days = max(1, min(days, 365))

        ticker = request.args.get('ticker')
        industry = request.args.get('industry')
        sector = request.args.get('sector')
        start_date = validate_date_param(request.args.get('start_date'))
        end_date = validate_date_param(request.args.get('end_date'))
        granularity = validate_enum_param(
            request.args.get('granularity', 'day'),
            ['day', 'week'],
            'granularity'
        )

        trends = db.analytics.get_sentiment_trends(
            days=days,
            ticker=ticker,
            industry=industry,
            sector=sector,
            start_date=start_date,
            end_date=end_date,
            granularity=granularity
        )

        return jsonify(success_response({'trends': trends}))
    except ValueError as e:
        return jsonify(*error_response('INVALID_PARAM', str(e)))
    except Exception as e:
        return jsonify(*error_response('DATABASE_ERROR', str(e), 500))

@app.route('/api/v1/sentiment-by-ticker', methods=['GET'])
def get_sentiment_by_ticker():
    """Get sentiment breakdown per ticker"""
    try:
        ticker_param = request.args.get('tickers')
        tickers = ticker_param.split(',') if ticker_param else None
        start_date = validate_date_param(request.args.get('start_date'))
        end_date = validate_date_param(request.args.get('end_date'))

        ticker_sentiments = db.analytics.get_sentiment_by_ticker(
            tickers=tickers,
            start_date=start_date,
            end_date=end_date
        )

        return jsonify(success_response({'ticker_sentiments': ticker_sentiments}))
    except ValueError as e:
        return jsonify(*error_response('INVALID_PARAM', str(e)))
    except Exception as e:
        return jsonify(*error_response('DATABASE_ERROR', str(e), 500))

@app.route('/api/v1/sentiment-comparison', methods=['GET'])
def get_sentiment_comparison():
    """Compare sentiment of multiple tickers side-by-side"""
    try:
        ticker_param = request.args.get('tickers')
        if not ticker_param:
            return jsonify(*error_response('MISSING_PARAM', 'tickers parameter required'))

        tickers = [t.strip().upper() for t in ticker_param.split(',')]
        start_date = validate_date_param(request.args.get('start_date'))
        end_date = validate_date_param(request.args.get('end_date'))

        comparison_data = db.analytics.get_sentiment_by_ticker(
            tickers=tickers,
            start_date=start_date,
            end_date=end_date
        )

        return jsonify(success_response({'comparison': comparison_data}))
    except ValueError as e:
        return jsonify(*error_response('INVALID_PARAM', str(e)))
    except Exception as e:
        return jsonify(*error_response('DATABASE_ERROR', str(e), 500))

@app.route('/api/v1/industry-heatmap', methods=['GET'])
def get_industry_heatmap():
    """Get industry-level sentiment aggregation for heatmap"""
    try:
        start_date = validate_date_param(request.args.get('start_date'))
        end_date = validate_date_param(request.args.get('end_date'))

        # Get all industries
        industries = db.industries.get_industries()

        # Get sentiment stats for each industry
        heatmap_data = []
        for industry_obj in industries:
            industry_name = industry_obj['name']
            stats = db.analytics.get_sentiment_stats(
                industry=industry_name,
                start_date=start_date,
                end_date=end_date
            )

            heatmap_data.append({
                'industry': industry_name,
                'total': stats['total'],
                'sentiments': stats['by_sentiment']
            })

        return jsonify(success_response({'heatmap': heatmap_data}))
    except ValueError as e:
        return jsonify(*error_response('INVALID_PARAM', str(e)))
    except Exception as e:
        return jsonify(*error_response('DATABASE_ERROR', str(e), 500))

@app.route('/api/v1/market-pulse', methods=['GET'])
def get_market_pulse():
    """Get market pulse data (most discussed, most positive/negative, etc.)"""
    try:
        start_date = validate_date_param(request.args.get('start_date'))
        end_date = validate_date_param(request.args.get('end_date'))

        pulse_data = db.analytics.get_market_pulse(
            start_date=start_date,
            end_date=end_date
        )

        return jsonify(success_response(pulse_data))
    except ValueError as e:
        return jsonify(*error_response('INVALID_PARAM', str(e)))
    except Exception as e:
        print(f"Error getting market pulse: {e}")
        import traceback
        traceback.print_exc()
        return jsonify(*error_response('DATABASE_ERROR', str(e), 500))

@app.route('/api/v1/volume-sentiment-correlation', methods=['GET'])
def get_volume_sentiment_correlation():
    """Get post volume vs sentiment over time"""
    try:
        days = int(request.args.get('days', 7))
        days = max(1, min(days, 365))

        ticker = request.args.get('ticker')
        start_date = validate_date_param(request.args.get('start_date'))
        end_date = validate_date_param(request.args.get('end_date'))

        trends = db.analytics.get_sentiment_trends(
            days=days,
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            granularity='day'
        )

        # Calculate volume and average sentiment for each day
        correlation_data = []
        for trend in trends:
            total_volume = trend['positive'] + trend['negative'] + trend['neutral']

            # Calculate weighted average sentiment score
            # positive = 1, neutral = 0, negative = -1
            if total_volume > 0:
                avg_sentiment = (
                    (trend['positive'] * 1.0 + trend['neutral'] * 0.0 + trend['negative'] * -1.0)
                    / total_volume
                )
            else:
                avg_sentiment = 0

            correlation_data.append({
                'date': trend['date'],
                'volume': total_volume,
                'avg_sentiment': round(avg_sentiment, 2),
                'positive': trend['positive'],
                'neutral': trend['neutral'],
                'negative': trend['negative']
            })

        return jsonify(success_response({'correlation': correlation_data}))
    except ValueError as e:
        return jsonify(*error_response('INVALID_PARAM', str(e)))
    except Exception as e:
        return jsonify(*error_response('DATABASE_ERROR', str(e), 500))

@app.route('/api/v1/stock-price/<ticker>', methods=['GET'])
def get_stock_price(ticker):
    """Get current stock price for a ticker"""
    try:
        price_data = price_data_provider.get_current_price(ticker)
        if price_data:
            return jsonify(success_response(price_data))
        else:
            return jsonify(*error_response('NOT_FOUND', f'Price data not found for {ticker}', 404))
    except Exception as e:
        return jsonify(*error_response('PRICE_ERROR', str(e), 500))

@app.route('/api/v1/stock-history/<ticker>', methods=['GET'])
def get_stock_history(ticker):
    """Get historical stock prices"""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        interval = request.args.get('interval', '1d')

        if not start_date or not end_date:
            return jsonify(*error_response('MISSING_PARAM', 'start_date and end_date are required'))

        history = price_data_provider.get_historical_prices(ticker, start_date, end_date, interval)
        if history:
            return jsonify(success_response({'history': history}))
        else:
            return jsonify(*error_response('NOT_FOUND', f'Historical data not found for {ticker}', 404))
    except Exception as e:
        return jsonify(*error_response('PRICE_ERROR', str(e), 500))

@app.route('/api/v1/market-indices', methods=['GET'])
def get_market_indices():
    """Get current market indices (S&P 500, Nasdaq, Dow Jones)"""
    try:
        indices = price_data_provider.get_market_indices()
        return jsonify(success_response(indices))
    except Exception as e:
        return jsonify(*error_response('PRICE_ERROR', str(e), 500))

@app.route('/api/v1/stock-data/refresh', methods=['POST'])
def refresh_stock_data():
    """Admin endpoint to refresh stock data cache"""
    try:
        stock_data_provider.refresh_cache()
        return jsonify(success_response({'message': 'Stock data cache refreshed'}))
    except Exception as e:
        return jsonify(*error_response('REFRESH_ERROR', str(e), 500))

@app.route('/api/v1/stock-data/info', methods=['GET'])
def get_stock_data_info():
    """Get information about cached stock data"""
    try:
        info = stock_data_provider.get_cache_info()
        return jsonify(success_response(info))
    except Exception as e:
        return jsonify(*error_response('INFO_ERROR', str(e), 500))

@app.route('/api/v1/stock-data/populate', methods=['POST'])
def populate_stock_data():
    """Populate database with comprehensive stock data from yfinance"""
    try:
        limit = int(request.args.get('limit', 200))
        stocks = stock_data_provider.fetch_popular_stocks(limit)

        # Save to database
        for stock in stocks:
            db.tickers.save_ticker(
                stock['ticker'],
                stock.get('company'),
                stock.get('sector'),
                stock.get('industry')
            )

        return jsonify(success_response({
            'message': f'Successfully populated {len(stocks)} stocks',
            'count': len(stocks)
        }))
    except Exception as e:
        return jsonify(*error_response('POPULATE_ERROR', str(e), 500))

@app.route('/api/v1/export/posts', methods=['GET'])
def export_posts():
    """Export posts to CSV or JSON"""
    try:
        format_type = request.args.get('format', 'csv').lower()

        # Get filter parameters
        ticker = request.args.get('ticker')
        industry = request.args.get('industry')
        sector = request.args.get('sector')
        sentiment = validate_enum_param(
            request.args.get('sentiment'),
            ['positive', 'negative', 'neutral'],
            'sentiment'
        )
        start_date = validate_date_param(request.args.get('start_date'))
        end_date = validate_date_param(request.args.get('end_date'))
        limit = int(request.args.get('limit', 1000))

        # Get filtered posts
        posts = db.posts.get_posts_filtered(
            ticker=ticker,
            industry=industry,
            sector=sector,
            sentiment=sentiment,
            start_date=start_date,
            end_date=end_date,
            limit=min(limit, 10000),
            offset=0
        )

        if format_type == 'csv':
            csv_data = export_service.export_posts_to_csv(posts)
            return Response(
                csv_data,
                mimetype='text/csv',
                headers={'Content-Disposition': 'attachment; filename=posts.csv'}
            )
        elif format_type == 'json':
            json_data = export_service.export_posts_to_json(posts)
            return Response(
                json_data,
                mimetype='application/json',
                headers={'Content-Disposition': 'attachment; filename=posts.json'}
            )
        else:
            return jsonify(*error_response('INVALID_FORMAT', 'Format must be csv or json'))

    except ValueError as e:
        return jsonify(*error_response('INVALID_PARAM', str(e)))
    except Exception as e:
        return jsonify(*error_response('EXPORT_ERROR', str(e), 500))

@app.route('/api/v1/export/sentiment-trends', methods=['GET'])
def export_sentiment_trends():
    """Export sentiment trends to CSV or JSON"""
    try:
        format_type = request.args.get('format', 'csv').lower()
        days = int(request.args.get('days', 30))

        ticker = request.args.get('ticker')
        industry = request.args.get('industry')
        sector = request.args.get('sector')
        start_date = validate_date_param(request.args.get('start_date'))
        end_date = validate_date_param(request.args.get('end_date'))
        granularity = validate_enum_param(
            request.args.get('granularity', 'day'),
            ['day', 'week'],
            'granularity'
        )

        trends = db.analytics.get_sentiment_trends(
            days=days,
            ticker=ticker,
            industry=industry,
            sector=sector,
            start_date=start_date,
            end_date=end_date,
            granularity=granularity
        )

        if format_type == 'csv':
            csv_data = export_service.export_sentiment_trends_to_csv(trends)
            return Response(
                csv_data,
                mimetype='text/csv',
                headers={'Content-Disposition': 'attachment; filename=sentiment_trends.csv'}
            )
        elif format_type == 'json':
            json_data = export_service.export_sentiment_trends_to_json(trends)
            return Response(
                json_data,
                mimetype='application/json',
                headers={'Content-Disposition': 'attachment; filename=sentiment_trends.json'}
            )
        else:
            return jsonify(*error_response('INVALID_FORMAT', 'Format must be csv or json'))

    except ValueError as e:
        return jsonify(*error_response('INVALID_PARAM', str(e)))
    except Exception as e:
        return jsonify(*error_response('EXPORT_ERROR', str(e), 500))

@app.route('/api/v1/watchlists', methods=['GET', 'POST'])
def manage_watchlists():
    """Get all watchlists or create a new one"""
    if request.method == 'GET':
        try:
            watchlists = watchlist_repo.get_watchlists()
            return jsonify(success_response({'watchlists': watchlists}))
        except Exception as e:
            return jsonify(*error_response('WATCHLIST_ERROR', str(e), 500))

    elif request.method == 'POST':
        try:
            data = request.get_json()
            if not data or 'name' not in data:
                return jsonify(*error_response('INVALID_REQUEST', 'name is required'))

            watchlist_id = watchlist_repo.create_watchlist(data['name'])
            watchlist = watchlist_repo.get_watchlist(watchlist_id)
            return jsonify(success_response(watchlist), 201)
        except Exception as e:
            return jsonify(*error_response('WATCHLIST_ERROR', str(e), 500))

@app.route('/api/v1/watchlists/<int:watchlist_id>', methods=['GET', 'PUT', 'DELETE'])
def manage_watchlist(watchlist_id):
    """Get, update, or delete a specific watchlist"""
    if request.method == 'GET':
        try:
            watchlist = watchlist_repo.get_watchlist(watchlist_id)
            if watchlist:
                return jsonify(success_response(watchlist))
            else:
                return jsonify(*error_response('NOT_FOUND', 'Watchlist not found', 404))
        except Exception as e:
            return jsonify(*error_response('WATCHLIST_ERROR', str(e), 500))

    elif request.method == 'PUT':
        try:
            data = request.get_json()
            if not data or 'name' not in data:
                return jsonify(*error_response('INVALID_REQUEST', 'name is required'))

            updated = watchlist_repo.update_watchlist(watchlist_id, data['name'])
            if updated:
                watchlist = watchlist_repo.get_watchlist(watchlist_id)
                return jsonify(success_response(watchlist))
            else:
                return jsonify(*error_response('NOT_FOUND', 'Watchlist not found', 404))
        except Exception as e:
            return jsonify(*error_response('WATCHLIST_ERROR', str(e), 500))

    elif request.method == 'DELETE':
        try:
            deleted = watchlist_repo.delete_watchlist(watchlist_id)
            if deleted:
                return jsonify(success_response({'message': 'Watchlist deleted'}))
            else:
                return jsonify(*error_response('NOT_FOUND', 'Watchlist not found', 404))
        except Exception as e:
            return jsonify(*error_response('WATCHLIST_ERROR', str(e), 500))

@app.route('/api/v1/watchlists/<int:watchlist_id>/tickers', methods=['POST'])
def add_ticker_to_watchlist(watchlist_id):
    """Add a ticker to a watchlist"""
    try:
        data = request.get_json()
        if not data or 'ticker' not in data:
            return jsonify(*error_response('INVALID_REQUEST', 'ticker is required'))

        added = watchlist_repo.add_ticker_to_watchlist(watchlist_id, data['ticker'])
        if added:
            return jsonify(success_response({'message': 'Ticker added to watchlist'}))
        else:
            return jsonify(*error_response('ALREADY_EXISTS', 'Ticker already in watchlist', 409))
    except Exception as e:
        return jsonify(*error_response('WATCHLIST_ERROR', str(e), 500))

@app.route('/api/v1/watchlists/<int:watchlist_id>/tickers/<ticker>', methods=['DELETE'])
def remove_ticker_from_watchlist(watchlist_id, ticker):
    """Remove a ticker from a watchlist"""
    try:
        removed = watchlist_repo.remove_ticker_from_watchlist(watchlist_id, ticker)
        if removed:
            return jsonify(success_response({'message': 'Ticker removed from watchlist'}))
        else:
            return jsonify(*error_response('NOT_FOUND', 'Ticker not found in watchlist', 404))
    except Exception as e:
        return jsonify(*error_response('WATCHLIST_ERROR', str(e), 500))

@app.route('/api/v1/ticker-detail/<ticker>', methods=['GET'])
def get_ticker_detail(ticker):
    """Return combined sentiment + yfinance data for a ticker."""
    from datetime import datetime, timedelta
    ticker = ticker.upper().strip()
    days = int(request.args.get('days', 7))
    try:
        # Sentiment from DB
        trends = db.analytics.get_sentiment_trends(days=days, ticker=ticker)
        total_pos = sum(t.get('positive', 0) for t in trends)
        total_neg = sum(t.get('negative', 0) for t in trends)
        total_neu = sum(t.get('neutral', 0) for t in trends)
        total = total_pos + total_neg + total_neu
        score = round(sum(t.get('avg_signed_score', 0) * (t.get('positive',0)+t.get('negative',0)+t.get('neutral',0)) for t in trends) / total, 3) if total > 0 else None
        if score is None: label = 'no_data'
        elif score > 0.1: label = 'bullish'
        elif score < -0.1: label = 'bearish'
        else: label = 'neutral'

        # Daily sentiment scores for chart (sorted oldest → newest)
        daily = []
        for t in sorted(trends, key=lambda x: x.get('date', '')):
            pos = t.get('positive', 0)
            neg = t.get('negative', 0)
            neu = t.get('neutral', 0)
            daily.append({
                'date': t.get('date'),
                'score': t.get('avg_signed_score'),
                'positive': pos,
                'negative': neg,
                'neutral': neu,
            })

        sentiment = {
            'total_posts': total,
            'positive': total_pos,
            'negative': total_neg,
            'neutral': total_neu,
            'score': score,
            'label': label,
            'positive_pct': round(total_pos / total * 100, 1) if total > 0 else 0,
            'negative_pct': round(total_neg / total * 100, 1) if total > 0 else 0,
            'neutral_pct': round(total_neu / total * 100, 1) if total > 0 else 0,
            'daily': daily,
        }

        # Company info
        info = industry_classifier.get_ticker_info(ticker) or {}

        # yfinance data
        price_data = {}
        try:
            current = price_data_provider.get_current_price(ticker)
            if current:
                price_data['current_price'] = current.get('price')
                price_data['change_today_pct'] = round(current.get('change_percent') or 0, 2)
                price_data['market_state'] = current.get('market_state')
        except: pass

        try:
            import yfinance as yf
            from datetime import date as _date
            stock = yf.Ticker(ticker)
            # Use same calendar-day cutoff as sentiment: now - timedelta(days=days)
            # Buffer: extra 15 days + half of days to safely cover weekends/holidays
            fetch_buf = days + max(15, days // 2)
            hist = stock.history(period=f'{fetch_buf}d', interval='1d')
            if not hist.empty:
                hist_dates = [d.date() for d in hist.index]
                cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date()

                # Chart data: all closes on or after the cutoff (matches sentiment window)
                window_rows = [(str(hist_dates[i]), round(float(hist['Close'].iloc[i]), 2))
                               for i in range(len(hist_dates)) if hist_dates[i] >= cutoff]
                price_data['price_7d'] = [{'date': d, 'close': c} for d, c in window_rows]

                # start_close: last close ON OR BEFORE cutoff (same as sentiment start boundary)
                before = [float(hist['Close'].iloc[i]) for i in range(len(hist_dates)) if hist_dates[i] <= cutoff]
                start_close = before[-1] if before else float(hist['Close'].iloc[0])

                # current price: use real-time price from yfinance info when available
                # (hist['Close'].iloc[-1] is yesterday's close when market is open)
                current_price = price_data.get('current_price') or float(hist['Close'].iloc[-1])

                price_data['price_7d_change_pct'] = round((current_price - start_close) / start_close * 100, 2) if start_close else None
                price_data['trend'] = (
                    'uptrend' if current_price > start_close else
                    'downtrend' if current_price < start_close else 'flat'
                )
                # Use actual High/Low columns for period range
                window_idx = [i for i in range(len(hist_dates)) if hist_dates[i] >= cutoff]
                if window_idx:
                    price_data['period_high'] = round(float(hist['High'].iloc[window_idx].max()), 2)
                    price_data['period_low'] = round(float(hist['Low'].iloc[window_idx].min()), 2)
        except Exception as e:
            print(f"[ticker-detail] history error for {ticker}: {e}")

        try:
            import yfinance as yf
            yf_info = yf.Ticker(ticker).info
            price_data['company_name'] = yf_info.get('longName') or yf_info.get('shortName', ticker)
            price_data['sector'] = yf_info.get('sector')
            price_data['industry'] = yf_info.get('industry')
            price_data['market_cap'] = yf_info.get('marketCap')
            price_data['pe_ratio'] = yf_info.get('trailingPE')
            price_data['52w_high'] = yf_info.get('fiftyTwoWeekHigh')
            price_data['52w_low'] = yf_info.get('fiftyTwoWeekLow')
            hi = price_data.get('52w_high')
            lo = price_data.get('52w_low')
            price = price_data.get('current_price')
            if hi and lo and price and (hi - lo) > 0:
                price_data['52w_position_pct'] = round((price - lo) / (hi - lo) * 100, 1)
        except: pass

        # Fetch recent posts from DB for content analysis
        recent_posts = []
        try:
            posts = db.posts.get_posts_filtered(ticker=ticker, limit=60)
            seen_titles = set()
            for p in posts:
                title = (p.get('title') or '').strip()
                text = (p.get('text') or '').strip()
                content = title if title else text[:150]
                if not content:
                    continue
                # Deduplicate by normalized title (catches Yahoo/Google duplicates)
                norm = ''.join(content.lower().split())[:80]
                if norm in seen_titles:
                    continue
                seen_titles.add(norm)

                # Resolve source: prefer source column, fall back to subreddit
                raw_source = p.get('source') or p.get('subreddit') or ''
                if raw_source in ('', None) or raw_source.startswith('r/') or raw_source in (
                    'stocks', 'StockMarket', 'investing', 'wallstreetbets', 'finance',
                    'ValueInvesting', 'pennystocks', 'ETFs', 'options', 'SecurityAnalysis',
                    'dividends', 'Daytrading', 'algotrading', 'technicalanalysis'
                ):
                    source = 'reddit'
                else:
                    source = raw_source

                recent_posts.append({
                    'content': content[:150],
                    'sentiment': p.get('sentiment_label'),
                    'source': source,
                    'date': str(p.get('created_at', ''))[:10],
                        'url': p.get('url', ''),
                    })
        except Exception as e:
            print(f"[ticker-detail] posts error: {e}")

        return jsonify(success_response({
            'ticker': ticker,
            'company': info.get('company') or price_data.get('company_name', ticker),
            'sector': info.get('sector') or price_data.get('sector', ''),
            'industry': info.get('industry') or price_data.get('industry', ''),
            'sentiment': sentiment,
            'price': price_data,
            'days': days,
            'recent_posts': recent_posts,
        }))
    except Exception as e:
        return jsonify(*error_response('DETAIL_ERROR', str(e), 500))

# ── Scheduler Endpoints ───────────────────────────────────────────────────────

@app.route('/api/v1/scheduler/status', methods=['GET'])
def scheduler_status():
    return jsonify(success_response({
        'last_fetch': _last_auto_fetch,
        'next_fetch': _next_auto_fetch,
        'interval_hours': AUTO_FETCH_INTERVAL_HOURS,
        'tickers': AUTO_FETCH_TICKERS,
        'running': _scheduler is not None and _scheduler.running,
    }))

@app.route('/api/v1/scheduler/run-now', methods=['POST'])
def scheduler_run_now():
    """Manually trigger an immediate auto-fetch."""
    import threading
    t = threading.Thread(target=auto_fetch_all_tickers, daemon=True)
    t.start()
    return jsonify(success_response({'message': 'Auto-fetch started in background'}))

# ── WhatsApp Endpoints ────────────────────────────────────────────────────────

@app.route('/api/v1/whatsapp/status', methods=['GET'])
def whatsapp_status():
    wa_cfg = config.get('whatsapp', {})
    return jsonify(success_response({
        'enabled': wa_cfg.get('enabled', False),
        'phone': wa_cfg.get('phone', ''),
        'digest_hour': wa_cfg.get('digest_hour', 8),
        'configured': whatsapp_service is not None,
    }))

@app.route('/api/v1/whatsapp/send-now', methods=['POST'])
def whatsapp_send_now():
    """Manually trigger a WhatsApp digest right now."""
    if not whatsapp_service:
        return jsonify(*error_response('WA_DISABLED', 'WhatsApp not configured', 503))
    import threading
    threading.Thread(target=send_whatsapp_digest, daemon=True).start()
    return jsonify(success_response({'message': 'Digest sending in background'}))

@app.route('/api/v1/whatsapp/test', methods=['POST'])
def whatsapp_test():
    """Send a test message to verify setup."""
    if not whatsapp_service:
        return jsonify(*error_response('WA_DISABLED', 'WhatsApp not configured', 503))
    ok = whatsapp_service.send("✅ WhatsApp integration working! Your daily sentiment digest is configured.")
    if ok:
        return jsonify(success_response({'message': 'Test message sent'}))
    return jsonify(*error_response('WA_FAILED', 'Failed to send message', 500))

# ── Sentiment Lab Endpoints ───────────────────────────────────────────────────

@app.route('/api/v1/lab/method-comparison', methods=['GET'])
def lab_method_comparison():
    """Compare 4 sentiment score methods across all tickers."""
    days = int(request.args.get('days', 7))
    tickers_param = request.args.get('tickers', '')
    ticker_list = [t.strip().upper() for t in tickers_param.split(',') if t.strip()] if tickers_param else None

    try:
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%S')

            ticker_filter = ''
            params = [cutoff]
            if ticker_list:
                placeholders = ','.join('?' * len(ticker_list))
                ticker_filter = f'AND t.symbol IN ({placeholders})'
                params.extend(ticker_list)

            cursor.execute(f'''
                SELECT t.symbol,
                  COUNT(*) as total_posts,
                  SUM(CASE WHEN p.sentiment_label='positive' THEN 1 ELSE 0 END) as pos_count,
                  SUM(CASE WHEN p.sentiment_label='negative' THEN 1 ELSE 0 END) as neg_count,
                  SUM(CASE WHEN p.sentiment_label='neutral'  THEN 1 ELSE 0 END) as neu_count,
                  AVG(p.sentiment_signed_score) as avg_signed,
                  AVG(CASE WHEN p.sentiment_score > 0.7 THEN p.sentiment_signed_score END) as high_conf_signed,
                  AVG(p.sentiment_score) as avg_confidence
                FROM posts p
                JOIN post_tickers pt ON p.id = pt.post_id
                JOIN tickers t ON pt.ticker_id = t.id
                WHERE p.created_at >= ? {ticker_filter}
                GROUP BY t.symbol
                HAVING total_posts >= 5
                ORDER BY avg_signed DESC
            ''', params)

            rows = cursor.fetchall()
            if not rows:
                return jsonify(success_response({'rows': [], 'stats': {}}))

            # Compute z-score across tickers
            scores = [r['avg_signed'] or 0 for r in rows]
            mean_s = sum(scores) / len(scores)
            variance = sum((s - mean_s) ** 2 for s in scores) / len(scores)
            std_s = variance ** 0.5 if variance > 0 else 1

            result = []
            for r in rows:
                avg = r['avg_signed'] or 0
                total = r['total_posts']
                method_a = round((r['pos_count'] - r['neg_count']) / total, 4) if total > 0 else 0
                method_b = round(avg, 4)
                method_c = round(r['high_conf_signed'] or 0, 4)
                method_d = round((avg - mean_s) / std_s, 4) if std_s > 0 else 0

                def label(score, z=False):
                    if z:
                        return 'bullish' if score > 0.5 else ('bearish' if score < -0.5 else 'neutral')
                    return 'bullish' if score > 0.05 else ('bearish' if score < -0.03 else 'neutral')

                result.append({
                    'ticker': r['symbol'],
                    'total_posts': total,
                    'pos': r['pos_count'], 'neg': r['neg_count'], 'neu': r['neu_count'],
                    'avg_confidence': round(r['avg_confidence'] or 0, 3),
                    'method_a': method_a, 'label_a': label(method_a),
                    'method_b': method_b, 'label_b': label(method_b),
                    'method_c': method_c, 'label_c': label(method_c),
                    'method_d': method_d, 'label_d': label(method_d, z=True),
                })

            return jsonify(success_response({
                'rows': result,
                'days': days,
                'stats': {'mean': round(mean_s, 4), 'std': round(std_s, 4), 'n_tickers': len(result)}
            }))
    except Exception as e:
        return jsonify(*error_response('LAB_ERROR', str(e), 500))


@app.route('/api/v1/lab/backtest', methods=['GET'])
def lab_backtest():
    """Daily sentiment vs price movement for a ticker."""
    ticker = request.args.get('ticker', 'NVDA').upper()
    days = int(request.args.get('days', 30))

    try:
        import yfinance as yf
        from datetime import timedelta as td

        cutoff = (datetime.now(timezone.utc) - td(days=days)).strftime('%Y-%m-%dT%H:%M:%S')

        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT DATE(p.created_at) as day,
                  AVG(p.sentiment_signed_score) as avg_signed,
                  COUNT(*) as posts,
                  SUM(CASE WHEN p.sentiment_label='positive' THEN 1 ELSE 0 END) as pos,
                  SUM(CASE WHEN p.sentiment_label='negative' THEN 1 ELSE 0 END) as neg
                FROM posts p
                JOIN post_tickers pt ON p.id = pt.post_id
                JOIN tickers t ON pt.ticker_id = t.id
                WHERE t.symbol = ? AND p.created_at >= ?
                GROUP BY day ORDER BY day ASC
            ''', (ticker, cutoff))
            sentiment_rows = {r['day']: dict(r) for r in cursor.fetchall()}

        # Get price history
        hist = yf.Ticker(ticker).history(period=f'{days + 5}d', interval='1d')
        price_data = {}
        closes = list(zip([str(d.date()) for d in hist.index], hist['Close'].tolist()))
        for i in range(1, len(closes)):
            date, close = closes[i]
            prev_close = closes[i-1][1]
            price_data[date] = {
                'close': round(close, 2),
                'price_change_pct': round((close - prev_close) / prev_close * 100, 3)
            }

        # Merge: sentiment day → next day's price change (1-day lag)
        daily = []
        sent_dates = sorted(sentiment_rows.keys())
        for i, date in enumerate(sent_dates):
            s = sentiment_rows[date]
            # same day price change
            p_same = price_data.get(date, {})
            # next trading day price change
            next_dates = [d for d in sorted(price_data.keys()) if d > date]
            p_next = price_data.get(next_dates[0], {}) if next_dates else {}

            daily.append({
                'date': date,
                'sentiment': round(s['avg_signed'] or 0, 4),
                'posts': s['posts'],
                'pos': s['pos'], 'neg': s['neg'],
                'price_close': p_same.get('close'),
                'price_change_pct': p_same.get('price_change_pct'),
                'next_day_price_change_pct': p_next.get('price_change_pct'),
            })

        # Correlation stats
        pairs_same = [(d['sentiment'], d['price_change_pct']) for d in daily if d['price_change_pct'] is not None]
        pairs_lag1 = [(d['sentiment'], d['next_day_price_change_pct']) for d in daily if d['next_day_price_change_pct'] is not None]

        def pearson(pairs):
            if len(pairs) < 3:
                return None
            xs = [p[0] for p in pairs]
            ys = [p[1] for p in pairs]
            mx, my = sum(xs)/len(xs), sum(ys)/len(ys)
            num = sum((x-mx)*(y-my) for x,y in zip(xs,ys))
            den = (sum((x-mx)**2 for x in xs) * sum((y-my)**2 for y in ys)) ** 0.5
            return round(num/den, 4) if den > 0 else None

        # Conditional average: when bullish/bearish next day price
        bull_days = [d['next_day_price_change_pct'] for d in daily if d['sentiment'] > 0.05 and d['next_day_price_change_pct'] is not None]
        bear_days = [d['next_day_price_change_pct'] for d in daily if d['sentiment'] < -0.03 and d['next_day_price_change_pct'] is not None]
        neut_days = [d['next_day_price_change_pct'] for d in daily if -0.03 <= d['sentiment'] <= 0.05 and d['next_day_price_change_pct'] is not None]

        return jsonify(success_response({
            'ticker': ticker,
            'days': days,
            'daily': daily,
            'correlation': {
                'same_day': pearson(pairs_same),
                'lag_1_day': pearson(pairs_lag1),
            },
            'conditional_avg_next_day': {
                'when_bullish': round(sum(bull_days)/len(bull_days), 3) if bull_days else None,
                'when_bearish': round(sum(bear_days)/len(bear_days), 3) if bear_days else None,
                'when_neutral': round(sum(neut_days)/len(neut_days), 3) if neut_days else None,
                'n_bullish_days': len(bull_days),
                'n_bearish_days': len(bear_days),
                'n_neutral_days': len(neut_days),
            }
        }))
    except Exception as e:
        return jsonify(*error_response('BACKTEST_ERROR', str(e), 500))


@app.route('/api/v1/lab/distribution', methods=['GET'])
def lab_distribution():
    """Histogram of signed_score distribution by source."""
    days = int(request.args.get('days', 30))
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%S')
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT source, sentiment_signed_score, sentiment_label, sentiment_score
                FROM posts
                WHERE created_at >= ?
            ''', (cutoff,))
            rows = cursor.fetchall()

        buckets = [-1.0, -0.8, -0.6, -0.4, -0.2, -0.05, 0.05, 0.2, 0.4, 0.6, 0.8, 1.01]
        bucket_labels = ['<-0.8','-0.8~-0.6','-0.6~-0.4','-0.4~-0.2','-0.2~-0.05','Near 0','0~0.2','0.2~0.4','0.4~0.6','0.6~0.8','>0.8']

        hist = [0] * len(bucket_labels)
        by_source = {}

        for r in rows:
            score = r['sentiment_signed_score'] or 0
            src = r['source'] or 'reddit'
            for i in range(len(buckets)-1):
                if buckets[i] <= score < buckets[i+1]:
                    hist[i] += 1
                    break
            if src not in by_source:
                by_source[src] = {'count': 0, 'avg_signed': 0, '_sum': 0}
            by_source[src]['count'] += 1
            by_source[src]['_sum'] += score

        for src in by_source:
            n = by_source[src]['count']
            by_source[src]['avg_signed'] = round(by_source[src]['_sum'] / n, 4) if n > 0 else 0
            del by_source[src]['_sum']

        total = len(rows)
        return jsonify(success_response({
            'days': days,
            'total_posts': total,
            'histogram': [{'bucket': bucket_labels[i], 'count': hist[i], 'pct': round(hist[i]*100/total, 1) if total else 0} for i in range(len(bucket_labels))],
            'by_source': by_source,
            'overall_avg': round(sum(r['sentiment_signed_score'] or 0 for r in rows) / total, 4) if total else 0,
            'overall_std': round((sum((r['sentiment_signed_score'] or 0 - sum(r['sentiment_signed_score'] or 0 for r in rows)/total)**2 for r in rows)/total)**0.5, 4) if total > 1 else 0,
        }))
    except Exception as e:
        return jsonify(*error_response('DIST_ERROR', str(e), 500))


# ── Gemini Leaderboard ────────────────────────────────────────────────────────

GEMINI_SENTIMENT_PROMPT = """You are a financial sentiment analyst specializing in stock-specific sentiment.

Read the posts below about {ticker} and assess: how do people feel about {ticker} AS AN INVESTMENT?

Important rules:
- A post can be negative in tone (e.g. "markets are scary") but BULLISH on {ticker} (e.g. "but {ticker} will outperform") — score it positive
- A post can be positive in tone but BEARISH on {ticker} — score it negative
- Only score sentiment that is DIRECTLY about {ticker}'s stock, business, or investment prospects
- Ignore general market/macro sentiment unless the author links it to {ticker} specifically

Score from -1.0 (extremely bearish on {ticker}) to +1.0 (extremely bullish on {ticker}), 0.0 = neutral.

Posts:
{posts}

Reply with only this JSON (no markdown, no explanation outside the JSON):
{{"score": 0.35, "label": "bullish", "reason": "max 8 words why"}}
label must be: bullish, neutral, or bearish"""


@app.route('/api/v1/gemini-board', methods=['GET'])
def gemini_board():
    """Leaderboard using Gemini to score sentiment instead of FinBERT."""
    import json as _json
    import re

    if not gemini_api_key:
        return jsonify(*error_response('GEMINI_DISABLED', 'Gemini API key not configured', 503))

    tickers_param = request.args.get('tickers', '')
    days = int(request.args.get('days', 7))
    ticker_list = [t.strip().upper() for t in tickers_param.split(',') if t.strip()]
    if not ticker_list:
        ticker_list = ['NVDA', 'AAPL', 'MSFT', 'GOOG', 'AMZN', 'META', 'TSLA', 'AVGO', 'TXN', 'COHR', 'INTC', 'ASML', 'SNDK']

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%S')
    results = []

    for ticker in ticker_list:
        try:
            # Fetch recent posts for this ticker from DB
            with db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT p.title, p.text, p.source, p.sentiment_signed_score
                    FROM posts p
                    JOIN post_tickers pt ON p.id = pt.post_id
                    JOIN tickers t ON pt.ticker_id = t.id
                    WHERE t.symbol = ? AND p.created_at >= ?
                    ORDER BY p.created_at DESC
                    LIMIT 30
                ''', (ticker, cutoff))
                rows = cursor.fetchall()

            if not rows:
                results.append({
                    'ticker': ticker, 'score': None, 'label': 'no_data',
                    'reason': 'No posts found', 'total_posts': 0,
                    'finbert_score': None,
                })
                continue

            # Build post text for Gemini
            post_lines = []
            finbert_scores = []
            for r in rows:
                title = (r['title'] or '').strip()
                text = (r['text'] or '').strip()[:200]
                content = title if title else text
                if content:
                    src = r['source'] or 'reddit'
                    post_lines.append(f"[{src}] {content}")
                if r['sentiment_signed_score'] is not None:
                    finbert_scores.append(r['sentiment_signed_score'])

            posts_text = '\n'.join(post_lines[:25])
            finbert_avg = round(sum(finbert_scores) / len(finbert_scores), 4) if finbert_scores else None

            # Call Gemini
            prompt = GEMINI_SENTIMENT_PROMPT.format(ticker=ticker, posts=posts_text)
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.1,
                    "maxOutputTokens": 1024
                }
            }
            resp = requests.post(url, json=payload, timeout=30)
            resp.raise_for_status()
            raw = resp.json()['candidates'][0]['content']['parts'][0]['text'].strip()
            print(f"[GeminiBoard] {ticker} raw: {raw[:400]}")

            # Strip markdown code fences then parse JSON
            cleaned = re.sub(r'```(?:json)?', '', raw).strip('` \n')
            match = re.search(r'\{.*\}', cleaned, re.DOTALL)
            try:
                parsed = _json.loads(match.group()) if match else {}
            except Exception:
                parsed = {}

            score = float(parsed.get('score', 0))
            score = max(-1.0, min(1.0, score))  # clamp
            label = parsed.get('label', 'neutral')
            reason = parsed.get('reason', '')

            results.append({
                'ticker': ticker,
                'score': round(score, 4),
                'label': label,
                'reason': reason,
                'total_posts': len(rows),
                'finbert_score': finbert_avg,
            })

        except Exception as e:
            results.append({
                'ticker': ticker, 'score': None, 'label': 'no_data',
                'reason': str(e), 'total_posts': 0, 'finbert_score': None,
            })

    # Sort by score descending
    results.sort(key=lambda x: (x['score'] is not None, x['score'] or 0), reverse=True)
    return jsonify(success_response({'board': results, 'days': days}))


# ── AI Agent Endpoints ────────────────────────────────────────────────────────

@app.route('/api/v1/agent/brief', methods=['GET'])
def agent_brief():
    """Auto-generate a market brief using the AI agent"""
    if not agent_service:
        return jsonify(*error_response('AGENT_DISABLED', 'AI Agent is not configured', 503))
    try:
        brief = agent_service.get_brief()
        return jsonify(success_response({'brief': brief}))
    except Exception as e:
        return jsonify(*error_response('AGENT_ERROR', str(e), 500))

@app.route('/api/v1/agent/stock-analysis', methods=['GET'])
def agent_stock_analysis():
    """Generate a full AI analysis for a specific stock"""
    if not agent_service:
        return jsonify(*error_response('AGENT_DISABLED', 'AI Agent is not configured', 503))
    ticker = request.args.get('ticker', '').upper().strip()
    days_param = int(request.args.get('days', 7))
    if not ticker:
        return jsonify(*error_response('INVALID_PARAM', 'ticker parameter required'))
    try:
        analysis = agent_service.get_stock_analysis(ticker, days=days_param)
        return jsonify(success_response({'ticker': ticker, 'analysis': analysis}))
    except Exception as e:
        return jsonify(*error_response('AGENT_ERROR', str(e), 500))

@app.route('/api/v1/agent/db-analysis', methods=['POST'])
def agent_db_analysis():
    """Deep analysis of DB data for a given time period or custom question."""
    if not agent_service:
        return jsonify(*error_response('AGENT_DISABLED', 'AI Agent is not configured', 503))
    try:
        body = request.get_json() or {}
        period = body.get('period', '7days')
        question = body.get('question', '').strip()
        history = body.get('history', [])
        ticker = (body.get('ticker', '') or '').upper().strip()

        period_map = {'today': 1, 'yesterday': 2, '3days': 3, '7days': 7, '30days': 30, 'week': 7, 'month': 30}
        days = period_map.get(period, 7)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%S')

        with db._get_connection() as conn:
            cursor = conn.cursor()

            if ticker:
                # Ticker-specific queries
                cursor.execute('''
                    SELECT DATE(p.created_at) as day,
                        COUNT(*) as total,
                        SUM(CASE WHEN p.sentiment_label='positive' THEN 1 ELSE 0 END) as pos,
                        SUM(CASE WHEN p.sentiment_label='negative' THEN 1 ELSE 0 END) as neg,
                        AVG(p.sentiment_signed_score) as avg_score
                    FROM posts p
                    JOIN post_tickers pt ON p.id = pt.post_id
                    JOIN tickers t ON pt.ticker_id = t.id
                    WHERE t.symbol = ? AND p.created_at >= ?
                    GROUP BY day ORDER BY day DESC
                ''', (ticker, cutoff))
                daily = [dict(r) for r in cursor.fetchall()]

                cursor.execute('''
                    SELECT p.title, p.text, p.source, p.sentiment_label, p.sentiment_signed_score, p.created_at
                    FROM posts p
                    JOIN post_tickers pt ON p.id = pt.post_id
                    JOIN tickers t ON pt.ticker_id = t.id
                    WHERE t.symbol = ? AND p.created_at >= ?
                    ORDER BY ABS(p.sentiment_signed_score) DESC LIMIT 40
                ''', (ticker, cutoff))
                cursor2_rows = cursor.fetchall()

                cursor.execute('''
                    SELECT p.source, COUNT(*) as count, AVG(p.sentiment_signed_score) as avg_score
                    FROM posts p
                    JOIN post_tickers pt ON p.id = pt.post_id
                    JOIN tickers t ON pt.ticker_id = t.id
                    WHERE t.symbol = ? AND p.created_at >= ?
                    GROUP BY p.source ORDER BY count DESC
                ''', (ticker, cutoff))
                by_source = [dict(r) for r in cursor.fetchall()]
                top_tickers = []
            else:
                # Market-wide queries
                cursor.execute('''
                    SELECT DATE(created_at) as day,
                        COUNT(*) as total,
                        SUM(CASE WHEN sentiment_label='positive' THEN 1 ELSE 0 END) as pos,
                        SUM(CASE WHEN sentiment_label='negative' THEN 1 ELSE 0 END) as neg,
                        AVG(sentiment_signed_score) as avg_score
                    FROM posts WHERE created_at >= ?
                    GROUP BY day ORDER BY day DESC
                ''', (cutoff,))
                daily = [dict(r) for r in cursor.fetchall()]

                cursor.execute('''
                    SELECT t.symbol,
                        COUNT(DISTINCT p.id) as posts,
                        AVG(p.sentiment_signed_score) as avg_score
                    FROM tickers t
                    JOIN post_tickers pt ON t.id = pt.ticker_id
                    JOIN posts p ON pt.post_id = p.id
                    WHERE p.created_at >= ?
                    GROUP BY t.symbol
                    ORDER BY posts DESC LIMIT 15
                ''', (cutoff,))
                top_tickers = [dict(r) for r in cursor.fetchall()]

                cursor.execute('''
                    SELECT title, text, source, sentiment_label, sentiment_signed_score, created_at
                    FROM posts WHERE created_at >= ?
                    ORDER BY ABS(sentiment_signed_score) DESC LIMIT 40
                ''', (cutoff,))
                cursor2_rows = cursor.fetchall()

                cursor.execute('''
                    SELECT source, COUNT(*) as count, AVG(sentiment_signed_score) as avg_score
                    FROM posts WHERE created_at >= ?
                    GROUP BY source ORDER BY count DESC
                ''', (cutoff,))
                by_source = [dict(r) for r in cursor.fetchall()]

            sample_posts = []
            for r in cursor2_rows:
                title = (r['title'] or '').strip()
                text = (r['text'] or '').strip()[:120]
                content = title if title else text
                if content:
                    sample_posts.append({
                        'content': content,
                        'source': r['source'],
                        'sentiment': r['sentiment_label'],
                        'score': round(r['sentiment_signed_score'] or 0, 3),
                        'date': str(r['created_at'])[:10]
                    })

            total_posts = sum(d['total'] for d in daily)

        period_label = {'today': '1天', 'yesterday': '2天', '3days': '3天', '7days': '7天', '30days': '30天', 'week': '7天', 'month': '30天'}.get(period, period)
        subject = f"{ticker} 股票" if ticker else "整体市场"

        db_context = {
            'subject': subject,
            'period': period_label,
            'total_posts_in_db': total_posts,
            'daily_trend': daily,
            'source_breakdown': by_source,
            'most_impactful_posts_sample': sample_posts,
        }
        if not ticker:
            db_context['top_tickers'] = top_tickers

        has_data = total_posts > 0

        db_summary = f"数据库数据（{subject}，{period_label}，共{total_posts}条帖子）：\n{json.dumps(db_context, ensure_ascii=False, indent=2, default=str)}"

        if question:
            # Follow-up: focused answer to specific question
            prompt = f"""你是一位专业金融情感分析师。以下是数据库数据供参考：

{db_summary}

用户问题：{question}

请直接回答这个问题。如果数据库没有足够信息，结合你的市场知识补充。回答要具体、简洁。
⚠️ 不构成投资建议。"""
        else:
            # Initial analysis: full structured report
            prompt = f"""你是一位专业金融情感分析师。以下是从本地数据库提取的{period_label} {subject}社交媒体和新闻数据：

{db_summary}

{"请基于以上数据做详细分析。" if has_data else f"数据库中该时间段内帖子数量不足（仅{total_posts}条），数据库分析受限，请结合你的市场知识补充。"}

请按以下结构回答：

**1. 整体情感概况**
- 该时间段内整体情绪：偏多/偏空/中性？给出数据支撑
- 每天情绪变化趋势，哪天最活跃/最极端？

**2. 热点话题**
{"- 讨论量最高的股票是哪些？情绪如何？" if not ticker else f"- 关于 {ticker} 帖子在讨论什么主题？"}
- 从帖子内容可以看出，最近在关注什么主题？（如：AI、关税、财报、宏观等）

**3. 情绪波动分析**
- 是否有某天情绪出现明显异常？可能的原因是什么？
- 最强烈的正面/负面内容在讲什么？

**4. 来源分析**
- 不同来源（Reddit/新闻/StockTwits）的情绪倾向有差异吗？

**5. 总结与补充**
- {"基于以上数据库数据，给出你的核心判断。" if has_data else "数据库数据不足，"}结合你自身的市场知识，补充该时间段内实际发生的重要事件、新闻、宏观因素。
- 最终给出综合判断。

⚠️ 数据来源：本地社交媒体情感数据库 + AI市场知识库。不构成投资建议。"""

        # Build conversation for Gemini directly (don't use agent_service.chat which rebuilds context)
        contents = []
        for msg in history:
            role = 'user' if msg['role'] == 'user' else 'model'
            contents.append({'role': role, 'parts': [{'text': msg['content']}]})
        contents.append({'role': 'user', 'parts': [{'text': prompt}]})

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_api_key}"
        payload = {
            'contents': contents,
            'generationConfig': {'temperature': 0.7, 'maxOutputTokens': 8192}
        }
        resp = requests.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        response_text = resp.json()['candidates'][0]['content']['parts'][0]['text']

        updated_history = history + [
            {'role': 'user', 'content': question if question else f'分析{period_label}{subject}数据'},
            {'role': 'assistant', 'content': response_text}
        ]

        return jsonify(success_response({
            'response': response_text,
            'history': updated_history,
            'db_stats': {'total_posts': total_posts, 'days': days, 'period': period_label}
        }))
    except Exception as e:
        return jsonify(*error_response('AGENT_ERROR', str(e), 500))


@app.route('/api/v1/agent/chat', methods=['POST'])
def agent_chat():
    """Chat with the AI agent"""
    if not agent_service:
        return jsonify(*error_response('AGENT_DISABLED', 'AI Agent is not configured', 503))
    try:
        body = request.get_json() or {}
        user_message = body.get('message', '').strip()
        history = body.get('history', [])

        if not user_message:
            return jsonify(*error_response('INVALID_PARAM', 'message is required'))

        response_text, updated_history = agent_service.chat(user_message, history)
        return jsonify(success_response({
            'response': response_text,
            'history': updated_history
        }))
    except Exception as e:
        return jsonify(*error_response('AGENT_ERROR', str(e), 500))

@app.route('/api/v1/ticker-board', methods=['GET'])
def get_ticker_board():
    """Get sentiment summary for a list of tickers, sorted by score."""
    try:
        tickers_param = request.args.get('tickers', '')
        days = int(request.args.get('days', 30))
        if not tickers_param:
            return jsonify(*error_response('INVALID_PARAM', 'tickers parameter required'))

        tickers = [t.strip().upper() for t in tickers_param.split(',') if t.strip()]
        board = []

        for ticker in tickers:
            trends = db.analytics.get_sentiment_trends(days=days, ticker=ticker)
            total_pos = sum(t.get('positive', 0) for t in trends)
            total_neg = sum(t.get('negative', 0) for t in trends)
            total_neu = sum(t.get('neutral', 0) for t in trends)
            total = total_pos + total_neg + total_neu

            score = round(sum(t.get('avg_signed_score', 0) * (t.get('positive',0)+t.get('negative',0)+t.get('neutral',0)) for t in trends) / total, 3) if total > 0 else None
            if score is None:
                label = 'no_data'
            elif score > 0.1:
                label = 'bullish'
            elif score < -0.1:
                label = 'bearish'
            else:
                label = 'neutral'

            # Get company info from industry_classifier
            info = industry_classifier.get_ticker_info(ticker) or {}

            board.append({
                'ticker': ticker,
                'company': info.get('company', ticker),
                'sector': info.get('sector', ''),
                'total_posts': total,
                'positive': total_pos,
                'negative': total_neg,
                'neutral': total_neu,
                'score': score,
                'label': label,
            })

        # Sort: bullish first (highest score), no_data last
        board.sort(key=lambda x: (x['score'] is None, -(x['score'] or 0)))
        return jsonify(success_response({'board': board, 'days': days}))
    except Exception as e:
        return jsonify(*error_response('BOARD_ERROR', str(e), 500))

@app.route('/api/v1/ai-ticker-board', methods=['GET'])
def ai_ticker_board():
    """Leaderboard using Gemini ai_sentiment_score stored in DB."""
    tickers_param = request.args.get('tickers', '')
    days = int(request.args.get('days', 7))
    ticker_list = [t.strip().upper() for t in tickers_param.split(',') if t.strip()]
    if not ticker_list:
        ticker_list = ['NVDA', 'AAPL', 'MSFT', 'GOOG', 'AMZN', 'META', 'TSLA', 'AVGO', 'TXN', 'COHR', 'INTC', 'ASML', 'SNDK']

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%S')

    board = []
    try:
        with db._get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ','.join('?' * len(ticker_list))
            cursor.execute(f'''
                SELECT t.symbol,
                    COUNT(DISTINCT p.id) as total_posts,
                    COUNT(DISTINCT CASE WHEN p.ai_sentiment_score IS NOT NULL THEN p.id END) as ai_scored,
                    AVG(p.ai_sentiment_score) as avg_ai_score,
                    AVG(p.sentiment_signed_score) as avg_finbert_score
                FROM tickers t
                JOIN post_tickers pt ON t.id = pt.ticker_id
                JOIN posts p ON pt.post_id = p.id
                WHERE t.symbol IN ({placeholders}) AND p.created_at >= ?
                GROUP BY t.symbol
            ''', ticker_list + [cutoff])

            rows = cursor.fetchall()
            ticker_data = {r['symbol']: r for r in rows}

        for ticker in ticker_list:
            r = ticker_data.get(ticker)
            if not r or r['ai_scored'] == 0:
                board.append({
                    'ticker': ticker,
                    'score': None,
                    'label': 'no_data',
                    'total_posts': r['total_posts'] if r else 0,
                    'ai_scored_posts': 0,
                    'finbert_score': round(r['avg_finbert_score'], 4) if r and r['avg_finbert_score'] is not None else None,
                })
                continue

            score = round(r['avg_ai_score'], 4)
            label = 'bullish' if score > 0.1 else ('bearish' if score < -0.1 else 'neutral')
            board.append({
                'ticker': ticker,
                'score': score,
                'label': label,
                'total_posts': r['total_posts'],
                'ai_scored_posts': r['ai_scored'],
                'finbert_score': round(r['avg_finbert_score'], 4) if r['avg_finbert_score'] is not None else None,
            })

        board.sort(key=lambda x: (x['score'] is not None, x['score'] or 0), reverse=True)
        return jsonify(success_response({'board': board, 'days': days}))
    except Exception as e:
        return jsonify(*error_response('AI_BOARD_ERROR', str(e), 500))

# Serve React App (SPA catch-all route)
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_spa(path):
    """Serve React SPA - catch all route for frontend"""
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', config.get('server', {}).get('port', 5000)))
    debug = os.environ.get('FLASK_DEBUG', str(config.get('server', {}).get('debug', False))).lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
