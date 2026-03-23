"""
Text Splitter Adapter

Reads a text corpus and splits it into chunks suitable for embedding.
"""

from typing import List
from src.domain.chunk import Chunk


class TextSplitter:
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
        with open(file_path, 'r', encoding='utf-8') as f:
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
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

        chunks = []
        current_text = ""
        chunk_index = 0

        for paragraph in paragraphs:
            # If adding this paragraph would exceed chunk_size, save current and start new
            if current_text and (len(current_text) + len(paragraph) + 2) > self.chunk_size:
                chunk = Chunk(
                    text=current_text.strip(),
                    chunk_index=chunk_index,
                    metadata={'char_start': max(0, sum(len(c.text) for c in chunks) - self.chunk_overlap * chunk_index)}
                )
                chunks.append(chunk)
                chunk_index += 1

                # Keep overlap: take the last chunk_overlap characters
                if self.chunk_overlap > 0 and len(current_text) > self.chunk_overlap:
                    current_text = current_text[-self.chunk_overlap:] + "\n\n" + paragraph
                else:
                    current_text = paragraph
            else:
                if current_text:
                    current_text += "\n\n" + paragraph
                else:
                    current_text = paragraph

            # Handle very long paragraphs that exceed chunk_size on their own
            while len(current_text) > self.chunk_size * 1.5:
                # Find a good split point (end of sentence)
                split_at = self._find_split_point(current_text, self.chunk_size)
                chunk = Chunk(
                    text=current_text[:split_at].strip(),
                    chunk_index=chunk_index,
                    metadata={}
                )
                chunks.append(chunk)
                chunk_index += 1

                # Keep overlap
                overlap_start = max(0, split_at - self.chunk_overlap)
                current_text = current_text[overlap_start:]

        # Don't forget the last chunk
        if current_text.strip():
            chunk = Chunk(
                text=current_text.strip(),
                chunk_index=chunk_index,
                metadata={}
            )
            chunks.append(chunk)

        return chunks

    @staticmethod
    def _find_split_point(text: str, target: int) -> int:
        """
        Finds a good split point near the target position.
        Prefers splitting at sentence boundaries (. ! ?) or commas.
        """
        # Look for sentence end near target
        for delimiter in ['. ', '.\n', '? ', '! ', ', ']:
            pos = text.rfind(delimiter, 0, target + 50)
            if pos > target * 0.5:  # Don't split too early
                return pos + len(delimiter)

        # Fallback: split at space near target
        pos = text.rfind(' ', 0, target + 20)
        if pos > 0:
            return pos + 1

        # Last resort: split at target
        return target

