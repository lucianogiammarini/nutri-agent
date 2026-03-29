"""
Dependency Injection Container

Configures and connects all layers of hexagonal architecture.
"""

import os

# RAG / Vector DB imports
from src.domain.vector_repository_interface import IVectorRepository
from src.domain.text_splitter_interface import ITextSplitter
from src.infrastructure.repositories.chroma_vector_repository import (
    ChromaVectorRepository,
)
from src.infrastructure.adapters.text_splitter import TextSplitter
from src.application.vector_use_cases import IndexCorpusUseCase, SearchCorpusUseCase
from src.infrastructure.web.rag_controller import RAGController

# Nutrition / Health Manager imports
from src.domain.profile_repository_interface import IProfileRepository
from src.domain.meal_repository_interface import IMealRepository
from src.domain.chat_repository_interface import IChatRepository
from src.infrastructure.repositories.sqlite_profile_repository import (
    SQLiteProfileRepository,
)
from src.infrastructure.repositories.sqlite_meal_repository import SQLiteMealRepository
from src.infrastructure.repositories.sqlite_chat_repository import SQLiteChatRepository
from src.infrastructure.repositories.sqlite_nutrition_cache import SQLiteNutritionCache
from src.infrastructure.adapters.langchain_adapter import LangChainAdapter
from src.infrastructure.adapters.usda_adapter import USDAAdapter
from src.domain.llm_adapter_interface import ILlmAdapter
from src.domain.food_api_interface import IFoodAPI
from src.infrastructure.adapters.model_manager import ModelManager
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from src.application.profile_use_cases import (
    CreateProfileUseCase,
    GetProfilesUseCase,
    GetProfileByIdUseCase,
    UpdateProfileUseCase,
)
from src.application.meal_use_cases import (
    AnalyzeMealUseCase,
    GetMealHistoryUseCase,
    GetTodaySummaryUseCase,
    DeleteMealUseCase,
)
from src.application.chat_use_case import ChatUseCase
from src.infrastructure.web.nutrition_controller import NutritionController


