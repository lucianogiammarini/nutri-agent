"""
Utility - ModelManager for LLM fallback and availability tracking.
Tracks if models (Gemini, GPT) are available or rate-limited per category (Chat/Vision).
"""

import os
import logging
from typing import Dict, Any, List, Optional
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


class ModelManager:
    """
    Manages model selection and availability (Fallback Strategy) per category.
    Categories: 'chat', 'vision'
    """

    def __init__(self):
        # Configuration - Data Driven
        self._categories = {
            "chat": {
                "active_id": "gemini-3.1-pro-preview",
                "primary_id": "gemini-3.1-pro-preview",
                "fallback_id": "gpt-4o-mini",
                "models": {
                    "gemini-3.1-pro-preview": {
                        "name": "Gemini 3.1 Pro Preview",
                        "available": True,
                        "provider": "google",
                        "id": "gemini-3.1-pro-preview",
                    },
                    "gpt-4o-mini": {
                        "name": "GPT-4o Mini",
                        "available": True,
                        "provider": "openai",
                        "id": "gpt-4o-mini",
                    },
                },
            },
            "vision": {
                "active_id": "gemini-3-flash-preview",
                "primary_id": "gemini-3-flash-preview",
                "fallback_id": "gpt-4o",
                "models": {
                    "gemini-3-flash-preview": {
                        "name": "Gemini 3 Flash",
                        "available": True,
                        "provider": "google",
                        "id": "gemini-3-flash-preview",
                    },
                    "gpt-4o": {
                        "name": "GPT-4o",
                        "available": True,
                        "provider": "openai",
                        "id": "gpt-4o",
                    },
                },
            },
        }

    def get_models_status(self, category: str = "chat") -> List[Dict[str, Any]]:
        """Returns the current status of all managed models for a specific category."""
        if category not in self._categories:
            return []
            
        cat = self._categories[category]
        return [
            {**status, "active": mid == cat["active_id"]}
            for mid, status in cat["models"].items()
        ]

    def get_active_model_id(self, category: str) -> str:
        return self._categories.get(category, {}).get("active_id", "")

    def set_active_model(self, category: str, model_id: str):
        if category in self._categories and model_id in self._categories[category]["models"]:
            self._categories[category]["active_id"] = model_id
            logger.info(f"[ModelManager] Active model for '{category}' set to: {model_id}")

    def mark_exhausted(self, category: str, model_id: str, reason: str = "Quota exceeded (429)"):
        """Marks a model as unavailable and performs automatic fallback if needed."""
        if category in self._categories and model_id in self._categories[category]["models"]:
            self._categories[category]["models"][model_id]["available"] = False
            logger.warning(f"[ModelManager] Model '{model_id}' in '{category}' marked as EXHAUSTED: {reason}")
            
            cat = self._categories[category]
            # Auto-fallback if the exhausted model was active
            if cat["active_id"] == model_id:
                if model_id == cat["primary_id"]:
                    cat["active_id"] = cat["fallback_id"]
                    logger.info(f"[ModelManager] Auto-fallback triggered for '{category}': {model_id} -> {cat['fallback_id']}")
                else:
                    logger.warning(f"[ModelManager] No more fallback models available for '{category}'!")

    def probe_models(self, google_api_key: str, openai_api_key: str):
        """Tests primary Gemini models for both categories at startup."""
        for cat_name, cat_data in self._categories.items():
            primary_id = cat_data["primary_id"]
            model_info = cat_data["models"][primary_id]
            
            if model_info["provider"] == "google" and google_api_key:
                try:
                    logger.info(f"[ModelManager] Probing availability for primary model: {primary_id} ({cat_name})...")
                    probe = ChatGoogleGenerativeAI(
                        model=primary_id,
                        google_api_key=google_api_key,
                        max_retries=0,
                    )
                    probe.invoke([HumanMessage(content="hi")])
                    logger.info(f"[ModelManager] Model {primary_id} is AVAILABLE")
                except Exception as e:
                    err_msg = str(e)
                    if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                        self.mark_exhausted(cat_name, primary_id, "Quota exceeded at startup")
                    else:
                        logger.warning(f"[ModelManager] Probe failed for {primary_id}: {err_msg}")
            elif model_info["provider"] == "google" and not google_api_key:
                self.mark_exhausted(cat_name, primary_id, "No Google Key")

        # Update OpenAI availability for all relevant models
        openai_available = bool(openai_api_key)
        for cat_name, cat_data in self._categories.items():
            for m_id, m_info in cat_data["models"].items():
                if m_info["provider"] == "openai":
                    m_info["available"] = openai_available

    def create_model(self, category: str, google_api_key: str, openai_api_key: str):
        """Factory method to create the active model instance for a category."""
        if category not in self._categories:
            return None
            
        active_id = self._categories[category]["active_id"]
        model_info = self._categories[category]["models"][active_id]
        
        # Use active_id directly as the model name for the SDK
        if model_info["provider"] == "google":
            return ChatGoogleGenerativeAI(
                model=active_id,
                temperature=0,
                google_api_key=google_api_key,
            )
        else:
            return ChatOpenAI(
                model=active_id,
                temperature=0,
                api_key=openai_api_key,
            )
