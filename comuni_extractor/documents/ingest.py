"""Ingest locally downloaded PDFs."""

import hashlib
import shutil
from pathlib import Path
from typing import List, Optional, Tuple
from difflib import SequenceMatcher

from comuni_extractor.io.manifest import ManifestEntry, ManifestManager


class PDFIngestor:
    """Ingest and match locally downloaded PDFs."""
    
    def __init__(
        self,
        pdf_dir: Path,
        manifest_manager: ManifestManager,
        interactive: bool = False,
    ):
        """Initialize ingestor.
        
        Args:
            pdf_dir: Directory to store PDFs
            manifest_manager: Manifest manager
            interactive: Enable interactive matching
        """
        self.pdf_dir = Path(pdf_dir)
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_manager = manifest_manager
        self.interactive = interactive
    
    def ingest_downloads(
        self,
        downloads_dir: Path,
        move: bool = False,
    ) -> Tuple[int, int, int]:
        """Ingest PDFs from downloads directory.
        
        Args:
            downloads_dir: Directory containing downloaded PDFs
            move: Move files instead of copying
            
        Returns:
            Tuple of (matched, unmatched, skipped)
        """
        downloads_dir = Path(downloads_dir)
        if not downloads_dir.exists():
            raise ValueError(f"Downloads directory not found: {downloads_dir}")
        
        # Find all PDFs
        pdf_files = list(downloads_dir.glob("*.pdf")) + list(downloads_dir.glob("*.PDF"))
        
        if not pdf_files:
            return 0, 0, 0
        
        # Get manifest entries to match against
        to_download = self.manifest_manager.get_by_status('to_download')
        
        matched = 0
        unmatched = 0
        skipped = 0
        
        for pdf_path in pdf_files:
            # Check if already ingested
            if self._is_already_ingested(pdf_path):
                skipped += 1
                continue
            
            # Try to match PDF to manifest entry
            entry = self._match_pdf_to_entry(pdf_path, to_download)
            
            if entry:
                # Matched: copy/move and update manifest
                success = self._process_matched_pdf(pdf_path, entry, move)
                if success:
                    matched += 1
                else:
                    unmatched += 1
            else:
                # Unmatched: still copy/move but mark as unmatched
                success = self._process_unmatched_pdf(pdf_path, move)
                if success:
                    unmatched += 1
        
        return matched, unmatched, skipped
    
    def _is_already_ingested(self, pdf_path: Path) -> bool:
        """Check if PDF is already ingested.
        
        Args:
            pdf_path: PDF file path
            
        Returns:
            True if already ingested
        """
        # Check by filename
        entry = self.manifest_manager.get_by_filename(pdf_path.name)
        if entry and entry.status == 'downloaded':
            return True
        
        # Check by hash
        file_hash = self._compute_hash(pdf_path)
        entries = self.manifest_manager.get_by_status('downloaded')
        for entry in entries:
            if entry.sha256 == file_hash:
                return True
        
        return False
    
    def _match_pdf_to_entry(
        self,
        pdf_path: Path,
        candidate_entries: List[ManifestEntry],
    ) -> Optional[ManifestEntry]:
        """Match PDF file to manifest entry.
        
        Args:
            pdf_path: PDF file path
            candidate_entries: List of candidate entries
            
        Returns:
            Matched entry or None
        """
        filename = pdf_path.name.lower()
        
        # Strategy 1: Exact match on suggested_filename
        for entry in candidate_entries:
            if entry.suggested_filename and entry.suggested_filename.lower() == filename:
                return entry
        
        # Strategy 2: Similarity matching on anchor_text
        best_match = None
        best_score = 0.6  # Minimum similarity threshold
        
        for entry in candidate_entries:
            # Compare filename to anchor_text
            anchor_clean = self._clean_for_comparison(entry.anchor_text)
            filename_clean = self._clean_for_comparison(pdf_path.stem)
            
            score = SequenceMatcher(None, filename_clean, anchor_clean).ratio()
            
            if score > best_score:
                best_score = score
                best_match = entry
        
        # Strategy 3: Interactive matching (if enabled)
        if not best_match and self.interactive:
            best_match = self._interactive_match(pdf_path, candidate_entries)
        
        return best_match
    
    def _clean_for_comparison(self, text: str) -> str:
        """Clean text for comparison.
        
        Args:
            text: Text to clean
            
        Returns:
            Cleaned text
        """
        import re
        # Remove special chars, lowercase, collapse whitespace
        text = re.sub(r'[^a-z0-9\s]', '', text.lower())
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def _interactive_match(
        self,
        pdf_path: Path,
        candidate_entries: List[ManifestEntry],
    ) -> Optional[ManifestEntry]:
        """Interactive matching prompt.
        
        Args:
            pdf_path: PDF file path
            candidate_entries: List of candidates
            
        Returns:
            Selected entry or None
        """
        print(f"\n❓ Match PDF: {pdf_path.name}")
        print("\nCandidati:")
        for i, entry in enumerate(candidate_entries[:10], 1):
            print(f"{i}. {entry.anchor_text[:60]}")
            print(f"   URL: {entry.pdf_url[:80]}")
        
        print("0. Nessuno (unmatched)")
        
        try:
            choice = int(input("\nScegli (0-{}): ".format(len(candidate_entries[:10]))))
            if 1 <= choice <= len(candidate_entries[:10]):
                return candidate_entries[choice - 1]
        except (ValueError, KeyboardInterrupt):
            pass
        
        return None
    
    def _process_matched_pdf(
        self,
        pdf_path: Path,
        entry: ManifestEntry,
        move: bool,
    ) -> bool:
        """Process matched PDF.
        
        Args:
            pdf_path: PDF file path
            entry: Matched manifest entry
            move: Move instead of copy
            
        Returns:
            True if successful
        """
        try:
            # Compute hash and size
            file_hash = self._compute_hash(pdf_path)
            file_size = pdf_path.stat().st_size
            
            # Determine destination filename
            dest_name = entry.suggested_filename or pdf_path.name
            dest_path = self.pdf_dir / dest_name
            
            # Avoid overwriting
            if dest_path.exists():
                stem = dest_path.stem
                suffix = dest_path.suffix
                counter = 1
                while dest_path.exists():
                    dest_path = self.pdf_dir / f"{stem}_{counter}{suffix}"
                    counter += 1
            
            # Copy or move
            if move:
                shutil.move(str(pdf_path), str(dest_path))
            else:
                shutil.copy2(str(pdf_path), str(dest_path))
            
            # Update manifest
            self.manifest_manager.mark_downloaded(
                pdf_url=entry.pdf_url,
                local_filename=dest_path.name,
                sha256=file_hash,
                size_bytes=file_size,
            )
            
            return True
        
        except Exception as e:
            self.manifest_manager.mark_failed(
                pdf_url=entry.pdf_url,
                error_reason=f"Ingest failed: {str(e)}",
            )
            return False
    
    def _process_unmatched_pdf(
        self,
        pdf_path: Path,
        move: bool,
    ) -> bool:
        """Process unmatched PDF.
        
        Args:
            pdf_path: PDF file path
            move: Move instead of copy
            
        Returns:
            True if successful
        """
        try:
            # Compute hash and size
            file_hash = self._compute_hash(pdf_path)
            file_size = pdf_path.stat().st_size
            
            # Copy or move to pdf_dir
            dest_path = self.pdf_dir / pdf_path.name
            
            # Avoid overwriting
            if dest_path.exists():
                stem = dest_path.stem
                suffix = dest_path.suffix
                counter = 1
                while dest_path.exists():
                    dest_path = self.pdf_dir / f"{stem}_{counter}{suffix}"
                    counter += 1
            
            if move:
                shutil.move(str(pdf_path), str(dest_path))
            else:
                shutil.copy2(str(pdf_path), str(dest_path))
            
            # Add to manifest as unmatched
            from datetime import datetime
            from comuni_extractor.io.manifest import ManifestEntry
            
            unmatched_entry = ManifestEntry(
                pdf_url=f"local://{pdf_path.name}",
                source_page_url="unknown",
                anchor_text="unmatched_local_file",
                discovered_at=datetime.now().isoformat(),
                status='unmatched',
                local_filename=dest_path.name,
                sha256=file_hash,
                size_bytes=file_size,
                ingested_at=datetime.now().isoformat(),
            )
            
            self.manifest_manager.add_entry(unmatched_entry)
            
            return True
        
        except Exception:
            return False
    
    def _compute_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of file.
        
        Args:
            file_path: File path
            
        Returns:
            SHA256 hex digest
        """
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()
