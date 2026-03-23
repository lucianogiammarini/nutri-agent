"""
ChromaDB Vector Repository

Implementation of the vector repository using ChromaDB.
ChromaDB uses SQLite internally for persistence, making it ideal
for academic projects.
"""

import time
import logging
from typing import List
import chromadb
from chromadb.utils import embedding_functions

from src.domain.chunk import Chunk
from src.domain.vector_repository_interface import IVectorRepository

logger = logging.getLogger(__name__)


class ChromaVectorRepository(IVectorRepository):
    """
    Vector repository implementation using ChromaDB.

    Uses the 'paraphrase-multilingual-MiniLM-L12-v2' model from
    sentence-transformers to generate embeddings, which works well
    with Spanish text.
    """

    def __init__(
        self,
        persist_directory: str = "chroma_db",
        collection_name: str = "gapa_corpus",
        embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    ):
        """
        Args:
            persist_directory: Directory for ChromaDB persistent storage
            collection_name: Name of the collection in ChromaDB
            embedding_model: sentence-transformers model name for embeddings
        """
        self._client = chromadb.PersistentClient(path=persist_directory)

        # Use sentence-transformers for multilingual embeddings
        self._embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=embedding_model
        )

        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=self._embedding_fn,
            metadata={"hnsw:space": "cosine"}  # Use cosine similarity
        )

    def add_chunks(self, chunks: List[Chunk]) -> int:
        """Stores chunks with their embeddings in ChromaDB."""
        if not chunks:
            return 0

        t0 = time.time()
        logger.info("[RAG] Indexando %d chunks en ChromaDB...", len(chunks))

        ids = [chunk.id for chunk in chunks]
        documents = [chunk.text for chunk in chunks]
        metadatas = [
            {
                "chunk_index": chunk.chunk_index,
                **{k: str(v) for k, v in chunk.metadata.items()}
            }
            for chunk in chunks
        ]

        # ChromaDB handles embedding generation automatically
        self._collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )

        logger.info("[RAG] ✓ %d chunks indexados (%.2fs). Total en DB: %d",
                     len(chunks), time.time() - t0, self._collection.count())
        return len(chunks)

    def search(self, query: str, top_k: int = 5) -> List[Chunk]:
        """Searches for the most relevant chunks using semantic similarity."""
        t0 = time.time()
        logger.info("[RAG] Búsqueda: '%s' (top_k=%d)", query[:80], top_k)

        results = self._collection.query(
            query_texts=[query],
            n_results=min(top_k, self._collection.count() or 1)
        )

        chunks = []
        if results and results['documents'] and results['documents'][0]:
            for i, doc in enumerate(results['documents'][0]):
                metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                distance = results['distances'][0][i] if results['distances'] else None

                # ChromaDB returns distances; convert to similarity score (cosine)
                # For cosine distance: similarity = 1 - distance
                score = round(1.0 - distance, 4) if distance is not None else None

                chunk = Chunk(
                    text=doc,
                    chunk_index=int(metadata.get('chunk_index', i)),
                    metadata=metadata,
                    id=results['ids'][0][i],
                    score=score
                )
                chunks.append(chunk)

        elapsed = time.time() - t0
        if chunks:
            logger.info("[RAG] ✓ %d resultados (%.2fs):", len(chunks), elapsed)
            for c in chunks:
                logger.info("[RAG]   [score=%.4f] %s...", c.score or 0, c.text[:90].replace('\n', ' '))
        else:
            logger.info("[RAG] ✗ Sin resultados para '%s' (%.2fs)", query[:50], elapsed)

        return chunks

    def count(self) -> int:
        """Returns the total number of stored chunks."""
        total = self._collection.count()
        logger.info("[RAG] Chunks en DB: %d", total)
        return total

    def clear(self) -> None:
        """Removes all chunks from the collection."""
        logger.info("[RAG] Limpiando colección '%s'...", self._collection.name)
        # Delete and recreate the collection
        collection_name = self._collection.name
        self._client.delete_collection(collection_name)
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=self._embedding_fn,
            metadata={"hnsw:space": "cosine"}
        )
        logger.info("[RAG] ✓ Colección limpiada")

