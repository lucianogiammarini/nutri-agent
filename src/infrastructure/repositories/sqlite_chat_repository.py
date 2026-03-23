"""
Adapter - SQLite repository for chat messages.
"""

import sqlite3
from typing import List
from datetime import datetime

from src.domain.chat_message import ChatMessage
from src.domain.chat_repository_interface import IChatRepository


class SQLiteChatRepository(IChatRepository):

    def __init__(self, database_path: str = 'database.db'):
        self.database_path = database_path
        self._init_database()

    def _init_database(self):
        conn = self._get_connection()
        conn.execute('''
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_profile_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
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

    def _row_to_message(self, row) -> ChatMessage:
        return ChatMessage(
            id=row['id'],
            user_profile_id=row['user_profile_id'],
            role=row['role'],
            content=row['content'],
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
        )

    def save(self, message: ChatMessage) -> ChatMessage:
        conn = self._get_connection()
        cursor = conn.execute(
            '''INSERT INTO chat_messages (user_profile_id, role, content, created_at)
               VALUES (?, ?, ?, ?)''',
            (message.user_profile_id, message.role, message.content, message.created_at),
        )
        message.id = cursor.lastrowid
        conn.commit()
        conn.close()
        return message

    def get_by_profile(self, profile_id: int, limit: int = 20) -> List[ChatMessage]:
        conn = self._get_connection()
        rows = conn.execute(
            'SELECT * FROM chat_messages WHERE user_profile_id = ? ORDER BY created_at DESC LIMIT ?',
            (profile_id, limit),
        ).fetchall()
        conn.close()
        # Return in chronological order (oldest first)
        return [self._row_to_message(r) for r in reversed(rows)]

    def delete_by_profile(self, profile_id: int) -> bool:
        conn = self._get_connection()
        cursor = conn.execute(
            'DELETE FROM chat_messages WHERE user_profile_id = ?',
            (profile_id,),
        )
        conn.commit()
        conn.close()
        return cursor.rowcount > 0

