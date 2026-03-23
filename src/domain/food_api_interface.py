from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

class IFoodAPI(ABC):
    """
    Port for external food/nutrition databases.
    """

    @abstractmethod
    def query_nutrition(
        self,
        food_name_en: str,
        quantity: float = 100,
        unit: str = "g",
    ) -> Optional[Dict[str, Any]]:
        """Queries nutrition info for a specific food item."""
        pass

    @abstractmethod
    def enrich_food_items_parallel(
        self,
        food_items: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Enriches a list of parsed food items with exact nutrition data."""
        pass
