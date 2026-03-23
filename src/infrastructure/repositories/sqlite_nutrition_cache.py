"""
Adapter - SQLite cache for Open Food Facts nutrition lookups.

Stores per-100g nutritional data keyed by normalized food name.
Avoids redundant HTTP calls for repeated foods.
"""

import sqlite3
import json
import logging
import time
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Cache entries expire after 7 days
CACHE_TTL_SECONDS = 7 * 24 * 60 * 60


class SQLiteNutritionCache:

    def __init__(self, database_path: str = 'database.db'):
        self.database_path = database_path
        self._init_database()

    def _init_database(self):
        conn = self._get_connection()
        conn.execute('''
            CREATE TABLE IF NOT EXISTS nutrition_cache (
                food_key   TEXT PRIMARY KEY,
                data_json  TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _normalize_key(food_name: str) -> str:
        """Deterministic cache key from food name."""
        return food_name.strip().lower()

    def get(self, food_name: str) -> Optional[Dict[str, Any]]:
        """Return cached per-100g nutrition data, or None if miss / expired."""
        key = self._normalize_key(food_name)
        conn = self._get_connection()
        row = conn.execute(
            'SELECT data_json, created_at FROM nutrition_cache WHERE food_key = ?',
            (key,),
        ).fetchone()
        conn.close()

        if not row:
            return None

        # Check TTL
        try:
            created = datetime.fromisoformat(row['created_at'])
            age = (datetime.now() - created).total_seconds()
            if age > CACHE_TTL_SECONDS:
                self.delete(key)
                return None
        except Exception:
            pass

        try:
            return json.loads(row['data_json'])
        except (json.JSONDecodeError, TypeError):
            return None

    def put(self, food_name: str, data: Dict[str, Any]) -> None:
        """Store per-100g nutrition data."""
        key = self._normalize_key(food_name)
        conn = self._get_connection()
        conn.execute(
            '''INSERT OR REPLACE INTO nutrition_cache (food_key, data_json, created_at)
               VALUES (?, ?, ?)''',
            (key, json.dumps(data, ensure_ascii=False), datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()

    def delete(self, key: str) -> None:
        conn = self._get_connection()
        conn.execute('DELETE FROM nutrition_cache WHERE food_key = ?', (key,))
        conn.commit()
        conn.close()

