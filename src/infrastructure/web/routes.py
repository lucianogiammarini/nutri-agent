"""
Flask routes configuration

Defines routes and connects them with controllers.
"""

from flask import Flask
from src.infrastructure.web.rag_controller import RAGController
from src.infrastructure.web.nutrition_controller import NutritionController


def configure_rag_routes(app: Flask, rag_controller: RAGController):
    """
    Configures Flask application routes for RAG (vector search)

    Args:
        app: Flask instance
        rag_controller: RAG controller
    """

    app.add_url_rule(
        '/rag/index',
        'rag_index',
        rag_controller.index_corpus,
        methods=['POST']
    )

    app.add_url_rule(
        '/rag/search',
        'rag_search',
        rag_controller.search,
        methods=['POST']
    )

    app.add_url_rule(
        '/rag/status',
        'rag_status',
        rag_controller.status,
        methods=['GET']
    )

    # Web Route (HTML view)
    app.add_url_rule(
        '/web/rag',
        'rag_search_view',
        rag_controller.search_view,
        methods=['GET']
    )


def configure_nutrition_routes(app: Flask, ctrl: NutritionController):
    """
    Configures routes for the Nutrition / Health Manager module.

    Args:
        app: Flask instance
        ctrl: Nutrition controller
    """

    # Web View
    app.add_url_rule('/web/dashboard', 'dashboard_view', ctrl.dashboard_view, methods=['GET'])

    # Profiles API
    app.add_url_rule('/api/profiles', 'api_create_profile', ctrl.api_create_profile, methods=['POST'])
    app.add_url_rule('/api/profiles', 'api_get_profiles', ctrl.api_get_profiles, methods=['GET'])
    app.add_url_rule('/api/profiles/<int:profile_id>', 'api_get_profile', ctrl.api_get_profile, methods=['GET'])
    app.add_url_rule('/api/profiles/<int:profile_id>', 'api_update_profile', ctrl.api_update_profile, methods=['PUT'])

    # Meals API
    app.add_url_rule('/api/meals/analyze', 'api_analyze_meal', ctrl.api_analyze_meal, methods=['POST'])
    app.add_url_rule('/api/meals/<int:profile_id>', 'api_meal_history', ctrl.api_meal_history, methods=['GET'])

    # Dashboard API
    app.add_url_rule('/api/dashboard/<int:profile_id>', 'api_today_summary', ctrl.api_today_summary, methods=['GET'])

    # Chat API
    app.add_url_rule('/api/chat', 'api_chat', ctrl.api_chat, methods=['POST'])
    app.add_url_rule('/api/chat/<int:profile_id>', 'api_chat_history', ctrl.api_chat_history, methods=['GET'])
    app.add_url_rule('/api/chat/<int:profile_id>', 'api_chat_clear', ctrl.api_chat_clear, methods=['DELETE'])
