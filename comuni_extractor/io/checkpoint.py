"""Checkpoint management for resuming runs."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from comuni_extractor.models import CheckpointState


class CheckpointManager:
    """Manage checkpoint state for resuming runs."""

    def __init__(self, checkpoint_dir: Path):
        """Initialize checkpoint manager.
        
        Args:
            checkpoint_dir: Directory to store checkpoint files
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def get_checkpoint_path(self, comune: str, year: int) -> Path:
        """Get checkpoint file path for a run.
        
        Args:
            comune: Comune name
            year: Year
            
        Returns:
            Path to checkpoint file
        """
        filename = f"checkpoint_{comune}_{year}.jsonl"
        return self.checkpoint_dir / filename

    def save_checkpoint(self, state: CheckpointState) -> None:
        """Save checkpoint state to file.
        
        Args:
            state: CheckpointState to save
        """
        path = self.get_checkpoint_path(state.comune_name, state.year)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state.to_dict(), f, ensure_ascii=False, indent=2)

    def load_checkpoint(self, comune: str, year: int) -> Optional[CheckpointState]:
        """Load checkpoint state from file.
        
        Args:
            comune: Comune name
            year: Year
            
        Returns:
            CheckpointState or None if not found
        """
        path = self.get_checkpoint_path(comune, year)
        if not path.exists():
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            state = CheckpointState(
                comune_name=data["comune_name"],
                year=data["year"],
                urls_discovered=data.get("urls_discovered", []),
                pdfs_downloaded=data.get("pdfs_downloaded", []),
                pdfs_processed=data.get("pdfs_processed", []),
                fields_extracted=data.get("fields_extracted", []),
            )
            if "timestamp" in data:
                state.timestamp = datetime.fromisoformat(data["timestamp"])

            return state
        except Exception as e:
            raise RuntimeError(f"Failed to load checkpoint: {e}")

    def delete_checkpoint(self, comune: str, year: int) -> None:
        """Delete checkpoint file.
        
        Args:
            comune: Comune name
            year: Year
        """
        path = self.get_checkpoint_path(comune, year)
        if path.exists():
            path.unlink()

    def clear_old_checkpoints(self, max_age_days: int = 30) -> int:
        """Delete checkpoints older than specified days.
        
        Args:
            max_age_days: Maximum age in days
            
        Returns:
            Number of deleted checkpoints
        """
        now = datetime.utcnow()
        deleted = 0

        for checkpoint_file in self.checkpoint_dir.glob("checkpoint_*.jsonl"):
            try:
                with open(checkpoint_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if "timestamp" in data:
                    ts = datetime.fromisoformat(data["timestamp"])
                    age_days = (now - ts).days

                    if age_days > max_age_days:
                        checkpoint_file.unlink()
                        deleted += 1
            except Exception:
                continue

        return deleted
