"""
RAG Controller - Input adapter (Web)

Handles HTTP requests for corpus indexing and semantic search.
"""

from flask import request, jsonify, render_template
from src.application.vector_use_cases import IndexCorpusUseCase, SearchCorpusUseCase


class RAGController:
    """
    RAG controller - Web adapter

    Provides endpoints for indexing the corpus and searching it.
    """

    def __init__(
        self,
        index_corpus_use_case: IndexCorpusUseCase,
        search_corpus_use_case: SearchCorpusUseCase,
        default_corpus_path: str = "gapa_clean_corpus.txt"
    ):
        self.index_corpus_use_case = index_corpus_use_case
        self.search_corpus_use_case = search_corpus_use_case
        self.default_corpus_path = default_corpus_path

    def index_corpus(self):
        """
        POST /rag/index

        Indexes the text corpus into the vector database.
        Optional JSON body: {"file_path": "path/to/file.txt", "clear": true}
        """
        data = request.get_json(silent=True) or {}
        file_path = data.get('file_path', self.default_corpus_path)
        clear_existing = data.get('clear', True)

        result = self.index_corpus_use_case.execute(
            file_path=file_path,
            clear_existing=clear_existing
        )

        status_code = 200 if result['success'] else 400
        return jsonify(result), status_code

    def search(self):
        """
        POST /rag/search

        Searches the corpus for relevant chunks.
        JSON body: {"query": "your question here", "top_k": 5}
        """
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'No data received. Send JSON with "query" field.'
            }), 400

        query = data.get('query', '')
        top_k = data.get('top_k', 5)

        result = self.search_corpus_use_case.execute(
            query=query,
            top_k=top_k
        )

        status_code = 200 if result['success'] else 400
        return jsonify(result), status_code

    def status(self):
        """
        GET /rag/status

        Returns the current status of the vector database.
        """
        try:
            from src.infrastructure.repositories.chroma_vector_repository import ChromaVectorRepository
            count = self.search_corpus_use_case.vector_repository.count()
            return jsonify({
                'success': True,
                'data': {
                    'indexed_chunks': count,
                    'corpus_file': self.default_corpus_path,
                    'status': 'ready' if count > 0 else 'empty'
                }
            }), 200
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    def search_view(self):
        """
        GET /web/rag

        Renders the RAG search web interface.
        """
        return render_template('rag_search.html')

