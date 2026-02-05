"""CSV file handling for Comuni Extractor."""

import glob
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import chardet
import pandas as pd


class CSVHandler:
    """Handle CSV file operations with glob support and schema preservation."""

    def __init__(
        self,
        source_dataset_path: str | Path,
        output_dir: Optional[str | Path] = None,
    ):
        """Initialize CSV handler.
        
        Args:
            source_dataset_path: Path to dataset folder containing template CSV files
            output_dir: Path to output directory for modified CSVs (optional)
        """
        self.source_dataset_path = Path(source_dataset_path)
        self.output_dir = Path(output_dir) if output_dir else None
        self.csv_templates: Dict[int, Path] = {}
        self.csv_output_paths: Dict[int, Path] = {}
        self._discover_csv_files()

    def _discover_csv_files(self) -> None:
        """Discover CSV template files using glob patterns."""
        # Standard CSV files (01_governo, 03_risultati_pillole, etc.)
        for csv_id in [1, 3, 4, 5, 6]:
            pattern = f"{csv_id:02d}_*.csv"
            matches = list(self.source_dataset_path.glob(pattern))
            if matches:
                self.csv_templates[csv_id] = matches[0]
                if self.output_dir:
                    # Use same filename in output directory
                    self.csv_output_paths[csv_id] = self.output_dir / matches[0].name

        # Special handling for 02_territorio_popolazione*.csv
        matches_02 = list(self.source_dataset_path.glob("02_*.csv"))
        if matches_02:
            self.csv_templates[2] = matches_02[0]
            if self.output_dir:
                self.csv_output_paths[2] = self.output_dir / matches_02[0].name

    @staticmethod
    def _detect_encoding(file_path: Path) -> str:
        """Detect file encoding."""
        with open(file_path, "rb") as f:
            raw_data = f.read(100000)
            result = chardet.detect(raw_data)
            return result.get("encoding", "utf-8") or "utf-8"

    def load_csv(self, csv_id: int) -> Optional[pd.DataFrame]:
        """Load a CSV file by ID.
        
        Prefers output CSV if it exists; otherwise loads from template.
        
        Args:
            csv_id: CSV file ID (1-6)
            
        Returns:
            DataFrame or None if file not found
        """
        if csv_id not in self.csv_templates:
            return None

        # Try to load from output directory first
        if self.output_dir and csv_id in self.csv_output_paths:
            output_path = self.csv_output_paths[csv_id]
            if output_path.exists():
                encoding = self._detect_encoding(output_path)
                try:
                    return pd.read_csv(output_path, encoding=encoding)
                except Exception as e:
                    raise RuntimeError(f"Failed to load output CSV {csv_id} from {output_path}: {e}")

        # Fall back to template
        template_path = self.csv_templates[csv_id]
        encoding = self._detect_encoding(template_path)

        try:
            df = pd.read_csv(template_path, encoding=encoding)
            return df
        except Exception as e:
            raise RuntimeError(f"Failed to load template CSV {csv_id} from {template_path}: {e}")

    def load_all_csvs(self) -> Dict[int, pd.DataFrame]:
        """Load all available CSVs.
        
        Returns:
            Dictionary mapping CSV ID to DataFrame
        """
        result = {}
        for csv_id in range(1, 7):
            df = self.load_csv(csv_id)
            if df is not None:
                result[csv_id] = df
        return result

    def save_csv(self, csv_id: int, df: pd.DataFrame) -> None:
        """Save DataFrame to output directory.
        
        Args:
            csv_id: CSV file ID
            df: DataFrame to save
            
        Raises:
            ValueError: If output_dir not configured or csv_id not found
        """
        if not self.output_dir:
            raise ValueError("Cannot save CSV: output_dir not configured")

        if csv_id not in self.csv_output_paths:
            raise ValueError(f"Cannot save CSV: csv_id {csv_id} not found in templates")

        output_path = self.csv_output_paths[csv_id]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False, encoding="utf-8")

    @staticmethod
    def find_or_create_row(
        df: pd.DataFrame, comune: str, year: int, key_columns: List[str]
    ) -> Tuple[pd.DataFrame, int]:
        """Find or create a row for a specific comune and year.
        
        Args:
            df: DataFrame
            comune: Comune name
            year: Year
            key_columns: Column names to match on
            
        Returns:
            Tuple of (updated DataFrame, row index)
        """
        # Try to find matching row
        mask = None
        for col in key_columns:
            if col in df.columns:
                if col.lower() == "anno" or col.lower() == "year":
                    col_mask = df[col] == year
                elif col.lower() == "comune":
                    col_mask = df[col].astype(str).str.lower() == comune.lower()
                else:
                    continue

                if mask is None:
                    mask = col_mask
                else:
                    mask = mask & col_mask

        if mask is not None and mask.any():
            row_idx = df[mask].index[0]
            return df, row_idx

        # Create new row
        new_row = {}
        for col in df.columns:
            if col.lower() == "comune":
                new_row[col] = comune
            elif col.lower() in ["anno", "year"]:
                new_row[col] = year
            else:
                new_row[col] = None

        new_df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        return new_df, len(new_df) - 1

    @staticmethod
    def write_csv(
        df: pd.DataFrame,
        output_path: Path,
        overwrite: bool = False,
        preserve_na: bool = True,
    ) -> None:
        """Write DataFrame to CSV.
        
        Args:
            df: DataFrame to write
            output_path: Output file path
            overwrite: Whether to overwrite existing values
            preserve_na: Whether to preserve NaN/None values
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False, encoding="utf-8")

    def update_csv_value(
        self,
        csv_id: int,
        comune: str,
        year: int,
        column: str,
        value: str,
        overwrite: bool = False,
    ) -> bool:
        """Update a value in CSV and save to output directory.
        
        Args:
            csv_id: CSV file ID
            comune: Comune name
            year: Year
            column: Column name
            value: Value to set
            overwrite: Whether to overwrite existing values
            
        Returns:
            True if value was updated, False otherwise
        """
        df = self.load_csv(csv_id)
        if df is None:
            return False

        # Find or create row
        df, row_idx = self.find_or_create_row(
            df, comune, year, ["comune", "anno"]
        )

        # Check if column exists
        if column not in df.columns:
            # Add column
            df[column] = None

        # Only update if cell is empty or overwrite is True
        current_val = df.loc[row_idx, column]
        if pd.isna(current_val) or overwrite:
            df.loc[row_idx, column] = value
            
            # Save to output directory
            if self.output_dir:
                self.save_csv(csv_id, df)
            
            return True

        return False

    def get_csv_columns(self, csv_id: int) -> List[str]:
        """Get column names for a CSV.
        
        Args:
            csv_id: CSV file ID
            
        Returns:
            List of column names
        """
        df = self.load_csv(csv_id)
        if df is None:
            return []
        return list(df.columns)
