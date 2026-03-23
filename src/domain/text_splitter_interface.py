from abc import ABC, abstractmethod
from typing import List
from src.domain.chunk import Chunk

class ITextSplitter(ABC):
    """
    Port for splitting text into chunks for RAG indexing.
    """

    @abstractmethod
    def split_file(self, file_path: str) -> List[Chunk]:
        """Reads a text file and splits it into smaller chunks."""
        pass

    @abstractmethod
    def split_text(self, text: str) -> List[Chunk]:
        """Splits raw string text into smaller chunks."""
        pass
