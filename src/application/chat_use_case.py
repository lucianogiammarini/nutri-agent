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
from src.infrastructure.adapters.langchain_adapter import LangChainAdapter
from src.infrastructure.adapters.openfoodfacts_adapter import OpenFoodFactsAdapter

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
        chat_adapter: LangChainAdapter,
        food_api_adapter: OpenFoodFactsAdapter,
        mcp_sqlite=None,
    ):
        self.profile_repo = profile_repository
        self.meal_repo = meal_repository
        self.vector_repo = vector_repository
        self.chat_repo = chat_repository
        self.chat_adapter = chat_adapter
        self.food_api = food_api_adapter
        self.mcp_sqlite = mcp_sqlite

    def execute(self, profile_id: int, message: str) -> Dict[str, Any]:
        try:
            if not message or not message.strip():
                return {'success': False, 'error': 'Message cannot be empty'}

            # 1. Load profile (always needed — lightweight)
            profile = self.profile_repo.get_by_id(profile_id)
            if not profile:
                return {'success': False, 'error': 'Profile not found'}

            goal_labels = {
                'deficit': 'Déficit calórico / Bajar de peso',
                'maintenance': 'Mantenimiento',
                'muscle_gain': 'Aumento de masa muscular',
            }
            profile_ctx = (
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
            )

            # 5. Save messages
            self.chat_repo.save(ChatMessage(
                user_profile_id=profile_id,
                role="user",
                content=message,
            ))
            self.chat_repo.save(ChatMessage(
                user_profile_id=profile_id,
                role="assistant",
                content=response,
            ))

            return {
                'success': True,
                'data': {
                    'response': response,
                },
            }
        except ValueError as e:
            return {'success': False, 'error': str(e)}
        except Exception as e:
            return {'success': False, 'error': f'Chat error: {str(e)}'}

    def _build_tool_handlers(self, profile_id: int, profile) -> Dict[str, Any]:
        """
        Returns a dict of tool_name -> callable for the OpenAI adapter
        to execute when the model invokes a tool.
        """

        def consultar_nutricion(food_name_en: str, quantity: float = 100, unit: str = "g") -> Dict:
            """Query USDA FoodData Central for nutrition data."""
            result = self.food_api.query_nutrition(food_name_en, quantity, unit)
            if result:
                return {
                    "alimento": result["name"],
                    "cantidad": f"{result['quantity']}{result['unit']}",
                    "calorias": result["calories"],
                    "proteinas": result["protein"],
                    "carbohidratos": result["carbs"],
                    "grasas": result["fat"],
                    "fibra": result.get("fiber", 0),
                    "azucar": result.get("sugar", 0),
                    "fuente": "USDA FoodData Central",
                }
            return {"error": f"No se encontró información nutricional para '{food_name_en}' en USDA"}

        def buscar_guia_alimentaria(consulta: str) -> Dict:
            """RAG search on the GAPA vector DB."""
            logger.info("[chat-tool] buscar_guia_alimentaria('%s')", consulta[:80])
            chunks = self.vector_repo.search(consulta, top_k=6)
            if chunks:
                logger.info("[chat-tool] GAPA: %d fragmentos encontrados", len(chunks))
                return {
                    "resultados": len(chunks),
                    "fragmentos": [
                        {"texto": c.text, "relevancia": round(c.score, 3) if hasattr(c, 'score') else None}
                        for c in chunks
                    ],
                    "fuente": "Guías Alimentarias para la Población Argentina (GAPA)",
                }
            logger.info("[chat-tool] GAPA: sin resultados para '%s'", consulta[:50])
            return {"resultados": 0, "mensaje": "No se encontró información relevante en las GAPA"}

        def obtener_resumen_hoy() -> Dict:
            """Get today's consumed macros vs goals."""
            meals = self.meal_repo.get_today_by_profile(profile_id)
            consumed_cal = sum(m.total_calories for m in meals)
            consumed_prot = sum(m.total_protein for m in meals)
            consumed_carbs = sum(m.total_carbs for m in meals)
            consumed_fat = sum(m.total_fat for m in meals)

            return {
                "comidas_registradas": len(meals),
                "consumido": {
                    "calorias": round(consumed_cal, 1),
                    "proteinas": round(consumed_prot, 1),
                    "carbohidratos": round(consumed_carbs, 1),
                    "grasas": round(consumed_fat, 1),
                },
                "metas": {
                    "calorias": profile.daily_calories,
                    "proteinas": profile.daily_protein,
                    "carbohidratos": profile.daily_carbs,
                    "grasas": profile.daily_fat,
                },
                "porcentaje": {
                    "calorias": round(consumed_cal / profile.daily_calories * 100) if profile.daily_calories else 0,
                    "proteinas": round(consumed_prot / profile.daily_protein * 100) if profile.daily_protein else 0,
                    "carbohidratos": round(consumed_carbs / profile.daily_carbs * 100) if profile.daily_carbs else 0,
                    "grasas": round(consumed_fat / profile.daily_fat * 100) if profile.daily_fat else 0,
                },
                "comidas": [
                    {"descripcion": m.description, "calorias": m.total_calories,
                     "proteinas": m.total_protein, "carbohidratos": m.total_carbs,
                     "grasas": m.total_fat}
                    for m in meals
                ],
            }

        def obtener_historial_comidas(limite: int = 10) -> Dict:
            """Get recent meal history."""
            meals = self.meal_repo.get_by_profile(profile_id, limit=min(limite, 20))
            return {
                "total": len(meals),
                "comidas": [
                    {
                        "descripcion": m.description,
                        "calorias": m.total_calories,
                        "proteinas": m.total_protein,
                        "carbohidratos": m.total_carbs,
                        "grasas": m.total_fat,
                        "fecha": m.created_at.isoformat() if m.created_at else None,
                    }
                    for m in meals
                ],
            }

        return {
            "consultar_nutricion": consultar_nutricion,
            "buscar_guia_alimentaria": buscar_guia_alimentaria,
            "obtener_resumen_hoy": obtener_resumen_hoy,
            "obtener_historial_comidas": obtener_historial_comidas,
        }

    def get_history(self, profile_id: int) -> Dict[str, Any]:
        try:
            messages = self.chat_repo.get_by_profile(profile_id, limit=50)
            return {
                'success': True,
                'data': [
                    {
                        "role": m.role,
                        "content": m.content,
                        "created_at": m.created_at.isoformat() if m.created_at else None,
                    }
                    for m in messages
                ],
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def clear_history(self, profile_id: int) -> Dict[str, Any]:
        try:
            self.chat_repo.delete_by_profile(profile_id)
            return {'success': True, 'message': 'Chat history cleared'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
