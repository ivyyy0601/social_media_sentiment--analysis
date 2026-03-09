"""
Watchlist repository for managing user watchlists.
"""

import sqlite3
from datetime import datetime
from contextlib import contextmanager
from typing import List, Dict, Optional


class WatchlistRepository:
    """Repository for watchlist CRUD operations"""
    
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
    
    def create_watchlist(self, name: str) -> int:
        """
        Create a new watchlist
        
        Args:
            name: Name of the watchlist
            
        Returns:
            ID of created watchlist
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO watchlists (name, created_at) VALUES (?, ?)',
                (name, datetime.utcnow().isoformat())
            )
            return cursor.lastrowid
    
    def get_watchlists(self) -> List[Dict]:
        """
        Get all watchlists
        
        Returns:
            List of watchlist dictionaries
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, name, created_at
                FROM watchlists
                ORDER BY created_at DESC
            ''')
            
            watchlists = []
            for row in cursor.fetchall():
                watchlist = {
                    'id': row['id'],
                    'name': row['name'],
                    'created_at': row['created_at'],
                    'tickers': self.get_watchlist_tickers(row['id'])
                }
                watchlists.append(watchlist)
            
            return watchlists
    
    def get_watchlist(self, watchlist_id: int) -> Optional[Dict]:
        """
        Get a specific watchlist
        
        Args:
            watchlist_id: ID of the watchlist
            
        Returns:
            Watchlist dictionary or None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT id, name, created_at FROM watchlists WHERE id = ?',
                (watchlist_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return {
                'id': row['id'],
                'name': row['name'],
                'created_at': row['created_at'],
                'tickers': self.get_watchlist_tickers(row['id'])
            }
    
    def update_watchlist(self, watchlist_id: int, name: str) -> bool:
        """
        Update watchlist name
        
        Args:
            watchlist_id: ID of the watchlist
            name: New name
            
        Returns:
            True if updated, False if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE watchlists SET name = ? WHERE id = ?',
                (name, watchlist_id)
            )
            return cursor.rowcount > 0
    
    def delete_watchlist(self, watchlist_id: int) -> bool:
        """
        Delete a watchlist
        
        Args:
            watchlist_id: ID of the watchlist
            
        Returns:
            True if deleted, False if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Delete watchlist (CASCADE will remove tickers)
            cursor.execute('DELETE FROM watchlists WHERE id = ?', (watchlist_id,))
            return cursor.rowcount > 0
    
    def get_watchlist_tickers(self, watchlist_id: int) -> List[str]:
        """
        Get tickers in a watchlist
        
        Args:
            watchlist_id: ID of the watchlist
            
        Returns:
            List of ticker symbols
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT ticker FROM watchlist_tickers WHERE watchlist_id = ? ORDER BY added_at',
                (watchlist_id,)
            )
            return [row['ticker'] for row in cursor.fetchall()]
    
    def add_ticker_to_watchlist(self, watchlist_id: int, ticker: str) -> bool:
        """
        Add a ticker to a watchlist
        
        Args:
            watchlist_id: ID of the watchlist
            ticker: Ticker symbol
            
        Returns:
            True if added, False if already exists
            
        Raises:
            Exception: For database errors other than integrity violations
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'INSERT INTO watchlist_tickers (watchlist_id, ticker, added_at) VALUES (?, ?, ?)',
                    (watchlist_id, ticker.upper(), datetime.utcnow().isoformat())
                )
                return True
        except sqlite3.IntegrityError:
            # Ticker already in watchlist
            return False
        except Exception as e:
            print(f"Error adding ticker to watchlist: {e}")
            raise
    
    def remove_ticker_from_watchlist(self, watchlist_id: int, ticker: str) -> bool:
        """
        Remove a ticker from a watchlist
        
        Args:
            watchlist_id: ID of the watchlist
            ticker: Ticker symbol
            
        Returns:
            True if removed, False if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'DELETE FROM watchlist_tickers WHERE watchlist_id = ? AND ticker = ?',
                (watchlist_id, ticker.upper())
            )
            return cursor.rowcount > 0
