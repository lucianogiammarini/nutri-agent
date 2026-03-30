"""
Text Splitter Adapter

Reads a text corpus and splits it into chunks suitable for embedding.
"""

from typing import List
from src.domain.chunk import Chunk
from src.domain.text_splitter_interface import ITextSplitter


class TextSplitter(ITextSplitter):
    """
    Splits a text corpus into overlapping chunks for RAG indexing.

    Uses paragraph-aware splitting: tries to split on paragraph boundaries
    (double newlines), and falls back to sentence/word boundaries.
    """

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        """
        Args:
            chunk_size: Target size in characters for each chunk
            chunk_overlap: Number of overlapping characters between consecutive chunks
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_file(self, file_path: str) -> List[Chunk]:
        """
        Reads a text file and splits it into chunks.

        Args:
            file_path: Path to the text file

        Returns:
            List of Chunk entities
        """
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

        return self.split_text(text)

    def split_text(self, text: str) -> List[Chunk]:
        """
        Splits text into overlapping chunks.

        Strategy:
        1. Split by paragraphs (double newline)
        2. Merge small paragraphs to reach chunk_size
        3. Split large paragraphs if needed

        Args:
            text: The full text to split

        Returns:
            List of Chunk entities
        """
        # Split into paragraphs
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

        chunks = []
        current_text = ""
        chunk_index = 0

        for paragraph in paragraphs:
            if self._should_start_new_chunk(current_text, paragraph):
                chunks.append(
                    self._create_merging_chunk(current_text, chunk_index, chunks)
                )
                chunk_index += 1
                current_text = self._prepare_next_chunk_text(current_text, paragraph)
            else:
                current_text = self._append_to_current_chunk(current_text, paragraph)

            current_text, chunk_index = self._split_if_too_long(
                current_text, chunks, chunk_index
            )

        # Don't forget the last chunk
        if current_text.strip():
            chunks.append(
                Chunk(text=current_text.strip(), chunk_index=chunk_index, metadata={})
            )

        return chunks

    def _should_start_new_chunk(self, current_text: str, next_paragraph: str) -> bool:
        """Determines if adding the next paragraph would exceed the chunk size."""
        if not current_text:
            return False
        return (len(current_text) + len(next_paragraph) + 2) > self.chunk_size

    def _create_merging_chunk(
        self, text: str, index: int, chunks: List[Chunk]
    ) -> Chunk:
        """Creates a chunk with estimated character start metadata."""
        char_start = max(
            0, sum(len(c.text) for c in chunks) - self.chunk_overlap * index
        )
        return Chunk(
            text=text.strip(), chunk_index=index, metadata={"char_start": char_start}
        )

    def _prepare_next_chunk_text(self, current_text: str, paragraph: str) -> str:
        """Handles overlap when starting a new chunk after a series of paragraphs."""
        if self.chunk_overlap > 0 and len(current_text) > self.chunk_overlap:
            return current_text[-self.chunk_overlap :] + "\n\n" + paragraph
        return paragraph

    def _append_to_current_chunk(self, current_text: str, paragraph: str) -> str:
        """Appends a paragraph to the current working text."""
        if current_text:
            return current_text + "\n\n" + paragraph
        return paragraph

    def _split_if_too_long(
        self, text: str, chunks: List[Chunk], index: int
    ) -> tuple[str, int]:
        """Handles very long paragraphs that exceed chunk_size on their own."""
        while len(text) > self.chunk_size * 1.5:
            # Find a good split point (end of sentence)
            split_at = self._find_split_point(text, self.chunk_size)
            chunks.append(
                Chunk(text=text[:split_at].strip(), chunk_index=index, metadata={})
            )
            index += 1

            # Keep overlap
            overlap_start = max(0, split_at - self.chunk_overlap)
            text = text[overlap_start:]
        return text, index

    @staticmethod
    def _find_split_point(text: str, target: int) -> int:
        """
        Finds a good split point near the target position.
        Prefers splitting at sentence boundaries (. ! ?) or commas.
        """
        # Look for sentence end near target
        for delimiter in [". ", ".\n", "? ", "! ", ", "]:
            pos = text.rfind(delimiter, 0, target + 50)
            if pos > target * 0.5:  # Don't split too early
                return pos + len(delimiter)

        # Fallback: split at space near target
        pos = text.rfind(" ", 0, target + 20)
        if pos > 0:
            return pos + 1

        # Last resort: split at target
        return target
