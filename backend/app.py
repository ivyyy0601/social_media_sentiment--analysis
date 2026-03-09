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
from datetime import datetime
from alphavantage_news_client import AlphaVantageNewsClient
from stocktwits_client import StockTwitsClient
from yahoo_finance_news_client import YahooFinanceNewsClient
from google_news_client import GoogleNewsClient
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
stocktwits_client = StockTwitsClient()
yahoo_news_client = YahooFinanceNewsClient()
google_news_client = GoogleNewsClient()

# WhatsApp service
wa_cfg = config.get('whatsapp', {})
whatsapp_service = None
if wa_cfg.get('enabled') and wa_cfg.get('phone') and wa_cfg.get('api_key'):
    whatsapp_service = WhatsAppService(wa_cfg['phone'], wa_cfg['api_key'])
    print(f"[WhatsApp] Notifications enabled → {wa_cfg['phone']}")

# AI Agent (Gemini)
groq_cfg = config.get('groq', {})
groq_api_key = groq_cfg.get('api_key', '')
groq_model = groq_cfg.get('model', 'llama-3.3-70b-versatile')
agent_service = None
if groq_api_key:
    try:
        agent_service = AgentService(db, price_data_provider, groq_api_key, groq_model, stock_data_provider)
        print("AI Agent initialized (Groq)")
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


def _process_and_save_post(post):
    """Analyze sentiment and save a single post to DB."""
    sentiment = sentiment_analyzer.analyze(post['text'])
    post['sentiment'] = sentiment
    post_id = db.posts.save_post(post)
    tickers_found = ticker_extractor.extract_tickers(post['text'])
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
        # StockTwits
        try:
            posts += stocktwits_client.fetch_posts(ticker, limit=30)
        except Exception as e:
            print(f"[Scheduler] StockTwits {ticker}: {e}")
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

        for post in posts:
            try:
                _process_and_save_post(post)
                total_new += 1
            except Exception:
                pass

    _last_auto_fetch = datetime.utcnow().isoformat()
    from datetime import timedelta
    _next_auto_fetch = (
        datetime.utcnow() + timedelta(hours=AUTO_FETCH_INTERVAL_HOURS)
    ).isoformat()
    print(f"[Scheduler] Done — processed {total_new} posts")


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
        'timestamp': datetime.utcnow().isoformat(),
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

        # 3️⃣ StockTwits + Yahoo Finance News（只在 query 像单个 ticker 时才抓）
        q = (query or "").strip().upper()
        is_single_ticker = q.isalnum() and 1 <= len(q) <= 5

        if is_single_ticker:
            # StockTwits
            try:
                st_posts = stocktwits_client.fetch_posts(q, limit=30)
                posts.extend(st_posts)
                print(f"[StockTwits] {len(st_posts)} posts for {q}")
            except Exception as e:
                print(f"[WARN] StockTwits fetch failed: {e}")

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

        analyzed_posts = []


        for post in posts:
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

        return jsonify(success_response({
            'posts': analyzed_posts,
            'count': len(analyzed_posts)
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
        score = round((total_pos - total_neg) / total, 3) if total > 0 else None
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
            tot = pos + neg + neu
            daily_score = round((pos - neg) / tot, 3) if tot > 0 else None
            daily.append({
                'date': t.get('date'),
                'score': daily_score,
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
            stock = yf.Ticker(ticker)
            # 30-day history to match sentiment period
            hist = stock.history(period='35d', interval='1d')
            if not hist.empty and len(hist) >= 2:
                closes = hist['Close'].tolist()
                dates = [str(d.date()) for d in hist.index]
                # 7-day recent window
                price_data['price_7d'] = [
                    {'date': dates[i], 'close': round(closes[i], 2)}
                    for i in range(max(0, len(closes)-7), len(closes))
                ]
                price_data['price_7d_change_pct'] = round((closes[-1] - closes[-8]) / closes[-8] * 100, 2) if len(closes) >= 8 else None
                price_data['trend'] = 'uptrend' if closes[-1] > closes[max(0, len(closes)-8)] else ('downtrend' if closes[-1] < closes[max(0, len(closes)-8)] else 'flat')
                # 30-day change (matches sentiment period)
                price_30d_start = closes[0]
                price_data['price_30d_change_pct'] = round((closes[-1] - price_30d_start) / price_30d_start * 100, 2)
                price_data['price_30d_high'] = round(max(closes), 2)
                price_data['price_30d_low'] = round(min(closes), 2)
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
            posts = db.posts.get_posts_filtered(ticker=ticker, limit=30)
            for p in posts:
                title = (p.get('title') or '').strip()
                text = (p.get('text') or '').strip()
                content = title if title else text[:150]
                if content:
                    recent_posts.append({
                        'content': content[:150],
                        'sentiment': p.get('sentiment_label'),
                        'source': p.get('subreddit', ''),
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

            score = round((total_pos - total_neg) / total, 3) if total > 0 else None
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
