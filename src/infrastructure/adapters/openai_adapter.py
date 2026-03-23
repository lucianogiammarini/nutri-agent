"""
Adapter - OpenAI API for vision analysis and chat (RAG synthesis).

Pipeline optimizado:
  Phase 1: Vision (detail=low) identifica alimentos + porciones
  Phase 2: Open Food Facts directo + paralelo (sin tool-calling intermedio)
"""

import os
import json
import base64
import time
import logging
from typing import Dict, Any, List, Optional

from openai import OpenAI

logger = logging.getLogger(__name__)


class OpenAIAdapter:
    """
    Handles communication with OpenAI API for:
    - Food image analysis (Vision) — only identifies foods & portions
    - Direct nutrition enrichment via injected food API (parallel)
    - RAG-powered nutritional chat (Chat Completions)
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model
        self._client = None
        self._food_api = None  # injected later

    def set_food_api(self, food_api):
        """Inject the food API adapter for nutrition lookups."""
        self._food_api = food_api

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            if not self.api_key:
                raise ValueError(
                    "OPENAI_API_KEY not configured. "
                    "Set it in your .env file or environment variables."
                )
            self._client = OpenAI(api_key=self.api_key)
        return self._client

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
            # Convert to RGB (JPEG doesn't support RGBA/P/LA)
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=80)
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            mime = "image/jpeg"
            logger.info("[analyze] Imagen comprimida %dx%d → JPEG 1024px: %.2fs",
                        img.width, img.height, time.time() - t0)
        except Exception as exc:
            # Pillow not installed or image format not supported — send raw file
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

        # Phase 1: Vision — identify foods and estimate portions ONLY
        system_prompt = """Eres un nutricionista experto con visión artificial.
Analiza la imagen del plato de comida. Tu ÚNICA tarea es identificar los alimentos
y estimar sus porciones (cantidad y unidad). NO calcules calorías ni macronutrientes.

