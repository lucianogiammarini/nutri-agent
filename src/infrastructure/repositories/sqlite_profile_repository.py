"""
Adapter - SQLite repository for user profiles.
"""

import sqlite3
from typing import List, Optional
from datetime import datetime

from src.domain.user_profile import UserProfile
from src.domain.profile_repository_interface import IProfileRepository


class SQLiteProfileRepository(IProfileRepository):

    def __init__(self, database_path: str = 'database.db'):
        self.database_path = database_path
        self._init_database()

    def _init_database(self):
        conn = self._get_connection()
        conn.execute('''
            CREATE TABLE IF NOT EXISTS user_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                age INTEGER NOT NULL,
                weight REAL NOT NULL,
                height REAL NOT NULL,
                goal TEXT NOT NULL DEFAULT 'maintenance',
                daily_calories INTEGER DEFAULT 2000,
                daily_protein REAL DEFAULT 75,
                daily_carbs REAL DEFAULT 250,
                daily_fat REAL DEFAULT 65,
                allergies TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _row_to_profile(self, row) -> UserProfile:
        return UserProfile(
            id=row['id'],
            name=row['name'],
            age=row['age'],
            weight=row['weight'],
            height=row['height'],
            goal=row['goal'],
            daily_calories=row['daily_calories'],
            daily_protein=row['daily_protein'],
            daily_carbs=row['daily_carbs'],
            daily_fat=row['daily_fat'],
            allergies=row['allergies'] or '',
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None,
        )

    def save(self, profile: UserProfile) -> UserProfile:
        conn = self._get_connection()
        cursor = conn.execute(
            '''INSERT INTO user_profiles
               (name, age, weight, height, goal, daily_calories, daily_protein,
                daily_carbs, daily_fat, allergies, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (profile.name, profile.age, profile.weight, profile.height,
             profile.goal, profile.daily_calories, profile.daily_protein,
             profile.daily_carbs, profile.daily_fat, profile.allergies,
             profile.created_at, profile.updated_at)
        )
        profile.id = cursor.lastrowid
        conn.commit()
        conn.close()
        return profile

    def get_all(self) -> List[UserProfile]:
        conn = self._get_connection()
        rows = conn.execute('SELECT * FROM user_profiles ORDER BY created_at DESC').fetchall()
        conn.close()
        return [self._row_to_profile(r) for r in rows]

    def get_by_id(self, profile_id: int) -> Optional[UserProfile]:
        conn = self._get_connection()
        row = conn.execute('SELECT * FROM user_profiles WHERE id = ?', (profile_id,)).fetchone()
        conn.close()
        return self._row_to_profile(row) if row else None

    def update(self, profile: UserProfile) -> UserProfile:
        profile.updated_at = datetime.now()
        conn = self._get_connection()
        conn.execute(
            '''UPDATE user_profiles SET name=?, age=?, weight=?, height=?, goal=?,
               daily_calories=?, daily_protein=?, daily_carbs=?, daily_fat=?,
               allergies=?, updated_at=? WHERE id=?''',
            (profile.name, profile.age, profile.weight, profile.height,
             profile.goal, profile.daily_calories, profile.daily_protein,
             profile.daily_carbs, profile.daily_fat, profile.allergies,
             profile.updated_at, profile.id)
        )
        conn.commit()
        conn.close()
        return profile

    def delete(self, profile_id: int) -> bool:
        conn = self._get_connection()
        cursor = conn.execute('DELETE FROM user_profiles WHERE id = ?', (profile_id,))
        conn.commit()
        conn.close()
        return cursor.rowcount > 0

