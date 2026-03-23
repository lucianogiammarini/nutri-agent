"""
Vector Use Cases - Application logic for RAG

Orchestrates corpus indexing and semantic search operations.
"""

import time
import logging
from typing import Dict, Any
from src.domain.vector_repository_interface import IVectorRepository
from src.domain.text_splitter_interface import ITextSplitter

logger = logging.getLogger(__name__)


class IndexCorpusUseCase:
    """
    Use case: Index a text corpus into the vector database.

    Reads a text file, splits it into chunks, and stores
    them with their embeddings for later retrieval.
    """

    def __init__(
        self, vector_repository: IVectorRepository, text_splitter: ITextSplitter
    ):
        self.vector_repository = vector_repository
        self.text_splitter = text_splitter

    def execute(self, file_path: str, clear_existing: bool = True) -> Dict[str, Any]:
        """
        Indexes the corpus file into the vector database.
        """
        try:
            t0 = time.time()
            logger.info(
                "[RAG-UC] Indexando corpus '%s' (clear=%s)...",
                file_path,
                clear_existing,
            )

            if clear_existing:
                self.vector_repository.clear()

            # Split file into chunks
            chunks = self.text_splitter.split_file(file_path)
            logger.info("[RAG-UC] Archivo dividido en %d chunks", len(chunks))

            if not chunks:
                return {
                    "success": False,
                    "error": "No chunks were generated from the file",
                }

            # Store chunks in vector DB
            stored_count = self.vector_repository.add_chunks(chunks)

            logger.info(
                "[RAG-UC] ✓ Indexación completa: %d chunks en %.2fs",
                stored_count,
                time.time() - t0,
            )

            return {
                "success": True,
                "message": f"Corpus indexed successfully",
                "data": {
                    "chunks_created": len(chunks),
                    "chunks_stored": stored_count,
                    "total_in_db": self.vector_repository.count(),
                    "file": file_path,
                },
            }
        except FileNotFoundError:
            return {"success": False, "error": f"File not found: {file_path}"}
        except Exception as e:
            return {"success": False, "error": f"Error indexing corpus: {str(e)}"}


class SearchCorpusUseCase:
    """
    Use case: Search the corpus using semantic similarity.

    Given a natural language query, returns the most relevant
    text chunks from the indexed corpus.
    """

    def __init__(self, vector_repository: IVectorRepository):
        self.vector_repository = vector_repository

    def execute(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """
        Searches the corpus for relevant chunks.

        Args:
            query: Natural language search query
            top_k: Number of results to return

        Returns:
            Dict with the search results
        """
        try:
            if not query or not query.strip():
                return {"success": False, "error": "Query cannot be empty"}

            total_chunks = self.vector_repository.count()
            if total_chunks == 0:
                logger.warning("[RAG-UC] Búsqueda fallida: corpus no indexado")
                return {
                    "success": False,
                    "error": "The corpus has not been indexed yet. Please index first.",
                }

            logger.info(
                "[RAG-UC] Búsqueda web: '%s' (top_k=%d, corpus=%d chunks)",
                query.strip()[:80],
                top_k,
                total_chunks,
            )

            results = self.vector_repository.search(query.strip(), top_k=top_k)

            logger.info("[RAG-UC] ✓ %d resultados retornados", len(results))

            return {
                "success": True,
                "message": f"Found {len(results)} relevant chunks",
                "data": {
                    "query": query,
                    "top_k": top_k,
                    "total_chunks_in_db": total_chunks,
                    "results": [chunk.to_dict() for chunk in results],
                },
            }
        except Exception as e:
            return {"success": False, "error": f"Error searching corpus: {str(e)}"}
