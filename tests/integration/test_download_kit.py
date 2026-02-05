"""Integration tests for download kit generation."""

import pytest
import csv
from pathlib import Path
from datetime import datetime

from comuni_extractor.io.manifest import ManifestEntry
from comuni_extractor.io.kit_writer import DownloadKitWriter


class TestDownloadKitGeneration:
    """Test download kit HTML and CSV generation."""

    def test_generate_kit_creates_both_files(self, tmp_path):
        """Test that generate_kit creates both HTML and CSV files."""
        # Sample manifest entries
        entries = [
            ManifestEntry(
                pdf_url="https://comune.test.it/docs/bilancio_2023.pdf",
                source_page_url="https://comune.test.it/bilanci",
                anchor_text="Bilancio Previsione 2023",
                discovered_at=datetime.now().isoformat(),
                status="to_download",
            ),
            ManifestEntry(
                pdf_url="https://servizipubblicaamministrazione.it/doc.pdf?id=123",
                source_page_url="https://comune.test.it/documenti",
                anchor_text="Documento Ufficiale",
                discovered_at=datetime.now().isoformat(),
                status="to_download",
            ),
        ]

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        kit_writer = DownloadKitWriter(output_dir=output_dir)
        html_path, csv_path = kit_writer.generate_kit(
            entries=entries, comune="test", year="2023"
        )

        # Check files exist
        assert html_path.exists()
        assert csv_path.exists()

        # Check filenames
        assert html_path.name == "links_test_2023.html"
        assert csv_path.name == "links_test_2023.csv"

    def test_html_contains_all_pdfs(self, tmp_path):
        """Test that HTML file contains all PDF URLs."""
        entries = [
            ManifestEntry(
                pdf_url=f"https://comune.test.it/docs/file{i}.pdf",
                source_page_url="https://comune.test.it/",
                anchor_text=f"File {i}",
                discovered_at=datetime.now().isoformat(),
                status="to_download",
            )
            for i in range(5)
        ]

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        kit_writer = DownloadKitWriter(output_dir=output_dir)
        html_path, _ = kit_writer.generate_kit(entries, "test", "2023")

        html_content = html_path.read_text(encoding="utf-8")

        # Check all PDF URLs are present
        for entry in entries:
            assert entry.pdf_url in html_content
            assert entry.anchor_text in html_content

        # Check HTML structure
        assert "<html" in html_content
        assert "</html>" in html_content

    def test_csv_has_correct_columns(self, tmp_path):
        """Test that CSV file has exactly 5 expected columns."""
        entries = [
            ManifestEntry(
                pdf_url="https://comune.test.it/docs/bilancio.pdf",
                source_page_url="https://comune.test.it/bilanci",
                anchor_text="Bilancio 2023",
                discovered_at="2024-01-15T10:30:00",
                status="to_download",
            ),
        ]

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        kit_writer = DownloadKitWriter(output_dir=output_dir)
        _, csv_path = kit_writer.generate_kit(entries, "test", "2023")

        # Read CSV
        with open(csv_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Check columns
        assert len(rows) == 1
        row = rows[0]
        assert "url" in row
        assert "suggested_filename" in row
        assert "source_page_url" in row
        assert "anchor_text" in row
        assert "discovered_at" in row

        # Check values
        assert row["url"] == "https://comune.test.it/docs/bilancio.pdf"
        assert row["source_page_url"] == "https://comune.test.it/bilanci"
        assert row["anchor_text"] == "Bilancio 2023"
        assert row["discovered_at"] == "2024-01-15T10:30:00"
        assert "bilancio.pdf" in row["suggested_filename"]

    def test_csv_handles_special_characters(self, tmp_path):
        """Test CSV properly escapes special characters."""
        entries = [
            ManifestEntry(
                pdf_url="https://comune.test.it/docs/file,with,commas.pdf",
                source_page_url="https://comune.test.it/page?q=test&year=2023",
                anchor_text='Documento "Importante"',
                discovered_at=datetime.now().isoformat(),
                status="to_download",
            ),
        ]

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        kit_writer = DownloadKitWriter(output_dir=output_dir)
        _, csv_path = kit_writer.generate_kit(entries, "test", "2023")

        # Read CSV
        with open(csv_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Should parse correctly despite special characters
        assert len(rows) == 1
        row = rows[0]
        assert "file,with,commas.pdf" in row["url"]
        assert "year=2023" in row["source_page_url"]
        assert '"Importante"' in row["anchor_text"]

    def test_suggested_filename_extraction(self, tmp_path):
        """Test that suggested filenames are extracted correctly."""
        entries = [
            ManifestEntry(
                pdf_url="https://comune.test.it/docs/path/to/bilancio_previsione_2023.pdf",
                source_page_url="https://comune.test.it/",
                anchor_text="Bilancio",
                discovered_at=datetime.now().isoformat(),
                status="to_download",
            ),
            ManifestEntry(
                pdf_url="https://server.it/download?file=documento.pdf&id=123",
                source_page_url="https://comune.test.it/",
                anchor_text="Documento",
                discovered_at=datetime.now().isoformat(),
                status="to_download",
            ),
        ]

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        kit_writer = DownloadKitWriter(output_dir=output_dir)
        _, csv_path = kit_writer.generate_kit(entries, "test", "2023")

        with open(csv_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Check extracted filenames
        assert rows[0]["suggested_filename"] == "bilancio_previsione_2023.pdf"
        # When no clear filename in path, should suggest something reasonable
        assert "pdf" in rows[1]["suggested_filename"].lower()
