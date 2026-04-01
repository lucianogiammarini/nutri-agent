"""
Use Case - RAG-powered nutritional chat with Tool Calling.

The LLM decides which tools to invoke based on the user's question:
- consultar_nutricion: Open Food Facts lookup
- buscar_guia_alimentaria: RAG search on GAPA corpus
- obtener_resumen_hoy: today's macro summary from DB
- obtener_historial_comidas: recent meal history from DB
"""

import logging
from typing import Dict, Any

from src.domain.chat_message import ChatMessage
from src.domain.chat_repository_interface import IChatRepository
from src.domain.profile_repository_interface import IProfileRepository
from src.domain.meal_repository_interface import IMealRepository
from src.domain.vector_repository_interface import IVectorRepository
from src.domain.llm_adapter_interface import ILlmAdapter
from src.domain.food_api_interface import IFoodAPI
from src.infrastructure.adapters.error_mapper import map_llm_error

logger = logging.getLogger(__name__)


class ChatUseCase:
    """
    RAG chat with tool calling:
    user question -> LLM decides tools -> executes -> synthesizes response.
    """

    def __init__(
        self,
        profile_repository: IProfileRepository,
        meal_repository: IMealRepository,
        vector_repository: IVectorRepository,
        chat_repository: IChatRepository,
        chat_adapter: ILlmAdapter,
        food_api_adapter: IFoodAPI,
        mcp_sqlite=None,
    ):
        self.profile_repo = profile_repository
        self.meal_repo = meal_repository
        self.vector_repo = vector_repository
        self.chat_repo = chat_repository
        self.chat_adapter = chat_adapter
        self.food_api = food_api_adapter
        self.mcp_sqlite = mcp_sqlite

    def execute(
        self, profile_id: int, message: str, on_progress: Any = None
    ) -> Dict[str, Any]:
        try:
            if not message or not message.strip():
                return {"success": False, "error": "Message cannot be empty"}

            # 1. Load profile (always needed — lightweight)
            profile = self.profile_repo.get_by_id(profile_id)
            if not profile:
                return {"success": False, "error": "Profile not found"}

            goal_labels = {
                "deficit": "Déficit calórico / Bajar de peso",
                "maintenance": "Mantenimiento",
                "muscle_gain": "Aumento de masa muscular",
            }
            profile_ctx = (
                f"ID de Usuario (para consultas DB): {profile.id}, "
                f"Nombre: {profile.name}, Edad: {profile.age} años, "
                f"Peso: {profile.weight}kg, Altura: {profile.height}cm, "
                f"IMC: {profile.bmi()}, Objetivo: {goal_labels.get(profile.goal, profile.goal)}, "
                f"Meta diaria: {profile.daily_calories}kcal, {profile.daily_protein}g prot, "
                f"{profile.daily_carbs}g carbs, {profile.daily_fat}g grasas"
            )
            if profile.allergies:
                profile_ctx += f", Alergias: {profile.allergies}"

            # 2. Chat history (always needed — lightweight)
            history_messages = self.chat_repo.get_by_profile(profile_id, limit=10)
            history = [{"role": m.role, "content": m.content} for m in history_messages]

            # 3. Build tool handlers — closures that capture profile_id
            tool_handlers = self._build_tool_handlers(profile_id, profile)

            # 4. Let the LLM decide which tools to call
            response = self.chat_adapter.chat_with_context(
                user_message=message,
                profile_context=profile_ctx,
                chat_history=history,
                tool_handlers=tool_handlers,
                mcp_tools=self.mcp_sqlite.tools if self.mcp_sqlite else [],
                on_progress=on_progress,
            )

            # 5. Save messages
            self.chat_repo.save(
                ChatMessage(
                    user_profile_id=profile_id,
                    role="user",
                    content=message,
                )
            )
            self.chat_repo.save(
                ChatMessage(
                    user_profile_id=profile_id,
                    role="assistant",
                    content=response,
                )
            )

            return {
                "success": True,
                "data": {
                    "response": response,
                },
            }
        except ValueError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.exception("Chat error")
            return {"success": False, "error": map_llm_error(e, context_prefix="Chat error")}

    def _build_tool_handlers(self, profile_id: int, profile) -> Dict[str, Any]:
        """
        Returns a dict of tool_name -> callable for the OpenAI adapter
        to execute when the model invokes a tool.
        """
        return {
            "query_nutrition": self._tool_query_nutrition,
            "search_food_guide": self._tool_search_food_guide,
            "get_today_summary": lambda: self._tool_get_today_summary(profile_id, profile),
            "get_meal_history": lambda limite=10: self._tool_get_meal_history(profile_id, limite),
        }

    # ── Tool Handlers ────────────────────────────────────────────────

    def _tool_query_nutrition(
        self, food_name_en: str, quantity: float = 100, unit: str = "g"
    ) -> Dict:
        """Query USDA FoodData Central for nutrition data."""
        result = self.food_api.query_nutrition(food_name_en, quantity, unit)
        if result:
            return {
                "food": result["name"],
                "quantity": f"{result['quantity']}{result['unit']}",
                "calories": result["calories"],
                "protein": result["protein"],
                "carbs": result["carbs"],
                "fat": result["fat"],
                "fiber": result.get("fiber", 0),
                "sugar": result.get("sugar", 0),
                "source": "USDA FoodData Central",
            }
        return {
            "error": f"No se encontró información nutricional para '{food_name_en}' en USDA"
        }

    def _tool_search_food_guide(self, consulta: str) -> Dict:
        """RAG search on the GAPA vector DB."""
        logger.info("[chat-tool] search_food_guide('%s')", consulta[:80])
        chunks = self.vector_repo.search(consulta, top_k=4)
        # Filter out low-relevance chunks to avoid hallucination
        MIN_SCORE = 0.3
        relevant = [
            c for c in chunks if hasattr(c, "score") and c.score and c.score >= MIN_SCORE
        ]
        if relevant:
            logger.info(
                "[chat-tool] GAPA: %d/%d fragmentos relevantes (score >= %.1f)",
                len(relevant),
                len(chunks),
                MIN_SCORE,
            )
            return {
                "results": len(relevant),
                "fragments": [
                    {
                        "text": c.text,
                        "relevance": round(c.score, 3),
                    }
                    for c in relevant
                ],
                "source": "Guías Alimentarias para la Población Argentina (GAPA)",
            }
        logger.info(
            "[chat-tool] GAPA: sin resultados relevantes para '%s' (mejor score: %.3f)",
            consulta[:50],
            chunks[0].score if chunks and chunks[0].score else 0,
        )
        return {
            "results": 0,
            "message": "No se encontró información relevante en las GAPA",
        }

    def _tool_get_today_summary(self, profile_id: int, profile) -> Dict:
        """Get today's consumed macros vs goals."""
        meals = self.meal_repo.get_today_by_profile(profile_id)
        c_cal = sum(m.total_calories for m in meals)
        c_prot = sum(m.total_protein for m in meals)
        c_carbs = sum(m.total_carbs for m in meals)
        c_fat = sum(m.total_fat for m in meals)

        def pct(v, g): return round(v / g * 100) if g else 0

        return {
            "meals_logged": len(meals),
            "consumed": {
                "calories": round(c_cal, 1),
                "protein": round(c_prot, 1),
                "carbs": round(c_carbs, 1),
                "fat": round(c_fat, 1),
            },
            "goals": {
                "calories": profile.daily_calories,
                "protein": profile.daily_protein,
                "carbs": profile.daily_carbs,
                "fat": profile.daily_fat,
            },
            "percentage": {
                "calories": pct(c_cal, profile.daily_calories),
                "protein": pct(c_prot, profile.daily_protein),
                "carbs": pct(c_carbs, profile.daily_carbs),
                "fat": pct(c_fat, profile.daily_fat),
            },
            "meals": [
                {
                    "description": m.description,
                    "calories": m.total_calories,
                    "protein": m.total_protein,
                    "carbs": m.total_carbs,
                    "fat": m.total_fat,
                }
                for m in meals
            ],
        }

    def _tool_get_meal_history(self, profile_id: int, limite: int = 10) -> Dict:
        """Get recent meal history."""
        meals = self.meal_repo.get_by_profile(profile_id, limit=min(limite, 20))
        return {
            "total": len(meals),
            "meals": [
                {
                    "description": m.description,
                    "calories": m.total_calories,
                    "protein": m.total_protein,
                    "carbs": m.total_carbs,
                    "fat": m.total_fat,
                    "date": m.created_at.isoformat() if m.created_at else None,
                }
                for m in meals
            ],
        }

    def get_history(self, profile_id: int) -> Dict[str, Any]:
        try:
            messages = self.chat_repo.get_by_profile(profile_id, limit=50)
            return {
                "success": True,
                "data": [
                    {
                        "role": m.role,
                        "content": m.content,
                        "created_at": m.created_at.isoformat()
                        if m.created_at
                        else None,
                    }
                    for m in messages
                ],
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def clear_history(self, profile_id: int) -> Dict[str, Any]:
        try:
            self.chat_repo.delete_by_profile(profile_id)
            return {"success": True, "message": "Chat history cleared"}
        except Exception as e:
            return {"success": False, "error": str(e)}
