"""
Adapter - LangChain generic adapter for vision analysis and chat (RAG synthesis).
"""

import os
import json
import base64
import time
import logging
from typing import Dict, Any, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_core.language_models.chat_models import BaseChatModel

logger = logging.getLogger(__name__)


class LangChainAdapter:
    """
    Handles communication with LangChain models for:
    - Food image analysis (Vision)
    - Direct nutrition enrichment via injected food API (parallel)
    - RAG-powered nutritional chat (Chat Completions)
    """

    def __init__(self, chat_model: BaseChatModel):
        self.chat_model = chat_model
        self._food_api = None  # injected later

    def set_food_api(self, food_api):
        """Inject the food API adapter for nutrition lookups."""
        self._food_api = food_api

    # ── Vision: Analyze food image ──────────────────────────────────

    def analyze_food_image(self, image_path: str, user_comment: str = "") -> Dict[str, Any]:
        """
        Two-phase analysis (optimized):
        1. Vision (detail=low) identifies foods and estimates portions.
        2. Open Food Facts queried directly in parallel (no tool-calling overhead).
        """
        t_total = time.time()
        if user_comment:
            logger.info("[analyze] Comentario del usuario: '%s'", user_comment)

        # ── Compress & encode image ──────────────────────────────
        t0 = time.time()
        try:
            from PIL import Image
            import io
            img = Image.open(image_path)
            img.thumbnail((1024, 1024))
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=80)
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            mime = "image/jpeg"
            logger.info("[analyze] Imagen comprimida %dx%d → JPEG 1024px: %.2fs",
                        img.width, img.height, time.time() - t0)
        except Exception as exc:
            logger.warning("[analyze] Compresión falló (%s), enviando imagen original", exc)
            with open(image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            ext = image_path.rsplit(".", 1)[-1].lower()
            mime = {
                "jpg": "image/jpeg", "jpeg": "image/jpeg",
                "png": "image/png", "webp": "image/webp",
                "avif": "image/avif",
            }.get(ext, "image/jpeg")
            logger.info("[analyze] Codificación de imagen (sin comprimir): %.2fs", time.time() - t0)

        system_prompt = """Eres un nutricionista experto con visión artificial.
Analiza la imagen del plato de comida. Tu ÚNICA tarea es identificar los alimentos y estimar sus porciones (cantidad y unidad). NO calcules calorías ni macronutrientes.

Devuelve ÚNICAMENTE un JSON válido (sin markdown, sin ```) con esta estructura:
{
  "description": "Descripción breve del plato en español",
  "food_items": [
    {
      "name": "nombre del alimento en español",
      "name_en": "nombre traducido al INGLÉS (ej: 'raw chicken breast')",
      "quantity": 150,
      "unit": "g"
    }
  ]
}

Reglas:
- Estima las cantidades lo más preciso posible basándote en el tamaño visual.
- Incluye TODOS los componentes visibles del plato.
- Usa unidades en gramos (g) siempre que sea posible.
- IMPORTANTÍSIMO: NO incluyas calorías ni macronutrientes.
- IMPORTANTE: Si el usuario incluye un comentario (ej: 'comí la mitad'), ajusta las cantidades reflejando el comentario real consumido."""

        user_text = "Identifica los alimentos y estima las porciones de este plato:"
        if user_comment:
            user_text += f"\n\nComentario del usuario: \"{user_comment}\""

        # ── Phase 1: Vision API call ─
        t1 = time.time()
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(
                content=[
                    {"type": "text", "text": user_text},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "high"},
                    },
                ]
            )
        ]

        response = self.chat_model.invoke(messages)
        logger.info("[analyze] Phase 1 — Vision API (identificar alimentos): %.2fs", time.time() - t1)

        raw_vision = response.content.strip()

        # ── Parse JSON ──────────────────────────────────────────
        t2 = time.time()
        cleaned = raw_vision
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

        try:
            vision_result = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("[analyze] JSON parse falló. Respuesta cruda: %s", raw_vision[:200])
            return {
                "description": raw_vision,
                "food_items": [],
                "total_calories": 0, "total_protein": 0,
                "total_carbs": 0, "total_fat": 0,
                "_raw": raw_vision,
            }
        logger.info("[analyze] Parsing JSON de Vision: %.4fs", time.time() - t2)

        food_items = vision_result.get("food_items", [])

        if not food_items:
            vision_result["_raw"] = raw_vision
            vision_result.update({"total_calories": 0, "total_protein": 0, "total_carbs": 0, "total_fat": 0})
            return vision_result

        # ── Phase 2: Direct parallel enrichment (no tool-calling) ──
        t3 = time.time()
        if self._food_api:
            enriched_items = self._food_api.enrich_food_items_parallel(food_items)
        else:
            enriched_items = food_items
            for item in enriched_items:
                item.setdefault("estimated_calories", 0)
                item.setdefault("estimated_protein", 0)
                item.setdefault("estimated_carbs", 0)
                item.setdefault("estimated_fat", 0)
                item["enriched_source"] = "not_available"
        logger.info("[analyze] Phase 2 — Open Food Facts (directo, paralelo): %.2fs", time.time() - t3)

        total_cal = sum(i.get("estimated_calories", 0) for i in enriched_items)
        total_prot = sum(i.get("estimated_protein", 0) for i in enriched_items)
        total_carbs = sum(i.get("estimated_carbs", 0) for i in enriched_items)
        total_fat = sum(i.get("estimated_fat", 0) for i in enriched_items)

        return {
            "description": vision_result.get("description", ""),
            "food_items": enriched_items,
            "total_calories": round(total_cal, 1),
            "total_protein": round(total_prot, 1),
            "total_carbs": round(total_carbs, 1),
            "total_fat": round(total_fat, 1),
            "_raw": raw_vision,
        }

    # ── Chat: RAG synthesis with Tool Calling ─────────────────────

    def chat_with_context(
        self,
        user_message: str,
        profile_context: str,
        chat_history: List[Dict[str, str]] = None,
        tool_handlers: Dict[str, Any] = None,
    ) -> str:
        """
        Chat with tool calling using LangChain's bind_tools.
        """
        t0 = time.time()

        system_prompt = f"""Eres un agente de intervención metabólica de precisión, 
experto en nutrición y salud basada en las Guías Alimentarias para la Población Argentina (GAPA).

PERFIL DEL USUARIO:
{profile_context}

HERRAMIENTAS DISPONIBLES:
Tenés acceso a herramientas. Usalas cuando sea necesario:
- consultar_nutricion: para datos nutricionales
- buscar_guia_alimentaria: para buscar recomendaciones
- obtener_resumen_hoy: para ver el consumo del día
- obtener_historial_comidas: para ver comidas recientes

REGLAS OBLIGATORIAS:
1. SIEMPRE usa 'buscar_guia_alimentaria' para preguntas de nutrición general.
2. Usa 'consultar_nutricion' para alimentos específicos.
3. Usa 'obtener_resumen_hoy' para el progreso del día.
4. Usa 'obtener_historial_comidas' para días anteriores.
"""

        CHAT_TOOLS = [
            {
                "type": "function",
                "function": {
                    "name": "consultar_nutricion",
                    "description": "Consulta información nutricional de un alimento en la base de datos de USDA. IMPORTANTE: Debes traducir el alimento al INGLÉS antes de buscarlo.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "food_name_en": {
                                "type": "string",
                                "description": "El nombre del alimento traducido al INGLÉS (ej. 'raw chicken breast')."
                            },
                            "quantity": {"type": "number"},
                            "unit": {"type": "string"},
                        },
                        "required": ["food_name_en", "quantity", "unit"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "buscar_guia_alimentaria",
                    "description": "Busca información en las Guías Alimentarias para la Población Argentina.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "consulta": {"type": "string"},
                        },
                        "required": ["consulta"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "obtener_resumen_hoy",
                    "description": "Obtiene el resumen de macronutrientes consumidos hoy.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "obtener_historial_comidas",
                    "description": "Obtiene historial de comidas recientes.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limite": {"type": "integer"},
                        },
                    },
                },
            },
        ]

        llm_with_tools = self.chat_model.bind_tools(CHAT_TOOLS)

        messages = [SystemMessage(content=system_prompt)]

        if chat_history:
            for msg in chat_history[-10:]:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                else:
                    messages.append(AIMessage(content=msg["content"]))

        messages.append(HumanMessage(content=user_message))

        max_rounds = 3
        round_count = 0
        tools_used = []

        logger.info("[chat] Enviando mensaje: '%s'", user_message[:80])
        response_msg = llm_with_tools.invoke(messages)

        while response_msg.tool_calls and round_count < max_rounds:
            round_count += 1
            messages.append(response_msg)
            
            for tool_call in response_msg.tool_calls:
                fn_name = tool_call["name"]
                args = tool_call["args"]

                t_tool = time.time()
                result_str = self._execute_chat_tool(fn_name, args, tool_handlers or {})
                logger.info("[chat]   Tool '%s' → %.2fs", fn_name, time.time() - t_tool)
                tools_used.append(fn_name)

                messages.append(ToolMessage(
                    tool_call_id=tool_call["id"],
                    content=result_str,
                    name=fn_name
                ))

            response_msg = llm_with_tools.invoke(messages)

        logger.info("[chat] ✅ Respuesta generada (%.2fs, %d rondas, tools: %s)",
                     time.time() - t0, round_count, tools_used or "ninguna")

        final_text = str(response_msg.content).strip()
        if not final_text:
            logger.warning("[chat] El LLM devolvió texto vacío tras %d rondas. Retornando fallback.", round_count)
            final_text = "Lo siento, intenté buscar esa información pero tuve problemas obteniendo los datos exactos. ¿Podrías intentar preguntar de otra forma?"

        return final_text

    def _execute_chat_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        handlers: Dict[str, Any],
    ) -> str:
        handler = handlers.get(name)
        if not handler:
            return json.dumps({"error": f"Tool '{name}' not available"})

        try:
            result = handler(**arguments)
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception as e:
            logger.warning("[chat] Tool '%s' error: %s", name, e)
            return json.dumps({"error": str(e)})
