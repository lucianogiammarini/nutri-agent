"""
Domain Entity: ChatMessage

Represents a single message in the user's chat conversation.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any


@dataclass
class ChatMessage:
    user_profile_id: int
    role: str  # 'user' or 'assistant'
    content: str
    id: Optional[int] = None
    created_at: Optional[datetime] = None

    def __post_init__(self):
        if self.role not in ("user", "assistant", "system"):
            raise ValueError("Role must be 'user', 'assistant', or 'system'")
        if not self.content or not self.content.strip():
            raise ValueError("Content cannot be empty")
        if self.created_at is None:
            self.created_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_profile_id": self.user_profile_id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
