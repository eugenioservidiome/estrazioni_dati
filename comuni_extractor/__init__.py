"""Comuni Extractor Platform - Extract structured data from Italian municipality websites."""

__version__ = "0.1.0"
__author__ = "Eugenio Servizi"

from comuni_extractor.models import (
    Chunk,
    Document,
    ExtractionCandidate,
    ExtractionResult,
    FieldSpec,
    FieldValue,
)

__all__ = [
    "Chunk",
    "Document",
    "ExtractionCandidate",
    "ExtractionResult",
    "FieldSpec",
    "FieldValue",
]
