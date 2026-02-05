"""TF-IDF indexing for document retrieval."""

from typing import List, Optional, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


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
        self.chunks: List[str] = []
        self.chunk_ids: List[str] = []

    def build(self, chunks: List[Tuple[str, str]]) -> None:
        """Build TF-IDF index from chunks.
        
        Args:
            chunks: List of (chunk_id, chunk_text) tuples
        """
        if not chunks:
            raise ValueError("No chunks provided")

        # Separate IDs and texts
        self.chunk_ids, self.chunks = zip(*chunks)
        self.chunk_ids = list(self.chunk_ids)
        self.chunks = list(self.chunks)

        # Build vectorizer
        self.vectorizer = TfidfVectorizer(
            ngram_range=self.ngram_range,
            max_features=self.max_features,
            min_df=self.min_df,
            max_df=self.max_df,
            lowercase=True,
            stop_words="english",  # TODO: Add Italian stop words
        )

        # Fit and transform
        self.tfidf_matrix = self.vectorizer.fit_transform(self.chunks)

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """Search for query in index.
        
        Args:
            query: Query string
            top_k: Number of results to return
            
        Returns:
            List of (chunk_id, relevance_score) tuples sorted by score descending
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
            (self.chunk_ids[i], float(scores[i]))
            for i in top_indices
            if scores[i] > 0
        ]

        return results

    def get_chunk(self, chunk_id: str) -> Optional[str]:
        """Get chunk text by ID.
        
        Args:
            chunk_id: Chunk identifier
            
        Returns:
            Chunk text or None
        """
        try:
            idx = self.chunk_ids.index(chunk_id)
            return self.chunks[idx]
        except (ValueError, IndexError):
            return None

    def get_chunks_by_ids(self, chunk_ids: List[str]) -> dict[str, str]:
        """Get multiple chunks by IDs.
        
        Args:
            chunk_ids: List of chunk IDs
            
        Returns:
            Dict mapping chunk_id to text
        """
        result = {}
        for chunk_id in chunk_ids:
            text = self.get_chunk(chunk_id)
            if text:
                result[chunk_id] = text
        return result

    def is_built(self) -> bool:
        """Check if index is built.
        
        Returns:
            True if index is ready to search
        """
        return self.vectorizer is not None and self.tfidf_matrix is not None