class DependencyContainer:
    """
    Dependency container - Dependency Injection Pattern
    """

    def __init__(
        self, database_path: str = "database.db", chroma_path: str = "chroma_db"
    ):
        self.base_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )

        self.database_path = os.path.join(self.base_dir, database_path)
        self.chroma_path = os.path.join(self.base_dir, chroma_path)

        # RAG Paths
        self.corpus_path = os.getenv(
            "RAG_CORPUS_PATH",
            os.path.join(self.base_dir, "data", "corpus", "gapa_clean_corpus.txt"),
        )
        self.manual_pdf_path = os.path.join(
            self.base_dir, "data", "corpus", "gapa_manual.pdf"
        )
        self._vector_repository = None
        self._rag_controller = None
        self._profile_repository = None
        self._meal_repository = None
        self._chat_repository = None
        self._vision_adapter = None
        self._chat_adapter = None
        self._food_api_adapter = None
        self._nutrition_cache = None
        self._nutrition_controller = None
        self._mcp_sqlite = None
        self._model_manager = None

        # Start availability probe
        self.model_manager.probe_models(
            google_api_key=os.getenv("GOOGLE_API_KEY", ""),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        )

    # ── MCP Integrations ────────────────────────────────────────

    @property
    def mcp_sqlite(self):
        if self._mcp_sqlite is None:
            # Import dynamically to avoid loading async loop at top level
            from src.infrastructure.adapters.mcp_adapter import SyncSQLiteMCP

            self._mcp_sqlite = SyncSQLiteMCP(self.database_path)
        return self._mcp_sqlite

    # ── RAG / Vector DB ─────────────────────────────────────────

    @property
    def vector_repository(self) -> IVectorRepository:
        if self._vector_repository is None:
            self._vector_repository = ChromaVectorRepository(
                persist_directory=self.chroma_path
            )
        return self._vector_repository

    @property
    def rag_controller(self) -> RAGController:
        if self._rag_controller is None:
            text_splitter = TextSplitter(chunk_size=1000, chunk_overlap=200)
            index_use_case = IndexCorpusUseCase(
                vector_repository=self.vector_repository,
                text_splitter=text_splitter,
            )
            search_use_case = SearchCorpusUseCase(
                vector_repository=self.vector_repository,
            )
            self._rag_controller = RAGController(
                index_corpus_use_case=index_use_case,
                search_corpus_use_case=search_use_case,
                default_corpus_path=self.corpus_path,
            )
        return self._rag_controller

    # ── Nutrition / Health Manager ──────────────────────────────

    @property
    def profile_repository(self) -> IProfileRepository:
        if self._profile_repository is None:
            self._profile_repository = SQLiteProfileRepository(self.database_path)
        return self._profile_repository

    @property
    def meal_repository(self) -> IMealRepository:
        if self._meal_repository is None:
            self._meal_repository = SQLiteMealRepository(self.database_path)
        return self._meal_repository

    @property
    def chat_repository(self) -> IChatRepository:
        if self._chat_repository is None:
            self._chat_repository = SQLiteChatRepository(self.database_path)
        return self._chat_repository

    @property
    def vision_adapter(self) -> ILlmAdapter:
        if self._vision_adapter is None:
            # Always get the latest model instance based on manager state
            model = self.model_manager.create_model(
                category="vision",
                google_api_key=os.getenv("GOOGLE_API_KEY", ""),
                openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            )
            self._vision_adapter = LangChainAdapter(chat_model=model, model_manager=self.model_manager, category="vision")
            # Inject food API for direct parallel nutrition lookups
            self._vision_adapter.set_food_api(self.food_api_adapter)
        return self._vision_adapter

    @property
    def model_manager(self) -> ModelManager:
        if self._model_manager is None:
            self._model_manager = ModelManager()
        return self._model_manager

    @property
    def chat_adapter(self) -> ILlmAdapter:
        if self._chat_adapter is None:
            # Always get the latest model instance based on manager state
            model = self.model_manager.create_model(
                category="chat",
                google_api_key=os.getenv("GOOGLE_API_KEY", ""),
                openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            )
            self._chat_adapter = LangChainAdapter(chat_model=model, model_manager=self.model_manager, category="chat")
        return self._chat_adapter

    @property
    def nutrition_cache(self) -> SQLiteNutritionCache:
        if self._nutrition_cache is None:
            self._nutrition_cache = SQLiteNutritionCache(self.database_path)
        return self._nutrition_cache

    @property
    def food_api_adapter(self) -> IFoodAPI:
        if self._food_api_adapter is None:
            self._food_api_adapter = USDAAdapter(
                nutrition_cache=self.nutrition_cache,
            )
        return self._food_api_adapter

    @property
    def nutrition_controller(self) -> NutritionController:
        if self._nutrition_controller is None:
            self._nutrition_controller = NutritionController(
                create_profile=CreateProfileUseCase(self.profile_repository),
                get_profiles=GetProfilesUseCase(self.profile_repository),
                get_profile_by_id=GetProfileByIdUseCase(self.profile_repository),
                update_profile=UpdateProfileUseCase(self.profile_repository),
                analyze_meal=AnalyzeMealUseCase(
                    meal_repository=self.meal_repository,
                    profile_repository=self.profile_repository,
                    vision_adapter=self.vision_adapter,
                ),
                get_meal_history=GetMealHistoryUseCase(self.meal_repository),
                delete_meal=DeleteMealUseCase(self.meal_repository),
                get_today_summary=GetTodaySummaryUseCase(
                    self.meal_repository,
                    self.profile_repository,
                ),
                chat=ChatUseCase(
                    profile_repository=self.profile_repository,
                    meal_repository=self.meal_repository,
                    vector_repository=self.vector_repository,
                    chat_repository=self.chat_repository,
                    chat_adapter=self.chat_adapter,
                    food_api_adapter=self.food_api_adapter,
                    mcp_sqlite=self.mcp_sqlite,
                ),
                model_manager=self.model_manager,
            )
        return self._nutrition_controller
