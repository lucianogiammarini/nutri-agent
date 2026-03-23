"""
Adapter - SQLite repository for meals.
"""

import sqlite3
from typing import List, Optional
from datetime import datetime, date

from src.domain.meal import Meal
from src.domain.meal_repository_interface import IMealRepository


class SQLiteMealRepository(IMealRepository):

    def __init__(self, database_path: str = 'database.db'):
        self.database_path = database_path
        self._init_database()

    def _init_database(self):
        conn = self._get_connection()
        conn.execute('''
            CREATE TABLE IF NOT EXISTS meals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_profile_id INTEGER NOT NULL,
                description TEXT DEFAULT '',
                photo_path TEXT,
                food_items TEXT DEFAULT '[]',
                total_calories REAL DEFAULT 0,
                total_protein REAL DEFAULT 0,
                total_carbs REAL DEFAULT 0,
                total_fat REAL DEFAULT 0,
                analysis_raw TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_profile_id) REFERENCES user_profiles(id)
            )
        ''')
        conn.commit()
        conn.close()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _row_to_meal(self, row) -> Meal:
        return Meal(
            id=row['id'],
            user_profile_id=row['user_profile_id'],
            description=row['description'] or '',
            photo_path=row['photo_path'],
            food_items=row['food_items'] or '[]',
            total_calories=row['total_calories'] or 0,
            total_protein=row['total_protein'] or 0,
            total_carbs=row['total_carbs'] or 0,
            total_fat=row['total_fat'] or 0,
            analysis_raw=row['analysis_raw'] or '',
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
        )

    def save(self, meal: Meal) -> Meal:
        conn = self._get_connection()
        cursor = conn.execute(
            '''INSERT INTO meals
               (user_profile_id, description, photo_path, food_items,
                total_calories, total_protein, total_carbs, total_fat,
                analysis_raw, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (meal.user_profile_id, meal.description, meal.photo_path,
             meal.food_items, meal.total_calories, meal.total_protein,
             meal.total_carbs, meal.total_fat, meal.analysis_raw,
             meal.created_at)
        )
        meal.id = cursor.lastrowid
        conn.commit()
        conn.close()
        return meal

    def get_by_profile(self, profile_id: int, limit: int = 50) -> List[Meal]:
        conn = self._get_connection()
        rows = conn.execute(
            'SELECT * FROM meals WHERE user_profile_id = ? ORDER BY created_at DESC LIMIT ?',
            (profile_id, limit)
        ).fetchall()
        conn.close()
        return [self._row_to_meal(r) for r in rows]

    def get_today_by_profile(self, profile_id: int) -> List[Meal]:
        conn = self._get_connection()
        today_str = date.today().isoformat()
        rows = conn.execute(
            "SELECT * FROM meals WHERE user_profile_id = ? AND date(created_at) = ? ORDER BY created_at DESC",
            (profile_id, today_str)
        ).fetchall()
        conn.close()
        return [self._row_to_meal(r) for r in rows]

    def get_by_id(self, meal_id: int) -> Optional[Meal]:
        conn = self._get_connection()
        row = conn.execute('SELECT * FROM meals WHERE id = ?', (meal_id,)).fetchone()
        conn.close()
        return self._row_to_meal(row) if row else None

    def delete(self, meal_id: int) -> bool:
        conn = self._get_connection()
        cursor = conn.execute('DELETE FROM meals WHERE id = ?', (meal_id,))
        conn.commit()
        conn.close()
        return cursor.rowcount > 0

