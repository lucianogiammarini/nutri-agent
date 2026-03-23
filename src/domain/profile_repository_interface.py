"""
Port (Interface) for user profile repository.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from src.domain.user_profile import UserProfile


class IProfileRepository(ABC):

    @abstractmethod
    def save(self, profile: UserProfile) -> UserProfile:
        pass

    @abstractmethod
    def get_all(self) -> List[UserProfile]:
        pass

    @abstractmethod
    def get_by_id(self, profile_id: int) -> Optional[UserProfile]:
        pass

    @abstractmethod
    def update(self, profile: UserProfile) -> UserProfile:
        pass

    @abstractmethod
    def delete(self, profile_id: int) -> bool:
        pass

