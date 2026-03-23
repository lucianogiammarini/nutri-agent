"""
Domain Entity: Meal

Represents a meal logged by the user with nutritional analysis.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
import json


@dataclass
class Meal:
    user_profile_id: int
    description: str = ""
    photo_path: Optional[str] = None
    food_items: str = "[]"         # JSON string of food items list
    total_calories: float = 0.0
    total_protein: float = 0.0
    total_carbs: float = 0.0
    total_fat: float = 0.0
    analysis_raw: str = ""         # raw AI response
    id: Optional[int] = None
    created_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

    def get_food_items(self) -> List[Dict[str, Any]]:
        try:
            return json.loads(self.food_items) if self.food_items else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_food_items(self, items: List[Dict[str, Any]]):
        self.food_items = json.dumps(items, ensure_ascii=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'user_profile_id': self.user_profile_id,
            'description': self.description,
            'photo_path': self.photo_path,
            'food_items': self.get_food_items(),
            'total_calories': self.total_calories,
            'total_protein': self.total_protein,
            'total_carbs': self.total_carbs,
            'total_fat': self.total_fat,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

