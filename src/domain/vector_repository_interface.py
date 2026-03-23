"""
Port (Interface) for vector repository

Defines the contract that any vector repository implementation must fulfill.
Used for RAG (Retrieval Augmented Generation) operations.
"""

from abc import ABC, abstractmethod
from typing import List
from src.domain.chunk import Chunk


class IVectorRepository(ABC):
    """
    Port - Vector repository interface

    Abstraction for storing and retrieving text chunks
    using semantic similarity search.
    """

    @abstractmethod
    def add_chunks(self, chunks: List[Chunk]) -> int:
        """
        Stores a list of chunks with their embeddings.

        Args:
            chunks: List of Chunk entities to store

        Returns:
            Number of chunks successfully stored
        """
        pass

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> List[Chunk]:
        """
        Searches for the most relevant chunks given a query.

        Args:
            query: Natural language search query
            top_k: Number of top results to return

        Returns:
            List of Chunk entities ordered by relevance (most relevant first)
        """
        pass

    @abstractmethod
    def count(self) -> int:
        """
        Returns the total number of chunks stored.

        Returns:
            Number of stored chunks
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """Removes all stored chunks."""
        pass

