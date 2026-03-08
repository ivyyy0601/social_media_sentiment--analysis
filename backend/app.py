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
from api_utils import (
    success_response, error_response, paginated_response,
    validate_pagination_params, validate_date_param, validate_enum_param
)
import os
import json
from datetime import datetime

# Configure Flask to serve static files from frontend build
static_folder = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'dist')
app = Flask(__name__, static_folder=static_folder, static_url_path='')

# Load configuration
def load_config():
    try:
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        with open(config_path, 'r') as f:
            return json.load(f)
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
db = Database()
ticker_extractor = TickerExtractor()
industry_classifier = IndustryClassifier()
stock_data_provider = StockDataProvider()
price_data_provider = PriceDataProvider()
export_service = ExportService()
watchlist_repo = WatchlistRepository()

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
        posts = reddit_client.fetch_posts(query, max_results, start_date, end_date)
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