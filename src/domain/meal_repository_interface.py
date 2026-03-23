"""
Port (Interface) for meal repository.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from src.domain.meal import Meal


class IMealRepository(ABC):

    @abstractmethod
    def save(self, meal: Meal) -> Meal:
        pass

    @abstractmethod
    def get_by_profile(self, profile_id: int, limit: int = 50) -> List[Meal]:
        pass

    @abstractmethod
    def get_today_by_profile(self, profile_id: int) -> List[Meal]:
        pass

    @abstractmethod
    def get_by_id(self, meal_id: int) -> Optional[Meal]:
        pass

    @abstractmethod
    def delete(self, meal_id: int) -> bool:
        pass

