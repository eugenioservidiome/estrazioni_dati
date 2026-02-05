"""Path management utilities for comuni extractor."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ComunePaths:
    """Paths structure for a comune/year combination."""

    comune_dir: Path
    pdf_dir: Path
    output_dir: Path
    cache_dir: Path
    logs_dir: Path
    manifest_path: Path

    @classmethod
    def from_root(
        cls,
        output_root: str | Path,
        comune: str,
        year: int,
    ) -> "ComunePaths":
        """Create paths from output root, comune, and year.
        
        Args:
            output_root: Root output directory (e.g., "./Comuni")
            comune: Normalized comune name (e.g., "roma")
            year: Reference year (e.g., 2023)
            
        Returns:
            ComunePaths instance
        """
        comune_dir = Path(output_root) / comune / str(year)
        
        return cls(
            comune_dir=comune_dir,
            pdf_dir=comune_dir / "pdf",
            output_dir=comune_dir / "output",
            cache_dir=comune_dir / "cache",
            logs_dir=comune_dir / "logs",
            manifest_path=comune_dir / "manifest.jsonl",
        )

    def ensure_directories(self) -> None:
        """Create all directories if they don't exist."""
        self.comune_dir.mkdir(parents=True, exist_ok=True)
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        (self.cache_dir / "llm").mkdir(parents=True, exist_ok=True)
