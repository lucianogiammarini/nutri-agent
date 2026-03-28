from abc import ABC, abstractmethod
from typing import Dict, Any, List


class ILlmAdapter(ABC):
    """
    Port for interacting with LLM APIs for vision and chat with tools.
    """

    @abstractmethod
    def analyze_food_image(
        self, image_path: str, user_comment: str = ""
    ) -> Dict[str, Any]:
        """Analyzes an image and returns identified food items."""
        pass

    @abstractmethod
    def chat_with_context(
        self,
        user_message: str,
        profile_context: str,
        chat_history: List[Dict[str, str]] = None,
        tool_handlers: Dict[str, Any] = None,
        on_progress: Any = None,
    ) -> str:
        """Handles a conversational turn with the LLM, possibly invoking tools.
        
        Args:
            on_progress: Optional callback to report progress (e.g. tool selection)
        """
        pass
