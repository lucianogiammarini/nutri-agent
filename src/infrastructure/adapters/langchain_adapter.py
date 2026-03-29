"""
Adapter - LangChain generic adapter for vision analysis and chat (RAG synthesis).
"""

import json
import base64
import time
import logging
import io
from PIL import Image
from typing import Dict, Any, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_core.language_models.chat_models import BaseChatModel
from src.domain.llm_adapter_interface import ILlmAdapter
from src.domain.food_api_interface import IFoodAPI

logger = logging.getLogger(__name__)

# ── Prompts and Definitions ────────────────────────────────────────

VISION_SYSTEM_PROMPT = """Eres un nutricionista experto en visión artificial y lector de etiquetas (OCR).
Analiza la imagen enviada. Detecta si es un PLATO DE COMIDA o una TABLA NUTRICIONAL (etiqueta).

Si es un PLATO DE COMIDA (meal):
Devuelve ÚNICAMENTE un JSON estructurado así (sin markdown, sin extras):
{
  "image_type": "meal",
  "reasoning": "Breve explicación de cómo estimaste cada porción (ej: 'Presa de pollo que ocupa 1/4 del plato, aparenta ser muslo mediano...')",
  "description": "Descripción breve del plato en español",
  "food_items": [
    {
      "name": "nombre del alimento en español",
      "name_en": "nombre traducido al INGLÉS para búsqueda en base de datos USDA (ej: 'roasted chicken thigh'). IMPORTANTE: incluir método de cocción (roasted, boiled, fried, steamed, baked, grilled, raw).",
      "quantity": 150,
      "unit": "g"
    }
  ],
  "nutrition_facts": null
}
REGLAS PARA PLATO:
- Identifica los alimentos y estima cantidad/unidad. NO calcules calorías ni macronutrientes manualmente.
- En "name_en" SIEMPRE incluí el método de cocción (roasted, boiled, fried, baked, steamed, grilled). Si no es evidente, asumir "cooked".
- Sé consistente: ante la misma imagen, siempre debés devolver la misma descomposición de alimentos y porciones.

Si es una TABLA NUTRICIONAL (label):
Extrae los valores matemáticamente exactos mediante OCR. Si los valores son por porción, extrae los valores POR PORCIÓN (o regla de tres si la cantidad consumida es diferente a una porción y el usuario lo aclaró).
Devuelve ÚNICAMENTE este JSON (sin markdown, sin extras):
{
  "image_type": "label",
  "reasoning": "Breve explicación de la lectura OCR",
  "description": "Tabla Nutricional de [Producto]",
  "food_items": [],
  "nutrition_facts": {
    "calories": 250.0,
    "protein": 5.0,
    "carbs": 30.0,
    "fat": 10.0
  }
}

REGLAS GENERALES:
- Usa el comentario del usuario (si hay) para ajustar las porciones leídas o estimadas.
- ESTRICTO: Devuelve ÚNICAMENTE JSON válido, nada antes ni después.
- El campo "reasoning" es OBLIGATORIO.
"""

CHAT_SYSTEM_PROMPT_TEMPLATE = """Eres un agente de intervención metabólica de precisión, 
experto en nutrición y salud basada en las Guías Alimentarias para la Población Argentina (GAPA).

PERFIL DEL USUARIO:
{profile_context}

HERRAMIENTAS DISPONIBLES:
Tenés acceso a herramientas. Usalas cuando sea necesario:
- query_nutrition: para datos nutricionales
- search_food_guide: para buscar recomendaciones
- get_today_summary: para ver el consumo del día
- get_meal_history: para ver comidas recientes

REGLAS OBLIGATORIAS:
1. SIEMPRE usa 'search_food_guide' para preguntas de nutrición general.
2. Usa 'query_nutrition' para alimentos específicos.
3. Usa 'get_today_summary' para el progreso del día.
4. Usa 'get_meal_history' para días anteriores.
"""

