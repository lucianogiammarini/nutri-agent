"""
Utility - Error mapper for LLM-related exceptions.
Maps technical errors to user-friendly Spanish messages.
"""

import logging

logger = logging.getLogger(__name__)


def map_llm_error(exception: Exception, context_prefix: str = "Error") -> str:
    """
    Analyzes an exception and returns a user-friendly Spanish message.
    
    Common technical strings:
    - RESOURCE_EXHAUSTED / 429: Quota exceeded
    - SAFETY: Content filters
    - INVALID_ARGUMENT / 400: Bad request
    - DEADLINE_EXCEEDED / 504: Timeout
    - UNAVAILABLE / 503: Service down
    """
    error_str = str(exception)
    
    # 1. 429 RESOURCE_EXHAUSTED (Quota)
    if "RESOURCE_EXHAUSTED" in error_str or "429" in error_str:
        return "Se ha superado la cuota de uso de la Inteligencia Artificial. Por favor, espera unos minutos antes de intentar de nuevo."
    
    # 2. SAFETY (Content Filtering)
    if "SAFETY" in error_str or "blocked" in error_str.lower():
        return "Tu mensaje fue filtrado por políticas de seguridad del modelo. Por favor, intenta de nuevo reformulando tu consulta."
    
    # 3. DEADLINE_EXCEEDED (Timeout)
    if "DEADLINE_EXCEEDED" in error_str or "timeout" in error_str.lower():
        return "El modelo tardó demasiado en responder. Por favor, intenta de nuevo."
    
    # 4. UNAVAILABLE (Service Down)
    if "UNAVAILABLE" in error_str or "503" in error_str:
        return "El servicio de IA no se encuentra disponible temporalmente. Por favor, intenta de nuevo en unos momentos."
    
    # 5. INVALID_ARGUMENT (Schema issues, too many tokens, etc.)
    if "INVALID_ARGUMENT" in error_str or "400" in error_str:
        return "Hubo un problema con la solicitud al modelo. Por favor, verifica tu mensaje o imagen e intenta de nuevo."
    
    # Default (fallback)
    logger.error(f"[ErrorMapper] Original error was: {error_str}")
    return f"{context_prefix}: Ocurrió un error inesperado al procesar tu solicitud con la IA."
