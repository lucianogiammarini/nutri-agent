"""
Use Cases - Meal analysis and history.

Orchestrates: image -> vision (identifies foods) -> tool calling (nutrition API) -> store.
"""

from typing import Dict, Any
from src.domain.meal import Meal
from src.domain.meal_repository_interface import IMealRepository
from src.domain.profile_repository_interface import IProfileRepository
from src.domain.llm_adapter_interface import ILlmAdapter


class AnalyzeMealUseCase:
    """
    Full pipeline:
      image -> vision (food identification + portion estimation)
            -> tool calling (Open Food Facts nutrition lookup)
            -> persist.
    """

    def __init__(
        self,
        meal_repository: IMealRepository,
        profile_repository: IProfileRepository,
        vision_adapter: ILlmAdapter,
    ):
        self.meal_repo = meal_repository
        self.profile_repo = profile_repository
        self.vision_adapter = vision_adapter

    def execute(
        self, profile_id: int, image_path: str, comment: str = ""
    ) -> Dict[str, Any]:
        try:
            profile = self.profile_repo.get_by_id(profile_id)
            if not profile:
                return {"success": False, "error": "Profile not found"}

            # Vision analysis + tool-calling enrichment (handled by LangChain adapter)
            analysis = self.vision_adapter.analyze_food_image(
                image_path, user_comment=comment
            )

            food_items = analysis.get("food_items", [])

            total_cal = analysis.get("total_calories", 0)
            total_prot = analysis.get("total_protein", 0)
            total_carbs = analysis.get("total_carbs", 0)
            total_fat = analysis.get("total_fat", 0)

            # Determine enrichment source from food items
            sources = {i.get("enriched_source", "vision_estimate") for i in food_items}
            enriched_with = "usda_fdc" if "usda_fdc" in sources else "vision_estimate"

            # Create and persist meal
            meal = Meal(
                user_profile_id=profile_id,
                description=analysis.get("description", ""),
                photo_path=image_path,
                total_calories=round(total_cal, 1),
                total_protein=round(total_prot, 1),
                total_carbs=round(total_carbs, 1),
                total_fat=round(total_fat, 1),
                analysis_raw=analysis.get("_raw", ""),
            )
            meal.set_food_items(food_items)
            saved = self.meal_repo.save(meal)

            return {
                "success": True,
                "message": "Meal analyzed and saved",
                "data": saved.to_dict(),
                "enriched_with": enriched_with,
            }
        except ValueError as e:
            logger.warning("[AnalyzeMealUseCase] Validation error: %s", e)
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.exception(
                "[AnalyzeMealUseCase] Unexpected error during meal analysis"
            )
            return {"success": False, "error": f"Error analyzing meal: {str(e)}"}


class GetMealHistoryUseCase:
    def __init__(self, meal_repository: IMealRepository):
        self.meal_repo = meal_repository

    def execute(self, profile_id: int, limit: int = 20) -> Dict[str, Any]:
        try:
            meals = self.meal_repo.get_by_profile(profile_id, limit)
            return {
                "success": True,
                "total": len(meals),
                "data": [m.to_dict() for m in meals],
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


class GetTodaySummaryUseCase:
    """Returns today's aggregated macros for a user profile."""

    def __init__(
        self, meal_repository: IMealRepository, profile_repository: IProfileRepository
    ):
        self.meal_repo = meal_repository
        self.profile_repo = profile_repository

    def execute(self, profile_id: int) -> Dict[str, Any]:
        try:
            profile = self.profile_repo.get_by_id(profile_id)
            if not profile:
                return {"success": False, "error": "Profile not found"}

            meals = self.meal_repo.get_today_by_profile(profile_id)

            consumed = {
                "calories": round(sum(m.total_calories for m in meals), 1),
                "protein": round(sum(m.total_protein for m in meals), 1),
                "carbs": round(sum(m.total_carbs for m in meals), 1),
                "fat": round(sum(m.total_fat for m in meals), 1),
            }

            goals = {
                "calories": profile.daily_calories,
                "protein": profile.daily_protein,
                "carbs": profile.daily_carbs,
                "fat": profile.daily_fat,
            }

            return {
                "success": True,
                "data": {
                    "profile": profile.to_dict(),
                    "consumed": consumed,
                    "goals": goals,
                    "meals_today": len(meals),
                    "meals": [m.to_dict() for m in meals],
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