Devuelve ÚNICAMENTE un JSON válido (sin markdown, sin ```) con esta estructura:
{
  "description": "Descripción breve del plato en español",
  "food_items": [
    {
      "name": "nombre del alimento en español",
      "quantity": 150,
      "unit": "g"
    }
  ]
}

Reglas:
- Estima las cantidades lo más preciso posible basándote en el tamaño visual.
- Incluye TODOS los componentes visibles del plato.
- Usa unidades en gramos (g) siempre que sea posible.
- No incluyas calorías, proteínas, ni macronutrientes.
- IMPORTANTE: Si el usuario incluye un comentario (ej: "comí la mitad", "solo 2 porciones"),
  AJUSTA las cantidades según ese comentario. Por ejemplo, si la foto muestra una pizza
  entera pero el usuario dice "comí 2 porciones", reporta solo las 2 porciones consumidas.
  Refleja el ajuste en la descripción."""

        # Build user message with optional comment
        user_text = "Identifica los alimentos y estima las porciones de este plato:"
        if user_comment:
            user_text += f"\n\nComentario del usuario: \"{user_comment}\""

        # ── Phase 1: Vision API call (detail=high for ingredient-level accuracy) ─
        t1 = time.time()
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime};base64,{b64}",
                                "detail": "high",
                            },
                        },
                    ],
                },
            ],
            max_tokens=800,
            temperature=0.3,
        )
        logger.info("[analyze] Phase 1 — Vision API (identificar alimentos): %.2fs", time.time() - t1)

        raw_vision = response.choices[0].message.content.strip()

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
        logger.info("[analyze] Alimentos identificados: %d → %s",
                     len(food_items),
                     [f"{i.get('name')} ({i.get('quantity')}{i.get('unit')})" for i in food_items])

        if not food_items:
            vision_result["_raw"] = raw_vision
            vision_result.update({"total_calories": 0, "total_protein": 0, "total_carbs": 0, "total_fat": 0})
            logger.info("[analyze] Sin alimentos detectados. Total: %.2fs", time.time() - t_total)
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

        # Calculate totals
        total_cal = sum(i.get("estimated_calories", 0) for i in enriched_items)
        total_prot = sum(i.get("estimated_protein", 0) for i in enriched_items)
        total_carbs = sum(i.get("estimated_carbs", 0) for i in enriched_items)
        total_fat = sum(i.get("estimated_fat", 0) for i in enriched_items)

        logger.info("[analyze] Totales → %dkcal | P:%.1fg | C:%.1fg | G:%.1fg",
                     total_cal, total_prot, total_carbs, total_fat)
        logger.info("[analyze] ✅ Pipeline completo: %.2fs", time.time() - t_total)

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

    # Tool definitions for the chat agent
    CHAT_TOOLS = [
        {
            "type": "function",
            "function": {
                "name": "consultar_nutricion",
                "description": (
                    "Consulta la información nutricional (calorías, proteínas, carbohidratos, "
                    "grasas y micronutrientes) de un alimento específico con cantidad y unidad. "
                    "Usar cuando el usuario pregunta por datos nutricionales de un alimento que NO "
                    "está en sus comidas registradas."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "food_name": {"type": "string", "description": "Nombre del alimento en español"},
                        "quantity": {"type": "number", "description": "Cantidad del alimento"},
                        "unit": {"type": "string", "description": "Unidad de medida: 'g', 'ml', 'taza', etc."},
                    },
                    "required": ["food_name", "quantity", "unit"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "buscar_guia_alimentaria",
                "description": (
                    "Busca información en las Guías Alimentarias para la Población Argentina (GAPA). "
                    "Usar cuando el usuario hace preguntas sobre nutrición, hábitos alimentarios, "
                    "recomendaciones dietarias, o necesitás fundamentar un consejo con fuentes confiables."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "consulta": {
                            "type": "string",
                            "description": "Texto de búsqueda sobre el tema nutricional a consultar en las GAPA",
                        },
                    },
                    "required": ["consulta"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "obtener_resumen_hoy",
                "description": (
                    "Obtiene el resumen de macronutrientes consumidos hoy por el usuario: "
                    "calorías, proteínas, carbohidratos, grasas, y las comidas registradas. "
                    "Usar cuando el usuario pregunta sobre su progreso del día, sus macros, "
                    "o si ya alcanzó sus metas."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "obtener_historial_comidas",
                "description": (
                    "Obtiene el historial de comidas recientes del usuario con detalles nutricionales. "
                    "Usar cuando el usuario pregunta qué comió ayer, los últimos días, "
                    "o quiere analizar tendencias en su alimentación."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limite": {
                            "type": "integer",
                            "description": "Cantidad máxima de comidas a retornar (default 10)",
                        },
                    },
                },
            },
        },
    ]

    def chat_with_context(
        self,
        user_message: str,
        profile_context: str,
        chat_history: List[Dict[str, str]] = None,
        tool_handlers: Dict[str, Any] = None,
    ) -> str:
        """
        Chat with tool calling. The model decides which tools to invoke
        based on the user's question. Available tools:
        - consultar_nutricion: Open Food Facts lookup
        - buscar_guia_alimentaria: RAG search on GAPA corpus
        - obtener_resumen_hoy: today's macro summary
        - obtener_historial_comidas: recent meal history
        """
        t0 = time.time()

        system_prompt = f"""Eres un agente de intervención metabólica de precisión, 
experto en nutrición y salud basada en las Guías Alimentarias para la Población Argentina (GAPA).

PERFIL DEL USUARIO:
{profile_context}

HERRAMIENTAS DISPONIBLES:
Tenés acceso a herramientas para consultar información en tiempo real. Usalas cuando sea
necesario para dar respuestas precisas:
- consultar_nutricion: para datos nutricionales de alimentos específicos
- buscar_guia_alimentaria: para buscar recomendaciones en las GAPA
- obtener_resumen_hoy: para ver el consumo de macronutrientes del día
- obtener_historial_comidas: para ver comidas recientes del usuario

REGLAS OBLIGATORIAS:
1. Para CUALQUIER pregunta sobre nutrición, alimentación, salud, dieta, hidratación, 
   vitaminas, minerales, o recomendaciones alimentarias, SIEMPRE debés usar la herramienta
   'buscar_guia_alimentaria' para fundamentar tu respuesta con las GAPA.
   NO respondas de tu conocimiento general, usá siempre la herramienta primero.
2. Si el usuario pregunta sobre un alimento específico (calorías, macros), usá 'consultar_nutricion'.
3. Si el usuario pregunta sobre su progreso del día o sus macros, usá 'obtener_resumen_hoy'.
4. Si el usuario pregunta qué comió o sobre días anteriores, usá 'obtener_historial_comidas'.
5. Solo para saludos, agradecimientos o aclaraciones simples respondé sin herramientas.

INSTRUCCIONES DE RESPUESTA:
- Responde en español, de forma clara y empática.
- Citá las GAPA como fuente cuando uses información de buscar_guia_alimentaria.
- Si el usuario menciona síntomas, consultá su resumen del día para correlacionar.
- Sé conciso pero completo."""

        messages = [{"role": "system", "content": system_prompt}]

        if chat_history:
            for msg in chat_history[-10:]:
                messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": user_message})

        # Initial call with tools
        logger.info("[chat] Enviando mensaje: '%s'", user_message[:80])
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=self.CHAT_TOOLS,
            tool_choice="auto",
            max_tokens=1000,
            temperature=0.7,
        )

        message = response.choices[0].message

        if not message.tool_calls:
            logger.info("[chat] Modelo respondió sin tools (respuesta directa)")
        

        # Tool calling loop (max 3 rounds)
        max_rounds = 3
        round_count = 0
        tools_used = []

        while message.tool_calls and round_count < max_rounds:
            round_count += 1
            messages.append(message)

            logger.info("[chat] Ronda %d: %d tool calls", round_count, len(message.tool_calls))

            for tool_call in message.tool_calls:
                fn_name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                t_tool = time.time()
                result_str = self._execute_chat_tool(fn_name, args, tool_handlers or {})
                logger.info("[chat]   Tool '%s' → %.2fs", fn_name, time.time() - t_tool)
                tools_used.append(fn_name)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result_str,
                })

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.CHAT_TOOLS,
                tool_choice="auto",
                max_tokens=1000,
                temperature=0.7,
            )
            message = response.choices[0].message

        logger.info("[chat] ✅ Respuesta generada (%.2fs, %d rondas, tools: %s)",
                     time.time() - t0, round_count, tools_used or "ninguna")

        return message.content.strip() if message.content else ""

    def _execute_chat_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        handlers: Dict[str, Any],
    ) -> str:
        """
        Dispatches a chat tool call to the appropriate handler.
        handlers is a dict of callable functions keyed by tool name.
        """
        handler = handlers.get(name)
        if not handler:
            return json.dumps({"error": f"Tool '{name}' not available"})

        try:
            result = handler(**arguments)
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception as e:
            logger.warning("[chat] Tool '%s' error: %s", name, e)
            return json.dumps({"error": str(e)})
