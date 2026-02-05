"""TF-IDF indexing for document retrieval."""

from typing import List, Optional, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from comuni_extractor.retrieval.chunker import TextChunk


class TFIDFIndexer:
    """Build and search TF-IDF indexes."""

    def __init__(
        self,
        ngram_range: Tuple[int, int] = (1, 2),
        max_features: int = 1000,
        min_df: int = 1,
        max_df: float = 0.95,
    ):
        """Initialize TF-IDF indexer.
        
        Args:
            ngram_range: Min and max n-gram sizes
            max_features: Maximum number of features
            min_df: Minimum document frequency
            max_df: Maximum document frequency ratio
        """
        self.ngram_range = ngram_range
        self.max_features = max_features
        self.min_df = min_df
        self.max_df = max_df

        self.vectorizer: Optional[TfidfVectorizer] = None
        self.tfidf_matrix = None
        self.chunks: List[TextChunk] = []

    def build(self, chunks: List[TextChunk]) -> None:
        """Build TF-IDF index from chunks.
        
        Args:
            chunks: List of TextChunk objects
        """
        if not chunks:
            raise ValueError("No chunks provided")

        # Store chunks
        self.chunks = chunks

        # Extract texts for vectorization
        chunk_texts = [chunk.text for chunk in chunks]

        # Build vectorizer
        self.vectorizer = TfidfVectorizer(
            ngram_range=self.ngram_range,
            max_features=self.max_features,
            min_df=self.min_df,
            max_df=self.max_df,
            lowercase=True,
            stop_words=None,  # Don't use English stop words for Italian texts
        )

        # Fit and transform
        self.tfidf_matrix = self.vectorizer.fit_transform(chunk_texts)

    def search(self, query: str, top_k: int = 5) -> List[Tuple[TextChunk, float]]:
        """Search for query in index.
        
        Args:
            query: Query string
            top_k: Number of results to return
            
        Returns:
            List of (TextChunk, relevance_score) tuples sorted by score descending
        """
        if self.vectorizer is None or self.tfidf_matrix is None:
            raise ValueError("Index not built. Call build() first.")

        # Transform query
        query_vec = self.vectorizer.transform([query])

        # Compute similarities
        similarities = query_vec * self.tfidf_matrix.T
        scores = similarities.A1  # Convert to array

        # Get top-k
        top_indices = np.argsort(scores)[::-1][:top_k]
        results = [
            (self.chunks[i], float(scores[i]))
            for i in top_indices
            if scores[i] > 0
        ]

        return results

    def get_chunk(self, chunk_id: str) -> Optional[TextChunk]:
        """Get chunk by ID.
        
        Args:
            chunk_id: Chunk identifier
            
        Returns:
            TextChunk or None
        """
        for chunk in self.chunks:
            if chunk.chunk_id == chunk_id:
                return chunk
        return None

    def get_chunks_by_ids(self, chunk_ids: List[str]) -> List[TextChunk]:
        """Get multiple chunks by IDs.
        
        Args:
            chunk_ids: List of chunk IDs
            
        Returns:
            List of TextChunk objects
        """
        result = []
        for chunk_id in chunk_ids:
            chunk = self.get_chunk(chunk_id)
            if chunk:
                result.append(chunk)
        return result

    def is_built(self) -> bool:
        """Check if index is built.
        
        Returns:
            True if index is ready to search
        """
        return self.vectorizer is not None and self.tfidf_matrix is not None
