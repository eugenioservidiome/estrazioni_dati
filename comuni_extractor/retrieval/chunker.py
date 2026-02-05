"""Text chunking utilities."""

from dataclasses import dataclass
from typing import List


@dataclass
class TextChunk:
    """A chunk of text."""

    text: str
    start_pos: int
    end_pos: int
    chunk_id: str = ""


class TextChunker:
    """Chunk text into overlapping segments."""

    def __init__(self, chunk_size: int = 1000, overlap: int = None):
        """Initialize chunker.
        
        Args:
            chunk_size: Size of each chunk in characters
            overlap: Overlap between chunks in characters (defaults to 20% of chunk_size)
        """
        if chunk_size <= 0:
            raise ValueError("chunk_size must be > 0")
        
        # Default overlap is 20% of chunk_size, but at least 1
        if overlap is None:
            overlap = max(1, chunk_size // 5)
        
        if overlap < 0:
            raise ValueError("overlap must be >= 0")
        if overlap >= chunk_size:
            raise ValueError("overlap must be < chunk_size")

        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str, doc_id: str = "") -> List[TextChunk]:
        """Chunk text into overlapping segments.
        
        Args:
            text: Text to chunk
            doc_id: Document ID for chunk identification
            
        Returns:
            List of TextChunk objects
        """
        if not text:
            return []

        chunks = []
        pos = 0
        chunk_idx = 0

        while pos < len(text):
            # Determine chunk end position
            end_pos = min(pos + self.chunk_size, len(text))

            # Try to break at sentence boundary near end
            if end_pos < len(text):
                # Look backwards for sentence end
                search_text = text[pos:end_pos]
                for sep in [". ", "\n\n", "\n"]:
                    idx = search_text.rfind(sep)
                    if idx > self.chunk_size // 2:  # At least halfway through
                        end_pos = pos + idx + len(sep)
                        break

            # Get chunk text
            chunk_text = text[pos:end_pos].strip()

            if chunk_text:
                chunk_id = f"{doc_id}_chunk_{chunk_idx}"
                chunks.append(
                    TextChunk(
                        text=chunk_text,
                        start_pos=pos,
                        end_pos=end_pos,
                        chunk_id=chunk_id,
                    )
                )
                chunk_idx += 1

            # Move position with overlap
            pos = end_pos - self.overlap

        return chunks

    def chunk_documents(
        self, documents: dict[str, str]
    ) -> List[TextChunk]:
        """Chunk multiple documents.
        
        Args:
            documents: Dict mapping doc_id to text
            
        Returns:
            List of TextChunk objects from all documents
        """
        all_chunks = []
        for doc_id, text in documents.items():
            chunks = self.chunk(text, doc_id)
            all_chunks.extend(chunks)
        return all_chunks
