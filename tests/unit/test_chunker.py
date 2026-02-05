"""Tests for text chunking."""

import pytest

from comuni_extractor.retrieval.chunker import TextChunker


class TestTextChunker:
    """Test TextChunker class."""

    def test_chunker_initialization(self):
        """Test chunker initialization."""
        chunker = TextChunker(chunk_size=100, overlap=10)
        assert chunker.chunk_size == 100
        assert chunker.overlap == 10

    def test_chunker_invalid_params(self):
        """Test invalid parameters."""
        with pytest.raises(ValueError):
            TextChunker(chunk_size=0)

        with pytest.raises(ValueError):
            TextChunker(chunk_size=100, overlap=-1)

        with pytest.raises(ValueError):
            TextChunker(chunk_size=100, overlap=100)

    def test_chunk_empty_text(self):
        """Test chunking empty text."""
        chunker = TextChunker(chunk_size=100)
        chunks = chunker.chunk("")
        assert len(chunks) == 0

    def test_chunk_short_text(self):
        """Test chunking text shorter than chunk size."""
        chunker = TextChunker(chunk_size=100)
        text = "This is a short text."
        chunks = chunker.chunk(text, doc_id="test")
        assert len(chunks) == 1
        assert chunks[0].text == text.strip()

    def test_chunk_long_text(self):
        """Test chunking long text with overlap."""
        chunker = TextChunker(chunk_size=50, overlap=10)
        text = "This is a longer text. " * 10  # Create long text
        chunks = chunker.chunk(text, doc_id="test")
        assert len(chunks) > 1

        # Check chunk IDs
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_id == f"test_chunk_{i}"

    def test_chunk_preserves_position(self):
        """Test that chunks preserve position information."""
        chunker = TextChunker(chunk_size=100, overlap=20)
        text = "A" * 300  # 300 characters
        chunks = chunker.chunk(text)

        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk.start_pos < chunk.end_pos
            assert chunk.text  # Non-empty

    def test_chunk_documents(self):
        """Test chunking multiple documents."""
        chunker = TextChunker(chunk_size=50, overlap=5)
        documents = {
            "doc1": "Text for document 1. " * 5,
            "doc2": "Text for document 2. " * 5,
        }
        chunks = chunker.chunk_documents(documents)

        assert len(chunks) > 0
        # Check that doc IDs are properly set
        doc1_chunks = [c for c in chunks if c.chunk_id.startswith("doc1")]
        doc2_chunks = [c for c in chunks if c.chunk_id.startswith("doc2")]
        assert len(doc1_chunks) > 0
        assert len(doc2_chunks) > 0
