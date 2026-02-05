"""Integration tests for PDF ingestion."""

import pytest
import hashlib
from pathlib import Path
from datetime import datetime

from comuni_extractor.io.manifest import ManifestManager, ManifestEntry
from comuni_extractor.documents.ingest import PDFIngestor


class TestPDFIngestion:
    """Test PDF ingest with matching and hashing."""

    def create_test_pdf(self, path: Path, content: str = "Test PDF content") -> str:
        """Create a test PDF file and return its SHA256 hash."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        
        # Compute hash
        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            sha256.update(f.read())
        return sha256.hexdigest()

    def test_exact_filename_match(self, tmp_path):
        """Test ingestion with exact filename match."""
        # Setup
        pdf_dir = tmp_path / "pdfs"
        downloads_dir = tmp_path / "downloads"
        manifest_path = tmp_path / "manifest.jsonl"
        
        pdf_dir.mkdir()
        downloads_dir.mkdir()

        # Create manifest with expected PDF
        manifest_mgr = ManifestManager(manifest_path)
        manifest_mgr.add_entry(
            ManifestEntry(
                pdf_url="https://comune.test.it/docs/bilancio_2023.pdf",
                source_page_url="https://comune.test.it/",
                anchor_text="Bilancio 2023",
                discovered_at=datetime.now().isoformat(),
                status="to_download",
                suggested_filename="bilancio_2023.pdf",
            )
        )

        # Create matching PDF in downloads
        pdf_file = downloads_dir / "bilancio_2023.pdf"
        expected_hash = self.create_test_pdf(pdf_file, "Bilancio content")

        # Ingest
        ingestor = PDFIngestor(pdf_dir, manifest_mgr, interactive=False)
        matched, unmatched, skipped = ingestor.ingest_downloads(downloads_dir, move=False)

        # Assertions
        assert matched == 1
        assert unmatched == 0
        assert skipped == 0

        # Check PDF was copied to pdf_dir
        ingested_pdf = pdf_dir / "bilancio_2023.pdf"
        assert ingested_pdf.exists()

        # Check manifest was updated
        entries = manifest_mgr.load_entries()
        entry = next(e for e in entries if "bilancio_2023.pdf" in e.pdf_url)
        assert entry.status == "downloaded"
        assert entry.local_filename == "bilancio_2023.pdf"
        assert entry.sha256 == expected_hash
        assert entry.size_bytes == pdf_file.stat().st_size

    def test_duplicate_detection_by_hash(self, tmp_path):
        """Test that duplicate PDFs are skipped."""
        pdf_dir = tmp_path / "pdfs"
        downloads_dir = tmp_path / "downloads"
        manifest_path = tmp_path / "manifest.jsonl"
        
        pdf_dir.mkdir()
        downloads_dir.mkdir()

        # Create manifest
        manifest_mgr = ManifestManager(manifest_path)
        manifest_mgr.add_entry(
            ManifestEntry(
                pdf_url="https://comune.test.it/docs/file.pdf",
                source_page_url="https://comune.test.it/",
                anchor_text="File",
                discovered_at=datetime.now().isoformat(),
                status="to_download",
                suggested_filename="file.pdf",
            )
        )

        # First ingestion
        pdf_file1 = downloads_dir / "file.pdf"
        pdf_hash = self.create_test_pdf(pdf_file1, "Content")
        
        ingestor = PDFIngestor(pdf_dir, manifest_mgr, interactive=False)
        matched1, _, _ = ingestor.ingest_downloads(downloads_dir, move=True)
        assert matched1 == 1

        # Try to ingest same content with different filename
        pdf_file2 = downloads_dir / "file_duplicate.pdf"
        self.create_test_pdf(pdf_file2, "Content")  # Same content = same hash
        
        manifest_mgr.add_entry(
            ManifestEntry(
                pdf_url="https://comune.test.it/docs/file2.pdf",
                source_page_url="https://comune.test.it/",
                anchor_text="File 2",
                discovered_at=datetime.now().isoformat(),
                status="to_download",
                suggested_filename="file_duplicate.pdf",
            )
        )

        matched2, unmatched2, skipped2 = ingestor.ingest_downloads(downloads_dir, move=False)
        
        # Should be skipped as duplicate
        assert skipped2 == 1
        assert matched2 == 0

    def test_unmatched_pdfs_create_manifest_entries(self, tmp_path):
        """Test that PDFs without manifest entry are recorded as unmatched."""
        pdf_dir = tmp_path / "pdfs"
        downloads_dir = tmp_path / "downloads"
        manifest_path = tmp_path / "manifest.jsonl"
        
        pdf_dir.mkdir()
        downloads_dir.mkdir()

        # Empty manifest
        manifest_mgr = ManifestManager(manifest_path)

        # Create PDF in downloads
        orphan_pdf = downloads_dir / "orphan.pdf"
        self.create_test_pdf(orphan_pdf, "Orphan content")

        # Ingest
        ingestor = PDFIngestor(pdf_dir, manifest_mgr, interactive=False)
        matched, unmatched, skipped = ingestor.ingest_downloads(downloads_dir, move=False)

        # Assertions
        assert matched == 0
        assert unmatched == 1
        assert skipped == 0

        # Check manifest has unmatched entry
        entries = manifest_mgr.load_entries()
        assert len(entries) == 1
        entry = entries[0]
        assert entry.status == "unmatched"
        assert entry.pdf_url.startswith("local://")
        assert "orphan.pdf" in entry.local_filename

    def test_move_vs_copy(self, tmp_path):
        """Test that move=True removes source file."""
        pdf_dir = tmp_path / "pdfs"
        downloads_dir = tmp_path / "downloads"
        manifest_path = tmp_path / "manifest.jsonl"
        
        pdf_dir.mkdir()
        downloads_dir.mkdir()

        manifest_mgr = ManifestManager(manifest_path)
        manifest_mgr.add_entry(
            ManifestEntry(
                pdf_url="https://comune.test.it/docs/test.pdf",
                source_page_url="https://comune.test.it/",
                anchor_text="Test",
                discovered_at=datetime.now().isoformat(),
                status="to_download",
                suggested_filename="test.pdf",
            )
        )

        # Test copy (move=False)
        pdf_copy = downloads_dir / "test.pdf"
        self.create_test_pdf(pdf_copy, "Content")
        
        ingestor = PDFIngestor(pdf_dir, manifest_mgr, interactive=False)
        ingestor.ingest_downloads(downloads_dir, move=False)
        
        assert pdf_copy.exists()  # Should still exist
        assert (pdf_dir / "test.pdf").exists()  # Should be copied

        # Clean up for move test
        (pdf_dir / "test.pdf").unlink()
        
        # Test move (move=True)
        pdf_move = downloads_dir / "test2.pdf"
        self.create_test_pdf(pdf_move, "Content 2")
        
        manifest_mgr.add_entry(
            ManifestEntry(
                pdf_url="https://comune.test.it/docs/test2.pdf",
                source_page_url="https://comune.test.it/",
                anchor_text="Test 2",
                discovered_at=datetime.now().isoformat(),
                status="to_download",
                suggested_filename="test2.pdf",
            )
        )
        
        ingestor.ingest_downloads(downloads_dir, move=True)
        
        assert not pdf_move.exists()  # Should be moved
        assert (pdf_dir / "test2.pdf").exists()  # Should be in destination

    def test_anti_overwrite_with_counter_suffix(self, tmp_path):
        """Test that existing files get counter suffix (_1, _2, etc.)."""
        pdf_dir = tmp_path / "pdfs"
        downloads_dir = tmp_path / "downloads"
        manifest_path = tmp_path / "manifest.jsonl"
        
        pdf_dir.mkdir()
        downloads_dir.mkdir()

        # Pre-create existing file
        existing_pdf = pdf_dir / "documento.pdf"
        self.create_test_pdf(existing_pdf, "Existing content")

        manifest_mgr = ManifestManager(manifest_path)
        manifest_mgr.add_entry(
            ManifestEntry(
                pdf_url="https://comune.test.it/docs/documento.pdf",
                source_page_url="https://comune.test.it/",
                anchor_text="Documento",
                discovered_at=datetime.now().isoformat(),
                status="to_download",
                suggested_filename="documento.pdf",
            )
        )

        # Create new PDF with same name (different content)
        new_pdf = downloads_dir / "documento.pdf"
        self.create_test_pdf(new_pdf, "New content")

        # Ingest
        ingestor = PDFIngestor(pdf_dir, manifest_mgr, interactive=False)
        matched, _, _ = ingestor.ingest_downloads(downloads_dir, move=False)

        assert matched == 1

        # Check that new file has counter suffix
        assert existing_pdf.exists()  # Original still there
        assert (pdf_dir / "documento_1.pdf").exists()  # New one with suffix

        # Check manifest
        entries = manifest_mgr.load_entries()
        entry = entries[0]
        assert entry.local_filename == "documento_1.pdf"
