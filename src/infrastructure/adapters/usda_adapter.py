import os
import time
import logging
import requests
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

from src.domain.food_api_interface import IFoodAPI

class USDAAdapter(IFoodAPI):
    """
    Queries the USDA FoodData Central API for nutrition data.
    Requires English search terms.
    """

    SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"

    def __init__(self, nutrition_cache=None):
        self._cache = nutrition_cache
        self.api_key = os.getenv("USDA_API_KEY", "DEMO_KEY")

    @property
    def is_configured(self) -> bool:
        return True

    def query_nutrition(
        self,
        food_name_en: str,
        quantity: float = 100,
        unit: str = "g",
    ) -> Optional[Dict[str, Any]]:
        t0 = time.time()
        logger.info("[USDA] query_nutrition('%s', %.1f%s)", food_name_en, quantity, unit)
        try:
            per100 = self._get_per100(food_name_en)
            if not per100:
                logger.warning("[USDA]   ✗ Sin datos para '%s' (%.2fs)", food_name_en, time.time() - t0)
                return None

            factor = self._calculate_factor(quantity, unit)

            result = {
                "name": per100.get("product_name", food_name_en),
                "quantity": quantity,
                "unit": unit,
                "calories": round(per100["calories_100"] * factor, 1),
                "protein": round(per100["protein_100"] * factor, 1),
                "carbs": round(per100["carbs_100"] * factor, 1),
                "fat": round(per100["fat_100"] * factor, 1),
                "fiber": round(per100.get("fiber_100", 0) * factor, 1),
                "sugar": round(per100.get("sugar_100", 0) * factor, 1),
                "sodium": round(per100.get("sodium_100", 0) * factor, 1),
                "potassium": round(per100.get("potassium_100", 0) * factor, 1),
                "saturated_fat": round(per100.get("saturated_fat_100", 0) * factor, 1),
                "cholesterol": round(per100.get("cholesterol_100", 0) * factor, 1),
                "source": "usda_fdc",
            }
            logger.info("[USDA]   ✓ '%s' → %skcal | P:%.1fg | C:%.1fg | G:%.1fg (%.2fs)",
                        result["name"], result["calories"], result["protein"],
                        result["carbs"], result["fat"], time.time() - t0)
            return result
        except Exception as e:
            logger.error("[USDA]   ✗ Excepción para '%s': %s (%.2fs)", food_name_en, e, time.time() - t0)
            return None

    def enrich_food_items_parallel(
        self,
        food_items: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        t0 = time.time()

        def _enrich_one(item: Dict[str, Any]) -> Dict[str, Any]:
            # Use name_en if provided by LLM; fallback to name
            search_name = item.get("name_en") or item.get("name", "?")
            result = self.query_nutrition(
                food_name_en=search_name,
                quantity=item.get("quantity", 100),
                unit=item.get("unit", "g"),
            )
            if result:
                item["estimated_calories"] = result["calories"]
                item["estimated_protein"] = result["protein"]
                item["estimated_carbs"] = result["carbs"]
                item["estimated_fat"] = result["fat"]
                item["micronutrients"] = {
                    k: result[k]
                    for k in ("fiber", "sugar", "sodium", "potassium",
                              "saturated_fat", "cholesterol")
                    if k in result
                }
                item["enriched_source"] = "usda_fdc"
            else:
                item.setdefault("estimated_calories", 0)
                item.setdefault("estimated_protein", 0)
                item.setdefault("estimated_carbs", 0)
                item.setdefault("estimated_fat", 0)
                item["enriched_source"] = "vision_estimate"
            return item

        with ThreadPoolExecutor(max_workers=min(max(len(food_items), 1), 6)) as pool:
            futures = {pool.submit(_enrich_one, item): idx for idx, item in enumerate(food_items)}
            results = [None] * len(food_items)
            for future in as_completed(futures):
                idx = futures[future]
                results[idx] = future.result()

        logger.info("[USDA] Enriquecimiento paralelo de %d alimentos: %.2fs", len(food_items), time.time() - t0)
        return results

    def _get_per100(self, food_name_en: str) -> Optional[Dict[str, Any]]:
        if self._cache:
            cached = self._cache.get(f"usda_{food_name_en}")
            if cached:
                logger.info("[USDA]   Cache HIT: '%s'", food_name_en)
                return cached

        t0 = time.time()
        product = self._search_product(food_name_en)
        elapsed = time.time() - t0

        if not product:
            logger.info("[USDA]   Cache MISS + API sin resultado: '%s' (%.2fs)", food_name_en, elapsed)
            return None

        # USDA returns an array of foodNutrients
        nutrients = product.get("foodNutrients", [])
        if not nutrients:
            return None

        def extract_nut(nutrient_id: int) -> float:
            for n in nutrients:
                if n.get("nutrientId") == nutrient_id:
                    return n.get("value", 0)
            return 0

        # FDC Nutrient IDs
        # 1008: Energy (kcal)
        # 1003: Protein (g)
        # 1005: Carbohydrate (g)
        # 1004: Total lipid (fat) (g)
        # 1079: Fiber, total dietary (g)
        # 2000: Sugars, total including NLEA (g)
        # 1093: Sodium, Na (mg)
        # 1092: Potassium, K (mg)
        # 1258: Fatty acids, total saturated (g)
        # 1253: Cholesterol (mg)

        per100 = {
            "product_name": product.get("description", food_name_en),
            "calories_100": extract_nut(1008),
            "protein_100": extract_nut(1003),
            "carbs_100": extract_nut(1005),
            "fat_100": extract_nut(1004),
            "fiber_100": extract_nut(1079),
            "sugar_100": extract_nut(2000),
            "sodium_100": extract_nut(1093),
            "potassium_100": extract_nut(1092),
            "saturated_fat_100": extract_nut(1258),
            "cholesterol_100": extract_nut(1253),
        }

        if self._cache:
            self._cache.put(f"usda_{food_name_en}", per100)

        logger.info("[USDA]   Cache MISS + API OK: '%s' (%.2fs)", food_name_en, elapsed)
        return per100

    def _search_product(self, food_name_en: str) -> Optional[Dict[str, Any]]:
        search_term = food_name_en.strip()
        logger.info("[USDA]   HTTP GET search_terms='%s'", search_term)

        try:
            resp = requests.get(
                self.SEARCH_URL,
                params={
                    "query": search_term,
                    "api_key": self.api_key,
                    "pageSize": 5,
                    "dataType": "Foundation,SR Legacy", # Usually whole/raw foods
                },
                timeout=5,
            )
            # If rate limited (429) via DEMO_KEY, log specific warning
            if resp.status_code == 429:
                logger.warning("[USDA] Rate limit exceeded (429) - DEMO_KEY limits apply.")
                return None
            
            resp.raise_for_status()
            data = resp.json()

            foods = data.get("foods", [])
            logger.info("[USDA]   HTTP %d — %d productos encontrados", resp.status_code, len(foods))

            if foods:
                return foods[0]
                
        except requests.exceptions.Timeout:
            logger.warning("[USDA]   HTTP TIMEOUT para '%s'", search_term)
        except requests.exceptions.RequestException as e:
            logger.warning("[USDA]   HTTP ERROR para '%s': %s", search_term, e)
        except Exception as e:
            logger.error("[USDA]   Error inesperado para '%s': %s", search_term, e)

        return None

    def _calculate_factor(self, quantity: float, unit: str) -> float:
        unit_lower = unit.lower().strip()
        grams = quantity
        if unit_lower in ("kg", "kilogramo", "kilogramos"):
            grams = quantity * 1000
        elif unit_lower in ("oz", "onza", "onzas"):
            grams = quantity * 28.3495
        elif unit_lower in ("lb", "libra", "libras"):
            grams = quantity * 453.592
        elif unit_lower in ("taza", "tazas", "cup", "cups"):
            grams = quantity * 240
        elif unit_lower in ("cucharada", "cucharadas", "tbsp"):
            grams = quantity * 15
        elif unit_lower in ("cucharadita", "cucharaditas", "tsp"):
            grams = quantity * 5
        elif unit_lower in ("ml", "mililitro", "mililitros"):
            grams = quantity
        elif unit_lower in ("l", "litro", "litros"):
            grams = quantity * 1000

        return grams / 100.0
