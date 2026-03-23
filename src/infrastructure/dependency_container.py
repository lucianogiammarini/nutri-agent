"""
Dependency Injection Container

Configures and connects all layers of hexagonal architecture.
"""

import os

# RAG / Vector DB imports
from src.domain.vector_repository_interface import IVectorRepository
from src.infrastructure.repositories.chroma_vector_repository import ChromaVectorRepository
from src.infrastructure.adapters.text_splitter import TextSplitter
from src.application.vector_use_cases import IndexCorpusUseCase, SearchCorpusUseCase
from src.infrastructure.web.rag_controller import RAGController

# Nutrition / Health Manager imports
from src.domain.profile_repository_interface import IProfileRepository
from src.domain.meal_repository_interface import IMealRepository
from src.domain.chat_repository_interface import IChatRepository
from src.infrastructure.repositories.sqlite_profile_repository import SQLiteProfileRepository
from src.infrastructure.repositories.sqlite_meal_repository import SQLiteMealRepository
from src.infrastructure.repositories.sqlite_chat_repository import SQLiteChatRepository
from src.infrastructure.repositories.sqlite_nutrition_cache import SQLiteNutritionCache
from src.infrastructure.adapters.langchain_adapter import LangChainAdapter
from src.infrastructure.adapters.usda_adapter import USDAAdapter
from langchain_openai import ChatOpenAI
from src.application.profile_use_cases import (
    CreateProfileUseCase, GetProfilesUseCase,
    GetProfileByIdUseCase, UpdateProfileUseCase,
)
from src.application.meal_use_cases import (
    AnalyzeMealUseCase, GetMealHistoryUseCase, GetTodaySummaryUseCase,
)
from src.application.chat_use_case import ChatUseCase
from src.infrastructure.web.nutrition_controller import NutritionController


class DependencyContainer:
    """
    Dependency container - Dependency Injection Pattern
    """

    def __init__(self, database_path: str = 'database.db', chroma_path: str = 'chroma_db'):
        self.database_path = database_path
        self.chroma_path = chroma_path
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
            text_splitter = TextSplitter(chunk_size=500, chunk_overlap=50)
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
    def vision_adapter(self) -> LangChainAdapter:
        if self._vision_adapter is None:
            model = ChatOpenAI(model="gpt-4o", api_key=os.getenv("OPENAI_API_KEY", ""))
            self._vision_adapter = LangChainAdapter(chat_model=model)
            # Inject food API for direct parallel nutrition lookups
            self._vision_adapter.set_food_api(self.food_api_adapter)
        return self._vision_adapter

    @property
    def chat_adapter(self) -> LangChainAdapter:
        if self._chat_adapter is None:
            model = ChatOpenAI(model="gpt-4o-mini", api_key=os.getenv("OPENAI_API_KEY", ""))
            self._chat_adapter = LangChainAdapter(chat_model=model)
        return self._chat_adapter

    @property
    def nutrition_cache(self) -> SQLiteNutritionCache:
        if self._nutrition_cache is None:
            self._nutrition_cache = SQLiteNutritionCache(self.database_path)
        return self._nutrition_cache

    @property
    def food_api_adapter(self) -> USDAAdapter:
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
                get_today_summary=GetTodaySummaryUseCase(
                    self.meal_repository, self.profile_repository,
                ),
                chat=ChatUseCase(
                    profile_repository=self.profile_repository,
                    meal_repository=self.meal_repository,
                    vector_repository=self.vector_repository,
                    chat_repository=self.chat_repository,
                    chat_adapter=self.chat_adapter,
                    food_api_adapter=self.food_api_adapter,
                ),
            )
        return self._nutrition_controller
