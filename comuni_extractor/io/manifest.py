"""Manifest management for PDF tracking."""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional


@dataclass
class ManifestEntry:
    """Single entry in manifest."""
    
    pdf_url: str
    source_page_url: str
    anchor_text: str
    discovered_at: str
    status: str  # to_download|downloaded|unmatched|skipped_duplicate|failed
    
    # Fields populated after download/ingest
    local_filename: Optional[str] = None
    sha256: Optional[str] = None
    size_bytes: Optional[int] = None
    ingested_at: Optional[str] = None
    error_reason: Optional[str] = None
    
    # Additional metadata
    suggested_filename: Optional[str] = None
    content_type: Optional[str] = None


class ManifestManager:
    """Manage manifest.jsonl file for PDF tracking."""
    
    def __init__(self, manifest_path: Path):
        """Initialize manifest manager.
        
        Args:
            manifest_path: Path to manifest.jsonl file
        """
        self.manifest_path = Path(manifest_path)
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        
    def load_entries(self) -> List[ManifestEntry]:
        """Load all entries from manifest.
        
        Returns:
            List of manifest entries
        """
        if not self.manifest_path.exists():
            return []
        
        entries = []
        with open(self.manifest_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    entries.append(ManifestEntry(**data))
        
        return entries
    
    def add_entry(self, entry: ManifestEntry) -> None:
        """Add new entry to manifest.
        
        Args:
            entry: Manifest entry to add
        """
        with open(self.manifest_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(asdict(entry), ensure_ascii=False) + '\n')
    
    def update_entry(self, pdf_url: str, **updates) -> bool:
        """Update existing entry by URL.
        
        Args:
            pdf_url: PDF URL to match
            **updates: Fields to update
            
        Returns:
            True if entry was found and updated
        """
        entries = self.load_entries()
        found = False
        
        for entry in entries:
            if entry.pdf_url == pdf_url:
                for key, value in updates.items():
                    if hasattr(entry, key):
                        setattr(entry, key, value)
                found = True
                break
        
        if found:
            # Rewrite entire manifest
            self._write_all(entries)
        
        return found
    
    def _write_all(self, entries: List[ManifestEntry]) -> None:
        """Write all entries to manifest.
        
        Args:
            entries: List of entries to write
        """
        with open(self.manifest_path, 'w', encoding='utf-8') as f:
            for entry in entries:
                f.write(json.dumps(asdict(entry), ensure_ascii=False) + '\n')
    
    def get_by_status(self, status: str) -> List[ManifestEntry]:
        """Get entries by status.
        
        Args:
            status: Status to filter by
            
        Returns:
            List of matching entries
        """
        entries = self.load_entries()
        return [e for e in entries if e.status == status]
    
    def get_by_url(self, pdf_url: str) -> Optional[ManifestEntry]:
        """Get entry by URL.
        
        Args:
            pdf_url: PDF URL
            
        Returns:
            Manifest entry or None
        """
        entries = self.load_entries()
        for entry in entries:
            if entry.pdf_url == pdf_url:
                return entry
        return None
    
    def get_by_filename(self, filename: str) -> Optional[ManifestEntry]:
        """Get entry by local filename.
        
        Args:
            filename: Local filename
            
        Returns:
            Manifest entry or None
        """
        entries = self.load_entries()
        for entry in entries:
            if entry.local_filename == filename:
                return entry
        return None
    
    def count_by_status(self) -> dict:
        """Count entries by status.
        
        Returns:
            Dict of status -> count
        """
        entries = self.load_entries()
        counts = {}
        for entry in entries:
            counts[entry.status] = counts.get(entry.status, 0) + 1
        return counts
    
    def mark_downloaded(
        self,
        pdf_url: str,
        local_filename: str,
        sha256: str,
        size_bytes: int,
    ) -> bool:
        """Mark entry as downloaded.
        
        Args:
            pdf_url: PDF URL
            local_filename: Local filename
            sha256: SHA256 hash
            size_bytes: File size
            
        Returns:
            True if updated
        """
        return self.update_entry(
            pdf_url,
            status='downloaded',
            local_filename=local_filename,
            sha256=sha256,
            size_bytes=size_bytes,
            ingested_at=datetime.now().isoformat(),
        )
    
    def mark_failed(self, pdf_url: str, error_reason: str) -> bool:
        """Mark entry as failed.
        
        Args:
            pdf_url: PDF URL
            error_reason: Failure reason
            
        Returns:
            True if updated
        """
        return self.update_entry(
            pdf_url,
            status='failed',
            error_reason=error_reason,
        )
