"""
Port (Interface) for chat message repository.
"""

from abc import ABC, abstractmethod
from typing import List
from src.domain.chat_message import ChatMessage


class IChatRepository(ABC):

    @abstractmethod
    def save(self, message: ChatMessage) -> ChatMessage:
        pass

    @abstractmethod
    def get_by_profile(self, profile_id: int, limit: int = 20) -> List[ChatMessage]:
        pass

    @abstractmethod
    def delete_by_profile(self, profile_id: int) -> bool:
        pass

