"""
Flask Application with Hexagonal Architecture

This file is the application entry point.
Configures dependencies and starts the server.
"""

import os
import logging
import warnings
import urllib3
warnings.filterwarnings("ignore", category=urllib3.exceptions.NotOpenSSLWarning)

from dotenv import load_dotenv
from flask import Flask, render_template
import flask

# Load environment variables from .env
load_dotenv()

# Configure logging so adapter timing logs are visible
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(message)s",
    datefmt="%H:%M:%S",
)

# Import dependency container and routes
from src.infrastructure.dependency_container import DependencyContainer
from src.infrastructure.web.routes import configure_rag_routes, configure_nutrition_routes

# Create Flask application with correct template folder
app = Flask(
    __name__,
    template_folder='src/infrastructure/web/templates',
    static_folder='static',
)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# Configure dependency container
container = DependencyContainer(database_path='database.db')


@app.route('/')
def index():
    """Main welcome route"""
    context = {
        'title': 'NutriAgent — Health Manager',
        'emoji': '🧬',
        'message': 'NutriAgent',
        'description': 'Agente de Intervención Metabólica de Precisión con IA multimodal y RAG',
        'app_name': 'Course 5 - Flask App',
        'flask_version': flask.__version__,
        'course': 'Web Development Diploma'
    }
    return render_template('index.html', **context)


# Configure routes
configure_rag_routes(app, container.rag_controller)
configure_nutrition_routes(app, container.nutrition_controller)


if __name__ == '__main__':
    print("=" * 70)
    print("🧬 NutriAgent — Health & Nutrition Manager")
    print("=" * 70)
    print("\n📋 Available routes:")
    print("\n  🌐 WEB INTERFACE:")
    print("  GET  /                       - Welcome page")
    print("  GET  /web/dashboard          - 🥗 Health & Nutrition Dashboard")
    print("  GET  /web/rag                - 🔍 RAG search interface")
    print("\n  🥗 NUTRITION API:")
    print("  POST /api/profiles           - Create health profile")
    print("  GET  /api/profiles           - List profiles")
    print("  POST /api/meals/analyze      - Analyze food photo (AI)")
    print("  GET  /api/dashboard/<id>     - Today's macro summary")
    print("  POST /api/chat               - RAG nutrition chat")
    print("\n  🔍 RAG - Vector Search:")
    print("  POST /rag/index              - Index corpus into vector DB")
    print("  POST /rag/search             - Semantic search on corpus")
    print("  GET  /rag/status             - Vector DB status")
    print("\n🚀 Server running on: http://0.0.0.0:5000")
    print("📱 Mobile access: http://<your-ip>:5000")
    print("=" * 70 + "\n")

    app.run(host='0.0.0.0', port=5000, debug=True)
