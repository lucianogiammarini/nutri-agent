"""
Adapter - Open Food Facts API for detailed nutritional data.

Free, open-source nutrition database with Spanish content support.
No API key required.

Optimizations:
- SQLite cache for repeated lookups (7-day TTL)
- Parallel HTTP requests via ThreadPoolExecutor
- Reduced timeout for faster fallback

API docs: https://wiki.openfoodfacts.org/API
"""

import time
import logging
import requests
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


class OpenFoodFactsAdapter:
    """
    Queries the Open Food Facts API for nutrition data.
    Supports Spanish language searches.
    No API key required - always available.
    """

    SEARCH_URL = "https://world.openfoodfacts.org/cgi/search.pl"

    def __init__(self, nutrition_cache=None):
        """
        Args:
            nutrition_cache: Optional SQLiteNutritionCache instance for
                             caching per-100g data across requests.
        """
        self._cache = nutrition_cache

    @property
    def is_configured(self) -> bool:
        """Open Food Facts is always available - no keys required."""
        return True

    # ── Public API ──────────────────────────────────────────────

    def query_nutrition(
        self,
        food_name: str,
        quantity: float = 100,
        unit: str = "g",
    ) -> Optional[Dict[str, Any]]:
        """
        Tool: consultar_nutricion(alimento, cantidad, unidad)

        Returns nutrition data scaled to the requested quantity.
        Uses SQLite cache to avoid redundant HTTP calls.
        """
        t0 = time.time()
        logger.info("[OFF] query_nutrition('%s', %.1f%s)", food_name, quantity, unit)
        try:
            per100 = self._get_per100(food_name)
            if not per100:
                logger.warning("[OFF]   ✗ Sin datos para '%s' (%.2fs)", food_name, time.time() - t0)
                return None

            factor = self._calculate_factor(quantity, unit)

            result = {
                "name": per100.get("product_name", food_name),
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
                "source": "openfoodfacts",
            }
            logger.info("[OFF]   ✓ '%s' → %skcal | P:%.1fg | C:%.1fg | G:%.1fg (%.2fs)",
                        result["name"], result["calories"], result["protein"],
                        result["carbs"], result["fat"], time.time() - t0)
            return result
        except Exception as e:
            logger.error("[OFF]   ✗ Excepción para '%s': %s (%.2fs)", food_name, e, time.time() - t0)
            return None

    def enrich_food_items_parallel(
        self,
        food_items: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Enriches all food items in PARALLEL using ThreadPoolExecutor.
        Each item is looked up via cache first, then HTTP if cache miss.
        """
        t0 = time.time()

        def _enrich_one(item: Dict[str, Any]) -> Dict[str, Any]:
            name = item.get("name", "?")
            result = self.query_nutrition(
                food_name=name,
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
                item["enriched_source"] = "openfoodfacts"
            else:
                item.setdefault("estimated_calories", 0)
                item.setdefault("estimated_protein", 0)
                item.setdefault("estimated_carbs", 0)
                item.setdefault("estimated_fat", 0)
                item["enriched_source"] = "vision_estimate"
                logger.warning("[OFF]   '%s' → sin datos, usando estimación de Vision", name)
            return item

        with ThreadPoolExecutor(max_workers=min(len(food_items), 6)) as pool:
            futures = {pool.submit(_enrich_one, item): idx for idx, item in enumerate(food_items)}
            results = [None] * len(food_items)
            for future in as_completed(futures):
                idx = futures[future]
                results[idx] = future.result()

        logger.info("[OFF] Enriquecimiento paralelo de %d alimentos: %.2fs", len(food_items), time.time() - t0)
        return results

    # Keep old sequential method as alias for backwards compat
    def enrich_food_items(self, food_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return self.enrich_food_items_parallel(food_items)

    # ── Internal: per-100g data with cache ──────────────────────

    def _get_per100(self, food_name: str) -> Optional[Dict[str, Any]]:
        """
        Returns per-100g nutritional values for a food name.
        Checks SQLite cache first; on miss, queries the API and stores result.
        """
        # 1. Cache hit?
        if self._cache:
            cached = self._cache.get(food_name)
            if cached:
                logger.info("[OFF]   Cache HIT: '%s'", food_name)
                return cached

        # 2. Cache miss → HTTP
        t0 = time.time()
        product = self._search_product(food_name)
        elapsed = time.time() - t0

        if not product:
            logger.info("[OFF]   Cache MISS + API sin resultado: '%s' (%.2fs)", food_name, elapsed)
            return None

        nutriments = product.get("nutriments", {})
        if not nutriments:
            return None

        per100 = {
            "product_name": product.get("product_name", food_name),
            "calories_100": nutriments.get("energy-kcal_100g", 0) or 0,
            "protein_100": nutriments.get("proteins_100g", 0) or 0,
            "carbs_100": nutriments.get("carbohydrates_100g", 0) or 0,
            "fat_100": nutriments.get("fat_100g", 0) or 0,
            "fiber_100": nutriments.get("fiber_100g", 0) or 0,
            "sugar_100": nutriments.get("sugars_100g", 0) or 0,
            "sodium_100": nutriments.get("sodium_100g", 0) or 0,
            "potassium_100": nutriments.get("potassium_100g", 0) or 0,
            "saturated_fat_100": nutriments.get("saturated-fat_100g", 0) or 0,
            "cholesterol_100": nutriments.get("cholesterol_100g", 0) or 0,
        }

        # 3. Store in cache
        if self._cache:
            self._cache.put(food_name, per100)

        logger.info("[OFF]   Cache MISS + API OK: '%s' (%.2fs)", food_name, elapsed)
        return per100

    # ── HTTP search ─────────────────────────────────────────────

    def _search_product(self, food_name: str) -> Optional[Dict[str, Any]]:
        """
        Searches Open Food Facts for a product matching the food name.
        Single request to world (contains all locales). Timeout = 5s.
        """
        search_term = food_name.strip().lower()
        logger.info("[OFF]   HTTP GET search_terms='%s'", search_term)

        try:
            t0 = time.time()
            resp = requests.get(
                self.SEARCH_URL,
                params={
                    "search_terms": search_term,
                    "search_simple": 1,
                    "action": "process",
                    "json": 1,
                    "page_size": 5,
                    "sort_by": "popularity",
                    "lc": "es",
                },
                timeout=5,
                headers={"User-Agent": "NutritionHealthManager/1.0"},
            )
            resp.raise_for_status()
            data = resp.json()

            products = data.get("products", [])
            logger.info("[OFF]   HTTP %d — %d productos encontrados (%.2fs)",
                        resp.status_code, len(products), time.time() - t0)

            if products:
                for p in products:
                    nutriments = p.get("nutriments", {})
                    if nutriments and nutriments.get("energy-kcal_100g"):
                        logger.info("[OFF]   Seleccionado: '%s' (%.0f kcal/100g)",
                                    p.get("product_name", "?"),
                                    nutriments.get("energy-kcal_100g", 0))
                        return p
                # Fallback to first product
                logger.info("[OFF]   Fallback al primer producto: '%s'",
                            products[0].get("product_name", "?"))
                return products[0]
        except requests.exceptions.Timeout:
            logger.warning("[OFF]   HTTP TIMEOUT para '%s'", search_term)
        except requests.exceptions.RequestException as e:
            logger.warning("[OFF]   HTTP ERROR para '%s': %s", search_term, e)
        except Exception as e:
            logger.error("[OFF]   Error inesperado para '%s': %s", search_term, e)

        return None

    # ── Unit conversion ─────────────────────────────────────────

    def _calculate_factor(self, quantity: float, unit: str) -> float:
        """
        Convert the requested quantity/unit to a multiplication factor
        based on 100g reference values from Open Food Facts.
        """
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

