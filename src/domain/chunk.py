"""
Domain Entity: Chunk

Represents a fragment of text from the corpus, used for RAG retrieval.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class Chunk:
    """
    Chunk Entity - Pure domain model

    A chunk is a piece of text extracted from the corpus,
    suitable for embedding and semantic search.
    """
    text: str
    chunk_index: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    id: Optional[str] = None
    score: Optional[float] = None

    def __post_init__(self):
        """Domain validations"""
        if not self.text or len(self.text.strip()) == 0:
            raise ValueError("Chunk text cannot be empty")

        if self.id is None:
            self.id = f"chunk_{self.chunk_index}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'text': self.text,
            'chunk_index': self.chunk_index,
            'metadata': self.metadata,
            'score': self.score,
        }