CHAT_TOOLS_DEF = [
    {
        "type": "function",
        "function": {
            "name": "query_nutrition",
            "description": "Consulta información nutricional de un alimento en la base de datos de USDA. IMPORTANTE: Debes traducir el alimento al INGLÉS antes de buscarlo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "food_name_en": {
                        "type": "string",
                        "description": "El nombre del alimento traducido al INGLÉS (ej. 'raw chicken breast').",
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
            "name": "search_food_guide",
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
            "name": "get_today_summary",
            "description": "Obtiene el resumen de macronutrientes consumidos hoy.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_meal_history",
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


class LangChainAdapter(ILlmAdapter):
    """
    Handles communication with LangChain models for:
    - Food image analysis (Vision)
    - Direct nutrition enrichment via injected food API (parallel)
    - RAG-powered nutritional chat (Chat Completions)
    """

    def __init__(self, chat_model: BaseChatModel):
        self.chat_model = chat_model
        self._food_api = None  # injected later

    def set_food_api(self, food_api: IFoodAPI):
        """Inject the food API adapter for nutrition lookups."""
        self._food_api = food_api

    def _extract_text_content(self, content: Any) -> str:
        """Extracts combined text from message content (handles both str and list of parts)."""
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            texts = []
            for item in content:
                if isinstance(item, str):
                    texts.append(item)
                elif isinstance(item, dict) and item.get("type") == "text":
                    texts.append(item.get("text", ""))
                # Skip other types like tool_use or image_url in output content if they exist
            return "".join(texts).strip()
        return str(content or "").strip()

    # ── Vision: Helpers ─────────────────────────────────────

    def _encode_image(self, image_path: str) -> tuple[str, str]:
        """Compresses and base64 encodes the image."""
        t0 = time.time()
        try:
            img = Image.open(image_path)
            img.thumbnail((1024, 1024))
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            mime = "image/jpeg"
            logger.info(
                "[analyze] Imagen comprimida %dx%d → JPEG 1024px: %.2fs",
                img.width,
                img.height,
                time.time() - t0,
            )
            return b64, mime
        except Exception as exc:
            logger.warning(
                "[analyze] Compresión falló (%s), enviando imagen original", exc
            )
            with open(image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            ext = image_path.rsplit(".", 1)[-1].lower()
            mime = {
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
                "png": "image/png",
                "webp": "image/webp",
                "avif": "image/avif",
            }.get(ext, "image/jpeg")
            logger.info(
                "[analyze] Codificación de imagen (sin comprimir): %.2fs",
                time.time() - t0,
            )
            return b64, mime

    def _parse_vision_json(self, raw_vision: str) -> Dict[str, Any]:
        """Cleans markdown format and parses the vision API JSON response."""
        cleaned = raw_vision
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning(
                "[analyze] JSON parse falló. Respuesta cruda: %s", raw_vision[:200]
            )
            return {}

    def _handle_label_ocr(
        self, vision_result: Dict[str, Any], raw_vision: str
    ) -> Dict[str, Any]:
        """Formats the result when the image is a Nutrition Label (OCR)."""
        facts = vision_result.get("nutrition_facts") or {}
        desc = vision_result.get("description", "Producto Envasado (OCR)")

        item = {
            "name": desc,
            "name_en": "Packaged Product",
            "portion": "Etiqueta OCR",
            "estimated_calories": float(facts.get("calories", 0) or 0),
            "estimated_protein": float(facts.get("protein", 0) or 0),
            "estimated_carbs": float(facts.get("carbs", 0) or 0),
            "estimated_fat": float(facts.get("fat", 0) or 0),
            "enriched_source": "nutrition_label_ocr",
        }

        return {
            "image_type": "label",
            "description": desc,
            "food_items": [item],
            "total_calories": round(item["estimated_calories"], 1),
            "total_protein": round(item["estimated_protein"], 1),
            "total_carbs": round(item["estimated_carbs"], 1),
            "total_fat": round(item["estimated_fat"], 1),
            "_raw": raw_vision,
        }

    def _handle_meal_enrichment(
        self, vision_result: Dict[str, Any], raw_vision: str, on_progress: Any = None
    ) -> Dict[str, Any]:
        """Enriches the food items directly using USDA if the image is a meal."""
        food_items = vision_result.get("food_items", [])
        if not food_items:
            vision_result["_raw"] = raw_vision
            vision_result.update(
                {
                    "image_type": "meal",
                    "total_calories": 0,
                    "total_protein": 0,
                    "total_carbs": 0,
                    "total_fat": 0,
                }
            )
            return vision_result

        t3 = time.time()
        if self._food_api:
            if on_progress:
                on_progress({"type": "thinking", "label": "Consultando base de datos nutricional USDA...", "detail": f"Analizando {len(food_items)} alimentos"})
            enriched_items = self._food_api.enrich_food_items_parallel(food_items)
        else:
            enriched_items = food_items
            for item in enriched_items:
                for k in (
                    "estimated_calories",
                    "estimated_protein",
                    "estimated_carbs",
                    "estimated_fat",
                ):
                    item.setdefault(k, 0)
                item["enriched_source"] = "not_available"

        logger.info(
            "[analyze] Phase 2 — USDA (directo, paralelo): %.2fs", time.time() - t3
        )

        total_cal = sum(i.get("estimated_calories", 0) for i in enriched_items)
        total_prot = sum(i.get("estimated_protein", 0) for i in enriched_items)
        total_carbs = sum(i.get("estimated_carbs", 0) for i in enriched_items)
        total_fat = sum(i.get("estimated_fat", 0) for i in enriched_items)

        return {
            "image_type": "meal",
            "description": vision_result.get("description", ""),
            "food_items": enriched_items,
            "total_calories": round(total_cal, 1),
            "total_protein": round(total_prot, 1),
            "total_carbs": round(total_carbs, 1),
            "total_fat": round(total_fat, 1),
            "_raw": raw_vision,
        }

    # ── Vision: Analyze food image ──────────────────────────────────

    def analyze_food_image(
        self, image_path: str, user_comment: str = "", on_progress: Any = None
    ) -> Dict[str, Any]:
        """
        Two-phase analysis (optimized):
        1. Vision (detail=high) identifies foods/labels.
        2. Routing: direct OCR return or parallel enrichment via food API.
        """
        t_total = time.time()
        if user_comment:
            logger.info("[analyze] Comentario del usuario: '%s'", user_comment)

        if on_progress:
            on_progress({"type": "thinking", "label": "Comprimiendo y codificando imagen...", "detail": ""})
        b64, mime = self._encode_image(image_path)

        user_text = "Analiza la siguiente imagen y extrae los datos correspondientes según sea plato o etiqueta:"
        if user_comment:
            user_text += f'\n\nComentario del usuario: "{user_comment}"'

        t1 = time.time()
        messages = [
            SystemMessage(content=VISION_SYSTEM_PROMPT),
            HumanMessage(
                content=[
                    {"type": "text", "text": user_text},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime};base64,{b64}",
                            "detail": "high",
                        },
                    },
                ]
            ),
        ]

        if on_progress:
            on_progress({"type": "thinking", "label": "Analizando imagen con visión artificial...", "detail": "Identificando platos o etiquetas"})
        response = self.chat_model.invoke(messages)
        logger.info("[analyze] Phase 1 — Vision API: %.2fs", time.time() - t1)

        raw_vision = self._extract_text_content(response.content)
        t2 = time.time()

        if on_progress:
            on_progress({"type": "thinking", "label": "Extrayendo y procesando información...", "detail": ""})
        vision_result = self._parse_vision_json(raw_vision)
        logger.info("[analyze] Parsing JSON de Vision: %.4fs", time.time() - t2)

        if not vision_result:
            return {
                "image_type": "meal",
                "description": raw_vision,
                "food_items": [],
                "total_calories": 0,
                "total_protein": 0,
                "total_carbs": 0,
                "total_fat": 0,
                "_raw": raw_vision,
            }

        image_type = vision_result.get("image_type", "meal")

        if image_type == "label":
            if on_progress:
                on_progress({"type": "thinking", "label": "Extrayendo datos de la etiqueta nutricional...", "detail": "OCR completado"})
            result = self._handle_label_ocr(vision_result, raw_vision)
        else:
            result = self._handle_meal_enrichment(vision_result, raw_vision, on_progress=on_progress)

        logger.info(
            "[analyze] Análisis completo finalizado: %.2fs", time.time() - t_total
        )
        return result

    # ── Chat: Helpers ─────────────────────────────────────────────

    def _build_chat_messages(
        self,
        user_message: str,
        profile_context: str,
        chat_history: List[Dict[str, str]],
    ) -> List[Any]:
        """Arranges the system prompt, history, and current user question into Langchain Messages."""
        system_prompt = CHAT_SYSTEM_PROMPT_TEMPLATE.format(
            profile_context=profile_context
        )
        messages: List[Any] = [SystemMessage(content=system_prompt)]

        if chat_history:
            for msg in chat_history[-10:]:
                if msg.get("role") == "user":
                    messages.append(HumanMessage(content=msg.get("content", "")))
                else:
                    messages.append(AIMessage(content=msg.get("content", "")))

        messages.append(HumanMessage(content=user_message))
        return messages

    def _execute_chat_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        handlers: Dict[str, Any],
    ) -> str:
        """Executes a requested tool function and returns the JSON stringified result."""
        handler = handlers.get(name)
        if not handler:
            return json.dumps({"error": f"Tool '{name}' not available"})

        try:
            result = handler(**arguments)
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception as e:
            logger.warning("[chat] Tool '%s' error: %s", name, e)
            return json.dumps({"error": str(e)})

    # ── Chat: RAG synthesis with Tool Calling ─────────────────────

    def chat_with_context(
        self,
        user_message: str,
        profile_context: str,
        chat_history: List[Dict[str, str]] = None,
        tool_handlers: Dict[str, Any] = None,
        mcp_tools: Optional[List[Any]] = None,
        on_progress: Any = None,
    ) -> str:
        """
        Chat with tool calling using LangChain's bind_tools.
        """
        t0 = time.time()
        # Combine base tools with MCP tools if any
        all_tools = list(CHAT_TOOLS_DEF)
        if mcp_tools:
            all_tools.extend(mcp_tools)

        llm_with_tools = self.chat_model.bind_tools(all_tools)
        messages = self._build_chat_messages(
            user_message, profile_context, chat_history or []
        )

        max_rounds = 3
        round_count = 0
        tools_used = []

        logger.info("[chat] Enviando mensaje: '%s'", user_message[:80])

        if on_progress:
            on_progress({"type": "thinking", "label": "Analizando tu pregunta...", "detail": ""})

        response_msg = llm_with_tools.invoke(messages)

        while response_msg.tool_calls and round_count < max_rounds:
            round_count += 1
            messages.append(response_msg)

            for tool_call in response_msg.tool_calls:
                fn_name = tool_call["name"]
                args = tool_call["args"]

                if on_progress:
                    on_progress({"type": "tool_start", "label": f"Consultando: {fn_name}", "detail": list(args.values())[0] if args else ""})

                t_tool = time.time()
                # 1. Try internal handlers
                if tool_handlers and fn_name in tool_handlers:
                    result_str = self._execute_chat_tool(fn_name, args, tool_handlers)
                # 2. Try MCP tools
                elif mcp_tools:
                    mcp_tool = next((t for t in mcp_tools if t.name == fn_name), None)
                    if mcp_tool:
                        try:
                            res = mcp_tool.invoke(args)
                            result_str = json.dumps(
                                res, ensure_ascii=False, default=str
                            )
                        except Exception as e:
                            result_str = json.dumps({"error": str(e)})
                    else:
                        result_str = json.dumps(
                            {"error": f"Tool '{fn_name}' not found"}
                        )
                else:
                    result_str = json.dumps(
                        {"error": f"Tool '{fn_name}' not available"}
                    )
                
                logger.info("[chat]   Tool '%s' → %.2fs", fn_name, time.time() - t_tool)

                if on_progress:
                    on_progress({"type": "tool_end", "label": f"Listo: {fn_name}", "detail": f"{time.time() - t_tool:.1f}s"})

                tools_used.append(fn_name)

                messages.append(
                    ToolMessage(
                        tool_call_id=tool_call["id"], content=result_str, name=fn_name
                    )
                )

            # Re-invoke the LLM with the new messages containing the execution results
            if on_progress:
                on_progress({"type": "synthesizing", "label": "Sintetizando respuesta...", "detail": ""})
            response_msg = llm_with_tools.invoke(messages)

        logger.info(
            "[chat] ✅ Respuesta generada (%.2fs, %d rondas, tools: %s)",
            time.time() - t0,
            round_count,
            tools_used or "ninguna",
        )

        final_text = self._extract_text_content(response_msg.content)

        if not final_text:
            logger.warning(
                "[chat] El LLM devolvió texto vacío tras %d rondas. Retornando fallback.",
                round_count,
            )
            final_text = "Lo siento, intenté buscar esa información pero tuve problemas obteniendo los datos exactos. ¿Podrías intentar preguntar de otra forma?"

        return final_text
