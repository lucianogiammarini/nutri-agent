"""
Domain Entity: UserProfile

Represents a user's health profile with nutritional goals.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any


@dataclass
class UserProfile:
    name: str
    age: int
    weight: float          # kg
    height: float          # cm
    goal: str              # 'deficit', 'maintenance', 'muscle_gain'
    daily_calories: int = 2000
    daily_protein: float = 75.0   # g
    daily_carbs: float = 250.0    # g
    daily_fat: float = 65.0       # g
    allergies: str = ""            # comma-separated
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if not self.name or len(self.name.strip()) == 0:
            raise ValueError("Name cannot be empty")
        if self.age < 1 or self.age > 150:
            raise ValueError("Age must be between 1 and 150")
        if self.weight <= 0:
            raise ValueError("Weight must be positive")
        if self.height <= 0:
            raise ValueError("Height must be positive")
        if self.goal not in ('deficit', 'maintenance', 'muscle_gain'):
            raise ValueError("Goal must be 'deficit', 'maintenance', or 'muscle_gain'")
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()

    def bmi(self) -> float:
        """Calculate Body Mass Index."""
        h_m = self.height / 100
        return round(self.weight / (h_m * h_m), 1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'age': self.age,
            'weight': self.weight,
            'height': self.height,
            'goal': self.goal,
            'daily_calories': self.daily_calories,
            'daily_protein': self.daily_protein,
            'daily_carbs': self.daily_carbs,
            'daily_fat': self.daily_fat,
            'allergies': self.allergies,
            'bmi': self.bmi(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

