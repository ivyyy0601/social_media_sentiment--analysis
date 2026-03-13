import sqlite3
import json
from datetime import datetime, timedelta
from contextlib import contextmanager


class Database:
    """Main database class that coordinates all repositories"""
    
    def __init__(self, db_path='finance_sentiment.db'):
        """
        Initialize database connection
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        
        # Initialize repositories
        self.posts = PostRepository(db_path)
        self.tickers = TickerRepository(db_path)
        self.industries = IndustryRepository(db_path)
        self.analytics = AnalyticsRepository(db_path)
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    # Legacy methods for backward compatibility
    def save_post(self, post_data):
        """Legacy method - delegates to PostRepository"""
        return self.posts.save_post(post_data)
    
    def get_recent_posts(self, limit=50):
        """Legacy method - delegates to PostRepository"""
        return self.posts.get_recent_posts(limit)
    
    def get_sentiment_stats(self):
        """Legacy method - delegates to AnalyticsRepository"""
        return self.analytics.get_sentiment_stats()
    
    def get_sentiment_trends(self, days=7):
        """Legacy method - delegates to AnalyticsRepository"""
        return self.analytics.get_sentiment_trends(days)


class PostRepository:
    """Repository for post CRUD operations"""
    
    def __init__(self, db_path='finance_sentiment.db'):
        self.db_path = db_path
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def save_post(self, post_data):
        """
        Save analyzed post to database with all metadata
        
        Args:
            post_data: Dictionary with post data and sentiment
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Extract Reddit ID from post ID if available
            reddit_id = post_data.get('reddit_id', post_data.get('id', '').replace('reddit_', ''))
            
            cursor.execute('''
                INSERT OR REPLACE INTO posts
                (id, reddit_id, url, subreddit, title, text, author, created_at, timezone,
                sentiment_label, sentiment_score, sentiment_scores, sentiment_signed_score, analyzed_at, source, ai_sentiment_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                post_data['id'],
                reddit_id,
                post_data.get('url', post_data.get('link', '')),
                post_data.get('subreddit', ''),
                post_data.get('title', ''),
                post_data['text'],
                post_data.get('author', post_data.get('author_id', 'unknown')),
                post_data['created_at'],
                post_data.get('timezone', 'UTC'),
                post_data['sentiment']['label'],
                post_data['sentiment']['score'],
                json.dumps(post_data['sentiment']['scores']),
                post_data['sentiment'].get('signed_score', 0.0),
                datetime.utcnow().isoformat(),
                post_data.get('source', ''),
                post_data.get('ai_sentiment_score')
            ))

            
            return post_data['id']

    def exists(self, post_id):
        """Return True if a post with this ID is already in the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM posts WHERE id = ? LIMIT 1', (post_id,))
            return cursor.fetchone() is not None

    def update_ai_score(self, post_id, score):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE posts SET ai_sentiment_score = ? WHERE id = ?',
                (score, post_id)
            )

    def get_recent_posts(self, limit=50, offset=0):
        """
        Get recent analyzed posts
        
        Args:
            limit: Maximum number of posts to return
            offset: Number of posts to skip (for pagination)
            
        Returns:
            List of post dictionaries
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, reddit_id, url, subreddit, title, text, author, 
                       created_at, timezone, sentiment_label, sentiment_score, 
                       sentiment_scores, analyzed_at
                FROM posts
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            ''', (limit, offset))
            
            return [self._row_to_post(row) for row in cursor.fetchall()]
    
    def get_posts_filtered(self, ticker=None, industry=None, sector=None, 
                          sentiment=None, start_date=None, end_date=None,
                          limit=50, offset=0):
        """
        Get posts with advanced filtering
        
        Args:
            ticker: Filter by ticker symbol
            industry: Filter by industry name
            sector: Filter by sector name
            sentiment: Filter by sentiment label
            start_date: Filter by start date (ISO format)
            end_date: Filter by end date (ISO format)
            limit: Maximum number of posts to return
            offset: Number of posts to skip
            
        Returns:
            List of post dictionaries
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Build query dynamically based on filters
            query = 'SELECT DISTINCT p.* FROM posts p'
            conditions = []
            params = []
            
            # Join with ticker filter
            if ticker:
                query += '''
                    INNER JOIN post_tickers pt ON p.id = pt.post_id
                    INNER JOIN tickers t ON pt.ticker_id = t.id
                '''
                conditions.append('t.symbol = ?')
                params.append(ticker)
            
            # Join with industry filter
            if industry:
                query += '''
                    INNER JOIN post_industries pi ON p.id = pi.post_id
                    INNER JOIN industries i ON pi.industry_id = i.id
                '''
                conditions.append('i.name = ?')
                params.append(industry)
            
            # Join with sector filter
            if sector:
                query += '''
                    INNER JOIN post_sectors ps ON p.id = ps.post_id
                    INNER JOIN sectors s ON ps.sector_id = s.id
                '''
                conditions.append('s.name = ?')
                params.append(sector)
            
            # Add other filters
            if sentiment:
                conditions.append('p.sentiment_label = ?')
                params.append(sentiment)
            
            if start_date:
                conditions.append('p.created_at >= ?')
                params.append(start_date)
            
            if end_date:
                conditions.append('p.created_at <= ?')
                params.append(end_date)
            
            # Add WHERE clause if there are conditions
            if conditions:
                query += ' WHERE ' + ' AND '.join(conditions)
            
            query += ' ORDER BY p.created_at DESC LIMIT ? OFFSET ?'
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            return [self._row_to_post(row) for row in cursor.fetchall()]
    
    def count_posts_filtered(self, ticker=None, industry=None, sector=None,
                            sentiment=None, start_date=None, end_date=None):
        """
        Count posts matching filters
        
        Returns:
            Total count of matching posts
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = 'SELECT COUNT(DISTINCT p.id) as count FROM posts p'
            conditions = []
            params = []
            
            if ticker:
                query += '''
                    INNER JOIN post_tickers pt ON p.id = pt.post_id
                    INNER JOIN tickers t ON pt.ticker_id = t.id
                '''
                conditions.append('t.symbol = ?')
                params.append(ticker)
            
            if industry:
                query += '''
                    INNER JOIN post_industries pi ON p.id = pi.post_id
                    INNER JOIN industries i ON pi.industry_id = i.id
                '''
                conditions.append('i.name = ?')
                params.append(industry)
            
            if sector:
                query += '''
                    INNER JOIN post_sectors ps ON p.id = ps.post_id
                    INNER JOIN sectors s ON ps.sector_id = s.id
                '''
                conditions.append('s.name = ?')
                params.append(sector)
            
            if sentiment:
                conditions.append('p.sentiment_label = ?')
                params.append(sentiment)
            
            if start_date:
                conditions.append('p.created_at >= ?')
                params.append(start_date)
            
            if end_date:
                conditions.append('p.created_at <= ?')
                params.append(end_date)
            
            if conditions:
                query += ' WHERE ' + ' AND '.join(conditions)
            
            cursor.execute(query, params)
            result = cursor.fetchone()
            return result['count'] if result else 0
    
    def get_post_by_id(self, post_id):
        """Get a single post by ID"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, reddit_id, url, subreddit, title, text, author,
                       created_at, timezone, sentiment_label, sentiment_score,
                       sentiment_scores, analyzed_at
                FROM posts WHERE id = ?
            ''', (post_id,))
            
            row = cursor.fetchone()
            return self._row_to_post(row) if row else None
    
    def _row_to_post(self, row):
        """Convert database row to post dictionary"""
        try:
            ai_score = row['ai_sentiment_score']
        except (IndexError, KeyError):
            ai_score = None
        return {
            'id': row['id'],
            'reddit_id': row['reddit_id'],
            'url': row['url'],
            'subreddit': row['subreddit'],
            'title': row['title'],
            'text': row['text'],
            'author': row['author'],
            'created_at': row['created_at'],
            'timezone': row['timezone'],
            'sentiment': {
                'label': row['sentiment_label'],
                'score': row['sentiment_score'],
                'signed_score': row['sentiment_signed_score'],  # ⭐新增
                'scores': json.loads(row['sentiment_scores']) if row['sentiment_scores'] else {}
            },
            'analyzed_at': row['analyzed_at'],
            'ai_sentiment_score': ai_score
        }


class TickerRepository:
    """Repository for ticker operations"""
    
    def __init__(self, db_path='finance_sentiment.db'):
        self.db_path = db_path
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def save_ticker(self, symbol, company_name=None, sector=None, industry=None):
        """
        Save or update ticker information
        
        Args:
            symbol: Ticker symbol
            company_name: Company name
            sector: Sector name
            industry: Industry name
            
        Returns:
            Ticker ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Get or create sector
            sector_id = None
            if sector:
                cursor.execute('INSERT OR IGNORE INTO sectors (name) VALUES (?)', (sector,))
                cursor.execute('SELECT id FROM sectors WHERE name = ?', (sector,))
                sector_id = cursor.fetchone()['id']
            
            # Get or create industry
            industry_id = None
            if industry:
                cursor.execute('INSERT OR IGNORE INTO industries (name) VALUES (?)', (industry,))
                cursor.execute('SELECT id FROM industries WHERE name = ?', (industry,))
                industry_id = cursor.fetchone()['id']
            
            # Insert or update ticker
            cursor.execute('''
                INSERT INTO tickers (symbol, company_name, sector_id, industry_id)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    company_name = excluded.company_name,
                    sector_id = excluded.sector_id,
                    industry_id = excluded.industry_id
            ''', (symbol, company_name, sector_id, industry_id))
            
            # Get ticker ID
            cursor.execute('SELECT id FROM tickers WHERE symbol = ?', (symbol,))
            return cursor.fetchone()['id']
    
    def link_post_to_tickers(self, post_id, ticker_symbols):
        """
        Link a post to multiple tickers
        
        Args:
            post_id: Post ID
            ticker_symbols: List of ticker symbols
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Clear existing links
            cursor.execute('DELETE FROM post_tickers WHERE post_id = ?', (post_id,))
            
            for symbol in ticker_symbols:
                # Get ticker ID
                cursor.execute('SELECT id FROM tickers WHERE symbol = ?', (symbol,))
                result = cursor.fetchone()
                
                if result:
                    ticker_id = result['id']
                    
                    # Create link
                    cursor.execute('''
                        INSERT OR IGNORE INTO post_tickers (post_id, ticker_id)
                        VALUES (?, ?)
                    ''', (post_id, ticker_id))
    
    def link_post_to_industries_and_sectors(self, post_id, industries, sectors):
        """
        Link a post to industries and sectors
        
        Args:
            post_id: Post ID
            industries: List of industry names
            sectors: List of sector names
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Clear existing links
            cursor.execute('DELETE FROM post_industries WHERE post_id = ?', (post_id,))
            cursor.execute('DELETE FROM post_sectors WHERE post_id = ?', (post_id,))
            
            # Link industries
            for industry in industries:
                cursor.execute('SELECT id FROM industries WHERE name = ?', (industry,))
                result = cursor.fetchone()
                if result:
                    cursor.execute('''
                        INSERT OR IGNORE INTO post_industries (post_id, industry_id)
                        VALUES (?, ?)
                    ''', (post_id, result['id']))
            
            # Link sectors
            for sector in sectors:
                cursor.execute('SELECT id FROM sectors WHERE name = ?', (sector,))
                result = cursor.fetchone()
                if result:
                    cursor.execute('''
                        INSERT OR IGNORE INTO post_sectors (post_id, sector_id)
                        VALUES (?, ?)
                    ''', (post_id, result['id']))
    
    def get_tickers(self):
        """Get all unique tickers"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT t.symbol, t.company_name, s.name as sector, i.name as industry
                FROM tickers t
                LEFT JOIN sectors s ON t.sector_id = s.id
                LEFT JOIN industries i ON t.industry_id = i.id
                ORDER BY t.symbol
            ''')
            
            return [{
                'symbol': row['symbol'],
                'company_name': row['company_name'],
                'sector': row['sector'],
                'industry': row['industry']
            } for row in cursor.fetchall()]
    
    def get_posts_by_ticker(self, ticker):
        """
        Get all posts mentioning a specific ticker
        
        Args:
            ticker: Ticker symbol
            
        Returns:
            List of post IDs
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT p.id
                FROM posts p
                INNER JOIN post_tickers pt ON p.id = pt.post_id
                INNER JOIN tickers t ON pt.ticker_id = t.id
                WHERE t.symbol = ?
                ORDER BY p.created_at DESC
            ''', (ticker,))
            
            return [row['id'] for row in cursor.fetchall()]


class IndustryRepository:
    """Repository for industry and sector operations"""
    
    def __init__(self, db_path='finance_sentiment.db'):
        self.db_path = db_path
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def get_industries(self):
        """Get all unique industries"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, name FROM industries ORDER BY name')
            return [{'id': row['id'], 'name': row['name']} for row in cursor.fetchall()]
    
    def get_sectors(self):
        """Get all unique sectors"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, name FROM sectors ORDER BY name')
            return [{'id': row['id'], 'name': row['name']} for row in cursor.fetchall()]


class AnalyticsRepository:
    """Repository for analytics and aggregation queries"""
    
    def __init__(self, db_path='finance_sentiment.db'):
        self.db_path = db_path
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def get_sentiment_stats(self, ticker=None, industry=None, sector=None,
                           start_date=None, end_date=None):
        """
        Get sentiment statistics with optional filtering
        
        Returns:
            Dictionary with sentiment counts and percentages
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = 'SELECT sentiment_label, COUNT(*) as count FROM posts p'
            conditions = []
            params = []
            
            if ticker:
                query += '''
                    INNER JOIN post_tickers pt ON p.id = pt.post_id
                    INNER JOIN tickers t ON pt.ticker_id = t.id
                '''
                conditions.append('t.symbol = ?')
                params.append(ticker)
            
            if industry:
                query += '''
                    INNER JOIN post_industries pi ON p.id = pi.post_id
                    INNER JOIN industries i ON pi.industry_id = i.id
                '''
                conditions.append('i.name = ?')
                params.append(industry)
            
            if sector:
                query += '''
                    INNER JOIN post_sectors ps ON p.id = ps.post_id
                    INNER JOIN sectors s ON ps.sector_id = s.id
                '''
                conditions.append('s.name = ?')
                params.append(sector)
            
            if start_date:
                conditions.append('p.created_at >= ?')
                params.append(start_date)
            
            if end_date:
                conditions.append('p.created_at <= ?')
                params.append(end_date)
            
            if conditions:
                query += ' WHERE ' + ' AND '.join(conditions)
            
            query += ' GROUP BY sentiment_label'
            
            cursor.execute(query, params)
            
            stats = {'total': 0, 'by_sentiment': {}}
            for row in cursor.fetchall():
                label = row['sentiment_label']
                count = row['count']
                stats['by_sentiment'][label] = count
                stats['total'] += count
            
            # Calculate percentages
            if stats['total'] > 0:
                for label in stats['by_sentiment']:
                    count = stats['by_sentiment'][label]
                    stats['by_sentiment'][label] = {
                        'count': count,
                        'percentage': round((count / stats['total']) * 100, 2)
                    }
            
            return stats
    
    def get_sentiment_trends(self, days=7, ticker=None, industry=None, sector=None,
                            start_date=None, end_date=None, granularity='day'):
        """
        Get sentiment trends over time
        
        Args:
            days: Number of days to include (ignored if start_date is provided)
            ticker: Filter by ticker
            industry: Filter by industry
            sector: Filter by sector
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            granularity: 'day' or 'week'
            
        Returns:
            List of daily or weekly sentiment counts
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Determine date format based on granularity
            if granularity == 'week':
                date_format = "strftime('%Y-W%W', created_at)"
            else:
                date_format = "DATE(created_at)"
            
            query = f'''
                SELECT {date_format} as date, sentiment_label, COUNT(*) as count,
                       AVG(sentiment_signed_score) as avg_signed
                FROM posts p
            '''
            
            conditions = []
            params = []
            
            if ticker:
                query += '''
                    INNER JOIN post_tickers pt ON p.id = pt.post_id
                    INNER JOIN tickers t ON pt.ticker_id = t.id
                '''
                conditions.append('t.symbol = ?')
                params.append(ticker)
            
            if industry:
                query += '''
                    INNER JOIN post_industries pi ON p.id = pi.post_id
                    INNER JOIN industries i ON pi.industry_id = i.id
                '''
                conditions.append('i.name = ?')
                params.append(industry)
            
            if sector:
                query += '''
                    INNER JOIN post_sectors ps ON p.id = ps.post_id
                    INNER JOIN sectors s ON ps.sector_id = s.id
                '''
                conditions.append('s.name = ?')
                params.append(sector)
            
            if start_date:
                conditions.append('p.created_at >= ?')
                params.append(start_date)
            elif not end_date:
                # Use days parameter if no date range specified
                from datetime import timezone as _tz
                cutoff_date = (datetime.now(_tz.utc) - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%S')
                conditions.append('p.created_at >= ?')
                params.append(cutoff_date)
            
            if end_date:
                conditions.append('p.created_at <= ?')
                params.append(end_date)
            
            if conditions:
                query += ' WHERE ' + ' AND '.join(conditions)
            
            query += ' GROUP BY date, sentiment_label ORDER BY date DESC'
            
            cursor.execute(query, params)
            
            trends = {}
            for row in cursor.fetchall():
                date = row['date']
                label = row['sentiment_label']
                count = row['count']
                avg_signed = row['avg_signed'] or 0.0

                if date not in trends:
                    trends[date] = {
                        'date': date, 'positive': 0, 'negative': 0, 'neutral': 0,
                        '_signed_sum': 0.0, '_total': 0
                    }

                trends[date][label] = count
                trends[date]['_signed_sum'] += avg_signed * count
                trends[date]['_total'] += count

            # Add avg_signed_score per day and clean up temp fields
            result = []
            for d in trends.values():
                total = d.pop('_total', 0)
                signed_sum = d.pop('_signed_sum', 0.0)
                d['avg_signed_score'] = round(signed_sum / total, 4) if total > 0 else 0.0
                result.append(d)
            return result
        
    def get_market_pulse(self, start_date=None, end_date=None, min_posts=3):
        """
        Get market pulse data (most discussed, most positive/negative stocks, etc.)

        Notes:
        - sentiment_signed_score: direction score in [-1, 1] (positive - negative)
        - sentiment_score: confidence (max prob). We DON'T use it for direction ranking.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Build date filter conditions and params
            where_conditions = ['1=1']
            params = []

            if start_date:
                where_conditions.append('p.created_at >= ?')
                params.append(start_date)

            if end_date:
                where_conditions.append('p.created_at <= ?')
                params.append(end_date)

            where_clause = ' AND '.join(where_conditions)

            # -----------------------------
            # 1) Most discussed stocks
            # -----------------------------
            cursor.execute(f'''
                SELECT
                    t.symbol,
                    COUNT(DISTINCT p.id) AS post_count,
                    AVG(p.sentiment_signed_score) AS avg_sentiment_score
                FROM tickers t
                INNER JOIN post_tickers pt ON t.id = pt.ticker_id
                INNER JOIN posts p ON pt.post_id = p.id
                WHERE {where_clause}
                AND p.sentiment_signed_score IS NOT NULL
                GROUP BY t.symbol
                ORDER BY post_count DESC
                LIMIT 10
            ''', params)

            most_discussed = [{
                'ticker': row['symbol'],
                'post_count': row['post_count'],
                'avg_sentiment_score': round(row['avg_sentiment_score'], 2) if row['avg_sentiment_score'] is not None else None
            } for row in cursor.fetchall()]

            # -----------------------------
            # 2) Most positive stocks
            #   - rank by avg signed score desc
            #   - require at least min_posts
            # -----------------------------
            cursor.execute(f'''
                SELECT
                    t.symbol,
                    AVG(p.sentiment_signed_score) AS avg_sentiment,
                    COUNT(DISTINCT p.id) AS post_count
                FROM tickers t
                INNER JOIN post_tickers pt ON t.id = pt.ticker_id
                INNER JOIN posts p ON pt.post_id = p.id
                WHERE {where_clause}
                AND p.sentiment_signed_score IS NOT NULL
                GROUP BY t.symbol
                HAVING  COUNT(DISTINCT p.id) >= ?
                ORDER BY avg_sentiment DESC
                LIMIT 10
            ''', params + [min_posts])

            most_positive = [{
                'ticker': row['symbol'],
                'avg_sentiment': round(row['avg_sentiment'], 2) if row['avg_sentiment'] is not None else None,
                'post_count': row['post_count']
            } for row in cursor.fetchall()]

            # -----------------------------
            # 3) Most negative stocks
            #   - rank by avg signed score asc
            #   - require at least min_posts
            # -----------------------------
            cursor.execute(f'''
                SELECT
                    t.symbol,
                    AVG(p.sentiment_signed_score) AS avg_sentiment,
                    COUNT(DISTINCT p.id) AS post_count
                FROM tickers t
                INNER JOIN post_tickers pt ON t.id = pt.ticker_id
                INNER JOIN posts p ON pt.post_id = p.id
                WHERE {where_clause}
                AND p.sentiment_signed_score IS NOT NULL
                GROUP BY t.symbol
                HAVING  COUNT(DISTINCT p.id) >= ?
                ORDER BY avg_sentiment ASC
                LIMIT 10
            ''', params + [min_posts])

            most_negative = [{
                'ticker': row['symbol'],
                'avg_sentiment': round(row['avg_sentiment'], 2) if row['avg_sentiment'] is not None else None,
                'post_count': row['post_count']
            } for row in cursor.fetchall()]

            # -----------------------------
            # 4) Sentiment by sector (counts)
            #   这块你原来是按 sentiment_label 计数，保留
            # -----------------------------
            cursor.execute(f'''
                SELECT s.name AS sector, p.sentiment_label,
                    COUNT(DISTINCT p.id) AS count
                FROM sectors s
                INNER JOIN post_sectors ps ON s.id = ps.sector_id
                INNER JOIN posts p ON ps.post_id = p.id
                WHERE {where_clause}
                GROUP BY s.name, p.sentiment_label
            ''', params)

            sentiment_by_sector = {}
            for row in cursor.fetchall():
                sector = row['sector']
                label = row['sentiment_label']
                count = row['count']

                if sector not in sentiment_by_sector:
                    sentiment_by_sector[sector] = {'positive': 0, 'neutral': 0, 'negative': 0}

                sentiment_by_sector[sector][label] = count

            # -----------------------------
            # 5) Overall market sentiment (direction + distribution)
            #   - average_score 用 signed_score 的平均（方向）
            #   - distribution 还是按 label 计数
            # -----------------------------
            cursor.execute(f'''
                SELECT
                    AVG(p.sentiment_signed_score) AS avg_signed,
                    p.sentiment_label,
                    COUNT(*) AS count
                FROM posts p
                WHERE {where_clause}
                GROUP BY p.sentiment_label
            ''', params)

            overall_sentiment = {
                'average_score': 0,  # 市场方向均值（signed）
                'distribution': {'positive': 0, 'neutral': 0, 'negative': 0}
            }

            total_posts = 0
            weighted_sum = 0

            for row in cursor.fetchall():
                label = row['sentiment_label']
                count = row['count']
                avg_signed = row['avg_signed']  # 该 label 内的 signed_score 平均

                overall_sentiment['distribution'][label] = count
                total_posts += count

                if avg_signed is not None:
                    weighted_sum += avg_signed * count

            if total_posts > 0:
                overall_sentiment['average_score'] = round(weighted_sum / total_posts, 2)

            return {
                'most_discussed_stocks': most_discussed,
                'most_positive_stocks': most_positive,
                'most_negative_stocks': most_negative,
                'sentiment_by_sector': sentiment_by_sector,
                'overall_market_sentiment': overall_sentiment
            }

    def get_sentiment_by_ticker(self, tickers=None, start_date=None, end_date=None):
        """
        Get sentiment breakdown per ticker
        
        Args:
            tickers: List of ticker symbols (None for all)
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            List of ticker sentiment data
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = '''
                SELECT t.symbol, p.sentiment_label, COUNT(*) as count,
                       AVG(p.sentiment_score) as avg_score
                FROM tickers t
                INNER JOIN post_tickers pt ON t.id = pt.ticker_id
                INNER JOIN posts p ON pt.post_id = p.id
                WHERE 1=1
            '''
            
            params = []
            
            if tickers:
                placeholders = ','.join('?' * len(tickers))
                query += f' AND t.symbol IN ({placeholders})'
                params.extend(tickers)
            
            if start_date:
                query += ' AND p.created_at >= ?'
                params.append(start_date)
            
            if end_date:
                query += ' AND p.created_at <= ?'
                params.append(end_date)
            
            query += ' GROUP BY t.symbol, p.sentiment_label ORDER BY t.symbol'
            
            cursor.execute(query, params)
            
            ticker_sentiments = {}
            for row in cursor.fetchall():
                symbol = row['symbol']
                label = row['sentiment_label']
                count = row['count']
                avg_score = row['avg_score']
                
                if symbol not in ticker_sentiments:
                    ticker_sentiments[symbol] = {
                        'ticker': symbol,
                        'sentiments': {'positive': 0, 'neutral': 0, 'negative': 0},
                        'avg_scores': {}
                    }
                
                ticker_sentiments[symbol]['sentiments'][label] = count
                ticker_sentiments[symbol]['avg_scores'][label] = round(avg_score, 2)
            
            return list(ticker_sentiments.values())
