"""PDF text extraction."""

import hashlib
from pathlib import Path
from typing import Optional

from pdfminer.high_level import extract_text
from pypdf import PdfReader


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text from PDF file.
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        Extracted text
        
    Raises:
        RuntimeError: If PDF extraction fails
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    try:
        # Try pdfminer.six first (more robust)
        text = extract_text(str(pdf_path))
        return text
    except Exception as e:
        raise RuntimeError(f"Failed to extract text from PDF {pdf_path}: {e}")


def extract_text_from_pdf_pypdf(pdf_path: Path) -> str:
    """Extract text using pypdf.
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        Extracted text
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    try:
        reader = PdfReader(str(pdf_path))
        text_parts = []

        for page in reader.pages:
            text_parts.append(page.extract_text())

        return "\n".join(text_parts)
    except Exception as e:
        raise RuntimeError(f"Failed to extract text from PDF {pdf_path}: {e}")


def compute_pdf_hash(pdf_path: Path) -> str:
    """Compute SHA256 hash of PDF file.
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        Hex digest of SHA256 hash
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    sha256_hash = hashlib.sha256()
    with open(pdf_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

    return sha256_hash.hexdigest()


def calculate_readability_score(text: str) -> float:
    """Calculate readability score based on alpha character ratio.
    
    Args:
        text: Extracted text
        
    Returns:
        Score between 0 and 1 (ratio of alphabetic chars)
    """
    if not text:
        return 0.0

    alpha_count = sum(1 for c in text if c.isalpha())
    return alpha_count / len(text) if text else 0.0


def is_readable_text(
    text: str,
    min_chars: int = 100,
    min_alpha_ratio: float = 0.5,
) -> bool:
    """Check if extracted text is readable enough for processing.
    
    Applies configurable thresholds to filter out scanned/unreadable PDFs.
    
    Args:
        text: Extracted text
        min_chars: Minimum character count
        min_alpha_ratio: Minimum ratio of alphabetic characters (0-1)
        
    Returns:
        True if text passes readability checks
    """
    if not text or len(text) < min_chars:
        return False
    
    alpha_count = sum(1 for c in text if c.isalpha())
    alpha_ratio = alpha_count / len(text)
    
    return alpha_ratio >= min_alpha_ratio
