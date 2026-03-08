
"""Database migration system for schema upgrades"""
import sqlite3
import os
from contextlib import contextmanager


class DatabaseMigration:
    """Handle database schema migrations"""

    VERSION_TABLE = 'schema_version'
    CURRENT_VERSION = 3  # Version 3 includes watchlist tables
    
    def __init__(self, db_path='finance_sentiment.db'):
        """
        Initialize migration manager

        Args:
            db_path: Path to SQLite database file
        """
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

    def get_current_version(self):
        """
        Get current schema version from database

        Returns:
            Current version number, or 0 if version table doesn't exist
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Check if version table exists
            cursor.execute('''
                SELECT name FROM sqlite_master
                WHERE type='table' AND name=?
            ''', (self.VERSION_TABLE,))

            if not cursor.fetchone():
                return 0

            cursor.execute(f'SELECT version FROM {self.VERSION_TABLE} LIMIT 1')
            result = cursor.fetchone()
            return result['version'] if result else 0

    def needs_migration(self):
        """
        Check if database needs migration

        Returns:
            True if migration is needed, False otherwise
        """
        return self.get_current_version() < self.CURRENT_VERSION

    def run_migrations(self):
        """
        Run all necessary migrations to bring database to current version
        """
        current_version = self.get_current_version()

        if current_version == 0:
            print("Initializing new database with schema version 3...")
            self._create_v3_schema()
        elif current_version == 1:
            print("Migrating database from version 1 to 3...")
            self._migrate_v1_to_v2()
            self._migrate_v2_to_v3()
        elif current_version == 2:
            print("Migrating database from version 2 to 3...")
            self._migrate_v2_to_v3()
        elif current_version == self.CURRENT_VERSION:
            print("Database is already at current version")
        else:
            raise Exception(f"Unknown database version: {current_version}")

    def _create_v2_schema(self):
        """Create complete version 2 schema from scratch"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Create version table
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS {self.VERSION_TABLE} (
                    version INTEGER NOT NULL
                )
            ''')
            cursor.execute(f'INSERT INTO {self.VERSION_TABLE} (version) VALUES (?)',
                          (self.CURRENT_VERSION,))

            # Create posts table with all fields
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS posts (
                    id TEXT PRIMARY KEY,
                    reddit_id TEXT UNIQUE,
                    url TEXT,
                    subreddit TEXT,
                    title TEXT,
                    text TEXT NOT NULL,
                    author TEXT,
                    created_at TEXT NOT NULL,
                    timezone TEXT,
                    sentiment_label TEXT NOT NULL,
                    sentiment_score REAL NOT NULL,
                    sentiment_scores TEXT NOT NULL,
                    analyzed_at TEXT NOT NULL
                )
            ''')

            # Create indexes for posts
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON posts(created_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sentiment_label ON posts(sentiment_label)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_subreddit ON posts(subreddit)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_url ON posts(url)')

            # Create sectors table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sectors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL
                )
            ''')

            # Create industries table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS industries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL
                )
            ''')

            # Create tickers table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tickers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT UNIQUE NOT NULL,
                    company_name TEXT,
                    sector_id INTEGER,
                    industry_id INTEGER,
                    FOREIGN KEY (sector_id) REFERENCES sectors(id),
                    FOREIGN KEY (industry_id) REFERENCES industries(id)
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_ticker_symbol ON tickers(symbol)')

            # Create junction tables for many-to-many relationships
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS post_tickers (
                    post_id TEXT NOT NULL,
                    ticker_id INTEGER NOT NULL,
                    PRIMARY KEY (post_id, ticker_id),
                    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
                    FOREIGN KEY (ticker_id) REFERENCES tickers(id) ON DELETE CASCADE
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_post_tickers_post ON post_tickers(post_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_post_tickers_ticker ON post_tickers(ticker_id)')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS post_industries (
                    post_id TEXT NOT NULL,
                    industry_id INTEGER NOT NULL,
                    PRIMARY KEY (post_id, industry_id),
                    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
                    FOREIGN KEY (industry_id) REFERENCES industries(id) ON DELETE CASCADE
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_post_industries_post ON post_industries(post_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_post_industries_industry ON post_industries(industry_id)')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS post_sectors (
                    post_id TEXT NOT NULL,
                    sector_id INTEGER NOT NULL,
                    PRIMARY KEY (post_id, sector_id),
                    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
                    FOREIGN KEY (sector_id) REFERENCES sectors(id) ON DELETE CASCADE
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_post_sectors_post ON post_sectors(post_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_post_sectors_sector ON post_sectors(sector_id)')

            print("Database schema version 2 created successfully")

    def _migrate_v1_to_v2(self):
        """Migrate from version 1 (basic schema) to version 2 (enhanced schema)"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Check if posts table exists and has old schema
            cursor.execute("PRAGMA table_info(posts)")
            columns = {row['name'] for row in cursor.fetchall()}

            # Add new columns to posts table if they don't exist
            new_columns = [
                ('url', 'TEXT'),
                ('subreddit', 'TEXT'),
                ('title', 'TEXT'),
                ('author', 'TEXT'),
                ('timezone', 'TEXT'),
                ('reddit_id', 'TEXT')
            ]

            for col_name, col_type in new_columns:
                if col_name not in columns:
                    cursor.execute(f'ALTER TABLE posts ADD COLUMN {col_name} {col_type}')
                    print(f"Added column {col_name} to posts table")

            # Create new tables (they won't exist in v1)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sectors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS industries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tickers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT UNIQUE NOT NULL,
                    company_name TEXT,
                    sector_id INTEGER,
                    industry_id INTEGER,
                    FOREIGN KEY (sector_id) REFERENCES sectors(id),
                    FOREIGN KEY (industry_id) REFERENCES industries(id)
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_ticker_symbol ON tickers(symbol)')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS post_tickers (
                    post_id TEXT NOT NULL,
                    ticker_id INTEGER NOT NULL,
                    PRIMARY KEY (post_id, ticker_id),
                    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
                    FOREIGN KEY (ticker_id) REFERENCES tickers(id) ON DELETE CASCADE
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_post_tickers_post ON post_tickers(post_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_post_tickers_ticker ON post_tickers(ticker_id)')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS post_industries (
                    post_id TEXT NOT NULL,
                    industry_id INTEGER NOT NULL,
                    PRIMARY KEY (post_id, industry_id),
                    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
                    FOREIGN KEY (industry_id) REFERENCES industries(id) ON DELETE CASCADE
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_post_industries_post ON post_industries(post_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_post_industries_industry ON post_industries(industry_id)')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS post_sectors (
                    post_id TEXT NOT NULL,
                    sector_id INTEGER NOT NULL,
                    PRIMARY KEY (post_id, sector_id),
                    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
                    FOREIGN KEY (sector_id) REFERENCES sectors(id) ON DELETE CASCADE
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_post_sectors_post ON post_sectors(post_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_post_sectors_sector ON post_sectors(sector_id)')

            # Add new indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_subreddit ON posts(subreddit)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_url ON posts(url)')

            # Update schema version
            cursor.execute(f'UPDATE {self.VERSION_TABLE} SET version = ?',
                          (self.CURRENT_VERSION,))

            print("Database migrated to version 2 successfully")
    
    def _create_v3_schema(self):
        """Create complete version 3 schema from scratch (includes watchlists)"""
        # First create v2 schema
        self._create_base_schema()
        
        # Then add watchlist tables
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Create watchlists table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS watchlists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create watchlist_tickers junction table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS watchlist_tickers (
                    watchlist_id INTEGER NOT NULL,
                    ticker TEXT NOT NULL,
                    added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (watchlist_id, ticker),
                    FOREIGN KEY (watchlist_id) REFERENCES watchlists(id) ON DELETE CASCADE
                )
            ''')
            
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_watchlist_tickers_watchlist ON watchlist_tickers(watchlist_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_watchlist_tickers_ticker ON watchlist_tickers(ticker)')
            
            # Update version to 3
            cursor.execute(f'UPDATE {self.VERSION_TABLE} SET version = ?', (3,))
            
            print("Database schema version 3 created successfully")
    
    def _create_base_schema(self):
        """Create base schema (v2) without watchlists"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Create version table
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS {self.VERSION_TABLE} (
                    version INTEGER NOT NULL
                )
            ''')
            cursor.execute(f'INSERT INTO {self.VERSION_TABLE} (version) VALUES (?)', (2,))
            
            # Create posts table with all fields
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS posts (
                    id TEXT PRIMARY KEY,
                    reddit_id TEXT UNIQUE,
                    url TEXT,
                    subreddit TEXT,
                    title TEXT,
                    text TEXT NOT NULL,
                    author TEXT,
                    created_at TEXT NOT NULL,
                    timezone TEXT,
                    sentiment_label TEXT NOT NULL,
                    sentiment_score REAL NOT NULL,
                    sentiment_scores TEXT NOT NULL,
                    analyzed_at TEXT NOT NULL
                )
            ''')
            
            # Create indexes for posts
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON posts(created_at DESC)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sentiment_label ON posts(sentiment_label)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_subreddit ON posts(subreddit)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_url ON posts(url)')
            
            # Create sectors table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sectors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL
                )
            ''')
            
            # Create industries table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS industries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL
                )
            ''')
            
            # Create tickers table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tickers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT UNIQUE NOT NULL,
                    company_name TEXT,
                    sector_id INTEGER,
                    industry_id INTEGER,
                    FOREIGN KEY (sector_id) REFERENCES sectors(id),
                    FOREIGN KEY (industry_id) REFERENCES industries(id)
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_ticker_symbol ON tickers(symbol)')
            
            # Create junction tables for many-to-many relationships
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS post_tickers (
                    post_id TEXT NOT NULL,
                    ticker_id INTEGER NOT NULL,
                    PRIMARY KEY (post_id, ticker_id),
                    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
                    FOREIGN KEY (ticker_id) REFERENCES tickers(id) ON DELETE CASCADE
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_post_tickers_post ON post_tickers(post_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_post_tickers_ticker ON post_tickers(ticker_id)')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS post_industries (
                    post_id TEXT NOT NULL,
                    industry_id INTEGER NOT NULL,
                    PRIMARY KEY (post_id, industry_id),
                    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
                    FOREIGN KEY (industry_id) REFERENCES industries(id) ON DELETE CASCADE
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_post_industries_post ON post_industries(post_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_post_industries_industry ON post_industries(industry_id)')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS post_sectors (
                    post_id TEXT NOT NULL,
                    sector_id INTEGER NOT NULL,
                    PRIMARY KEY (post_id, sector_id),
                    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
                    FOREIGN KEY (sector_id) REFERENCES sectors(id) ON DELETE CASCADE
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_post_sectors_post ON post_sectors(post_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_post_sectors_sector ON post_sectors(sector_id)')
    
    def _migrate_v2_to_v3(self):
        """Migrate from version 2 to version 3 (add watchlist tables)"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Create watchlists table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS watchlists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create watchlist_tickers junction table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS watchlist_tickers (
                    watchlist_id INTEGER NOT NULL,
                    ticker TEXT NOT NULL,
                    added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (watchlist_id, ticker),
                    FOREIGN KEY (watchlist_id) REFERENCES watchlists(id) ON DELETE CASCADE
                )
            ''')
            
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_watchlist_tickers_watchlist ON watchlist_tickers(watchlist_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_watchlist_tickers_ticker ON watchlist_tickers(ticker)')
            
            # Update schema version
            cursor.execute(f'UPDATE {self.VERSION_TABLE} SET version = ?', (3,))
