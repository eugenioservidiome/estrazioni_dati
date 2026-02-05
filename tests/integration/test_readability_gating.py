"""Integration tests for readability gating."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from comuni_extractor.documents.pdf_extractor import PDFTextExtractor, is_readable_text
from comuni_extractor.pipeline.orchestrator import PipelineOrchestrator


class TestReadabilityGating:
    """Test that unreadable PDFs are skipped before LLM calls."""

    def test_is_readable_text_with_good_text(self):
        """Test that readable text passes the gate."""
        good_text = """
        Questo è un documento leggibile con molto testo in italiano.
        Contiene abbastanza caratteri alfabetici e parole riconoscibili.
        Bilancio di previsione per l'anno 2023.
        Entrate totali: 1.500.000 euro.
        """
        
        result = is_readable_text(good_text, min_chars=100, min_alpha_ratio=0.5)
        assert result is True

    def test_is_readable_text_with_scanned_garbage(self):
        """Test that scanned/garbage text fails the gate."""
        # Simulate OCR garbage with low alpha ratio
        bad_text = "|||###123456789@@@!!!***%%%^^^&&&((()))" * 10
        
        result = is_readable_text(bad_text, min_chars=100, min_alpha_ratio=0.5)
        assert result is False

    def test_is_readable_text_too_short(self):
        """Test that very short text fails the gate."""
        short_text = "ABC"
        
        result = is_readable_text(short_text, min_chars=100, min_alpha_ratio=0.5)
        assert result is False

    def test_is_readable_text_low_alpha_ratio(self):
        """Test that text with too many non-alpha chars fails."""
        # 50 chars total, only 20 alpha (40% ratio)
        low_alpha = "a" * 20 + "1234567890!@#$%^&*()" * 1.5
        
        result = is_readable_text(low_alpha, min_chars=40, min_alpha_ratio=0.5)
        assert result is False

    @patch("comuni_extractor.pipeline.orchestrator.PDFTextExtractor")
    @patch("comuni_extractor.pipeline.orchestrator.LLMClient")
    def test_orchestrator_skips_llm_on_unreadable_pdf(
        self, mock_llm_client_class, mock_pdf_extractor_class, tmp_path
    ):
        """Test that orchestrator doesn't call LLM for unreadable PDFs."""
        # Setup
        pdf_dir = tmp_path / "pdfs"
        output_dir = tmp_path / "output"
        guide_path = tmp_path / "guida_compilazione.csv"
        
        pdf_dir.mkdir()
        output_dir.mkdir()
        
        # Create simple guide file
        guide_path.write_text(
            "anno,tipo_bilancio,campo,descrizione\n"
            "2023,previsione,entrate_totali,Entrate totali previste\n"
        )

        # Create a test PDF
        test_pdf = pdf_dir / "test.pdf"
        test_pdf.write_bytes(b"PDF content")  # Dummy bytes

        # Mock PDF extractor to return unreadable text
        mock_extractor_instance = Mock()
        mock_extractor_instance.extract_text.return_value = "|||###123" * 5  # Garbage
        mock_pdf_extractor_class.return_value = mock_extractor_instance

        # Mock LLM client
        mock_llm_instance = Mock()
        mock_llm_client_class.return_value = mock_llm_instance

        # Create orchestrator
        orchestrator = PipelineOrchestrator(
            comune="test",
            year="2023",
            output_dir=output_dir,
        )

        # Run analyze phase
        report = orchestrator.run_analyze(
            pdf_dir=pdf_dir,
            guide_path=guide_path,
            overwrite=False,
        )

        # Assertions
        # LLM client should NOT have been called for unreadable PDF
        assert mock_llm_instance.extract_fields.call_count == 0
        
        # PDF should be in failed/skipped count
        assert report.stats["pdfs_failed"] >= 1 or report.stats.get("pdfs_skipped", 0) >= 1

    @patch("comuni_extractor.pipeline.orchestrator.PDFTextExtractor")
    @patch("comuni_extractor.pipeline.orchestrator.LLMClient")
    def test_orchestrator_calls_llm_on_readable_pdf(
        self, mock_llm_client_class, mock_pdf_extractor_class, tmp_path
    ):
        """Test that orchestrator DOES call LLM for readable PDFs."""
        # Setup
        pdf_dir = tmp_path / "pdfs"
        output_dir = tmp_path / "output"
        guide_path = tmp_path / "guida_compilazione.csv"
        
        pdf_dir.mkdir()
        output_dir.mkdir()
        
        # Create guide file
        guide_path.write_text(
            "anno,tipo_bilancio,campo,descrizione\n"
            "2023,previsione,entrate_totali,Entrate totali previste\n"
        )

        # Create test PDF
        test_pdf = pdf_dir / "bilancio.pdf"
        test_pdf.write_bytes(b"PDF content")

        # Mock PDF extractor to return READABLE text
        readable_text = """
        Bilancio di Previsione 2023
        Comune di Test
        
        Entrate Totali: 1.500.000 euro
        Spese Correnti: 1.200.000 euro
        Investimenti: 300.000 euro
        """ * 5  # Enough text to pass readability
        
        mock_extractor_instance = Mock()
        mock_extractor_instance.extract_text.return_value = readable_text
        mock_pdf_extractor_class.return_value = mock_extractor_instance

        # Mock LLM client to return extraction result
        mock_llm_instance = Mock()
        mock_result = Mock()
        mock_result.extracted_fields = {"entrate_totali": "1500000"}
        mock_result.confidence_score = 0.9
        mock_result.model_name = "gpt-4"
        mock_result.tipo_bilancio = "previsione"
        mock_result.chunks_used = []
        mock_llm_instance.extract_fields.return_value = mock_result
        mock_llm_client_class.return_value = mock_llm_instance

        # Create orchestrator
        orchestrator = PipelineOrchestrator(
            comune="test",
            year="2023",
            output_dir=output_dir,
        )

        # Run analyze phase
        report = orchestrator.run_analyze(
            pdf_dir=pdf_dir,
            guide_path=guide_path,
            overwrite=False,
        )

        # Assertions
        # LLM should have been called for readable PDF
        assert mock_llm_instance.extract_fields.call_count >= 1
        
        # PDF should be in downloaded (processed) count
        assert report.stats.get("pdfs_downloaded", 0) >= 1

    def test_configurable_readability_thresholds(self):
        """Test that readability thresholds can be configured."""
        text = "a" * 60 + "1234567890" * 4  # 60 alpha, 40 non-alpha = 60% ratio
        
        # Should pass with 50% threshold
        assert is_readable_text(text, min_chars=50, min_alpha_ratio=0.5) is True
        
        # Should fail with 70% threshold
        assert is_readable_text(text, min_chars=50, min_alpha_ratio=0.7) is False
        
        # Should fail if min_chars too high
        assert is_readable_text(text, min_chars=200, min_alpha_ratio=0.5) is False
