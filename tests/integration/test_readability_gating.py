"""Integration tests for readability gating."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from comuni_extractor.documents.pdf_extractor import is_readable_text
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
        # 50 chars total, only 20 alpha (40% ratio < 0.5 threshold)
        low_alpha = "a" * 20 + "1234567890!@#$%^&*()" + "1234567890"
        
        result = is_readable_text(low_alpha, min_chars=40, min_alpha_ratio=0.5)
        assert result is False

    @pytest.mark.timeout(90)
    @patch("comuni_extractor.pipeline.orchestrator.extract_text_from_pdf")
    @patch("comuni_extractor.pipeline.orchestrator.LLMClient")
    @patch("comuni_extractor.pipeline.orchestrator.CSVHandler")
    @patch("comuni_extractor.pipeline.orchestrator.ReportGenerator")
    @patch("comuni_extractor.pipeline.orchestrator.TextChunker")
    @patch("comuni_extractor.pipeline.orchestrator.TFIDFIndexer")
    def test_orchestrator_skips_llm_on_unreadable_pdf(
        self, mock_indexer_class, mock_chunker_class, mock_report_gen_class, 
        mock_csv_handler_class, mock_llm_client_class, mock_extract_pdf, tmp_path
    ):
        """Test that orchestrator doesn't call LLM for unreadable PDFs."""
        from comuni_extractor.config import AppConfig
        from comuni_extractor.models import FieldSpec, FieldDataType
        from comuni_extractor.io.guide_parser import GuideParser
        
        # Setup paths
        pdf_dir = tmp_path / "pdfs"
        output_dir = tmp_path / "output"
        guide_path = tmp_path / "guide.md"
        dataset_path = tmp_path / "dataset"
        
        pdf_dir.mkdir()
        output_dir.mkdir()
        dataset_path.mkdir()
        
        # Create test CSV templates
        for csv_id in [1, 2, 3, 4, 5, 6]:
            csv_file = dataset_path / f"{csv_id:02d}_test.csv"
            csv_file.write_text("comune,anno\n")
        
        # Create simple guide
        guide_path.write_text(
            "# Guide\\n\\n## campo1\\ndescrizione\\ncsv_id: 1\\ncolumn: test_col"
        )

        # Create a test PDF
        test_pdf = pdf_dir / "test.pdf"
        test_pdf.write_bytes(b"<PDF content>")  # Dummy

        # Mock extract_text_from_pdf to return  unreadable text
        mock_extract_pdf.return_value = "|||###123" * 10  # Garbage

        # Mock LLM client
        mock_llm_instance = Mock()
        mock_llm_client_class.return_value = mock_llm_instance
        
        # Configure mock to return proper ExtractionResult if called
        from comuni_extractor.models import ExtractionResult
        mock_llm_instance.extract_field_candidates.return_value = ExtractionResult(
            field_name="campo1",
            csv_id=1,
            column="test_col",
            data_type=FieldDataType.TEXT,
            candidates=[]
        )
        
        # Mock other components
        mock_csv_instance = Mock()
        mock_csv_handler_class.return_value = mock_csv_instance
        mock_csv_instance.update_csv_value.return_value = False
        
        mock_report_instance = Mock()
        mock_report_gen_class.return_value = mock_report_instance
        mock_report_instance.save_report.return_value = output_dir / "report.json"
        
        mock_chunker_instance = Mock()
        mock_chunker_class.return_value = mock_chunker_instance
        mock_chunker_instance.chunk.return_value = []
        
        mock_indexer_instance = Mock()
        mock_indexer_class.return_value = mock_indexer_instance

        # Create config
        config = AppConfig()
        config.paths.drive_dataset_path = str(dataset_path)
        config.paths.output_root = str(output_dir)

        # Create orchestrator
        orchestrator = PipelineOrchestrator(
            config=config,
            comune="testcomune",
            year=2023,
            openai_key="test-key",
        )

        # Mock GuideParser
        with patch.object(GuideParser, "parse") as mock_parse:
            mock_parse.return_value = [
                FieldSpec(
                    name="campo1",
                    csv_id=1,
                    column="test_col",
                    description="test field",
                    data_type=FieldDataType.TEXT,
                )
            ]

            # Run analyze
            report = orchestrator.run_analyze(
                pdf_dir=pdf_dir,
                guide_path=guide_path,
                overwrite=False,
            )

        # Verify: LLM should NOT be called because PDF was unreadable
        assert mock_llm_instance.extract_field_candidates.call_count == 0
        
        # Verify stats show failed PDF
        assert report.stats.download_stats.pdfs_failed > 0
        assert report.stats.download_stats.pdfs_successful == 0

    @pytest.mark.timeout(90)
    @patch("comuni_extractor.pipeline.orchestrator.extract_text_from_pdf")
    @patch("comuni_extractor.pipeline.orchestrator.LLMClient")
    @patch("comuni_extractor.pipeline.orchestrator.CSVHandler")
    @patch("comuni_extractor.pipeline.orchestrator.ReportGenerator")
    @patch("comuni_extractor.pipeline.orchestrator.TextChunker")
    @patch("comuni_extractor.pipeline.orchestrator.TFIDFIndexer")
    def test_orchestrator_calls_llm_on_readable_pdf(
        self, mock_indexer_class, mock_chunker_class, mock_report_gen_class, 
        mock_csv_handler_class, mock_llm_client_class, mock_extract_pdf, tmp_path
    ):
        """Test that orchestrator DOES call LLM for readable PDFs."""
        from comuni_extractor.config import AppConfig
        from comuni_extractor.models import FieldSpec, FieldDataType
        from comuni_extractor.io.guide_parser import GuideParser
        
        # Setup paths
        pdf_dir = tmp_path / "pdfs"
        output_dir = tmp_path / "output"
        guide_path = tmp_path / "guide.md"
        dataset_path = tmp_path / "dataset"
        
        pdf_dir.mkdir()
        output_dir.mkdir()
        dataset_path.mkdir()
        
        # Create test CSV templates
        for csv_id in [1, 2, 3, 4, 5, 6]:
            csv_file = dataset_path / f"{csv_id:02d}_test.csv"
            csv_file.write_text("comune,anno\n")
        
        # Create simple guide
        guide_path.write_text(
            "# Guide\\n\\n## campo1\\ndescrizione\\ncsv_id: 1\\ncolumn: test_col"
        )

        # Create a test PDF
        test_pdf = pdf_dir / "test.pdf"
        test_pdf.write_bytes(b"<PDF content>")  # Dummy

        # Mock extract_text_from_pdf to return READABLE text
        readable_text = """
        Bilancio di Previsione 2023
        Comune di Test
        
        Entrate Totali: 1.500.000 euro
        Spese Correnti: 1.200.000 euro
        Investimenti: 300.000 euro
        """ * 5  # Enough text to pass readability
        
        mock_extract_pdf.return_value = readable_text

        # Mock LLM client
        mock_llm_instance = Mock()
        mock_llm_client_class.return_value = mock_llm_instance
        
        # Configure mock to return proper ExtractionResult with candidates
        from comuni_extractor.models import ExtractionResult, ExtractionCandidate, ValueType as ValueTypeEnum
        mock_llm_instance.extract_field_candidates.return_value = ExtractionResult(
            field_name="campo1",
            csv_id=1,
            column="test_col",
            data_type=FieldDataType.TEXT,
            candidates=[
                ExtractionCandidate(
                    value="500000",
                    value_type=ValueTypeEnum.DEFINITIVO,
                    confidence=0.9,
                    source_pdf="test.pdf",
                    evidence="Entrate Totali: 1.500.000 euro",
                )
            ]
        )
        
        # Mock other components
        mock_csv_instance = Mock()
        mock_csv_handler_class.return_value = mock_csv_instance
        mock_csv_instance.update_csv_value.return_value = True
        
        mock_report_instance = Mock()
        mock_report_gen_class.return_value = mock_report_instance
        mock_report_instance.save_report.return_value = output_dir / "report.json"
        
        mock_chunker_instance = Mock()
        mock_chunker_class.return_value = mock_chunker_instance
        # Configure chunker to return some test chunks
        from comuni_extractor.retrieval.chunker import TextChunk
        test_chunk = TextChunk(
            text="Bilancio di Previsione 2023",
            start_pos=0,
            end_pos=30,
            chunk_id="test_chunk_1"
        )
        mock_chunker_instance.chunk.return_value = [test_chunk]
        
        mock_indexer_instance = Mock()
        mock_indexer_class.return_value = mock_indexer_instance
        # Configure indexer.build to accept anything
        mock_indexer_instance.build.return_value = None
        # Configure indexer.search to return the test chunk with a score
        mock_indexer_instance.search.return_value = [(test_chunk, 0.8)]

        # Create config
        config = AppConfig()
        config.paths.drive_dataset_path = str(dataset_path)
        config.paths.output_root = str(output_dir)

        # Create orchestrator
        orchestrator = PipelineOrchestrator(
            config=config,
            comune="testcomune",
            year=2023,
            openai_key="test-key",
        )

        # Mock GuideParser
        with patch.object(GuideParser, "parse") as mock_parse:
            mock_parse.return_value = [
                FieldSpec(
                    name="campo1",
                    csv_id=1,
                    column="test_col",
                    description="test field",
                    data_type=FieldDataType.TEXT,
                )
            ]
            
            # Run analyze
            report = orchestrator.run_analyze(
                pdf_dir=pdf_dir,
                guide_path=guide_path,
                overwrite=False,
            )

        # Verify: LLM SHOULD be called because PDF was readable
        assert mock_llm_instance.extract_field_candidates.call_count > 0
        
        # Verify stats show successful PDF processing
        assert report.stats.download_stats.pdfs_successful > 0

    def test_configurable_readability_thresholds(self):
        """Test that readability thresholds can be configured."""
        text = "a" * 60 + "1234567890" * 4  # 60 alpha, 40 non-alpha = 60% ratio
        
        # Should pass with 50% threshold
        assert is_readable_text(text, min_chars=50, min_alpha_ratio=0.5) is True
        
        # Should fail with 70% threshold
        assert is_readable_text(text, min_chars=50, min_alpha_ratio=0.7) is False
        
        # Should fail if min_chars too high
        assert is_readable_text(text, min_chars=200, min_alpha_ratio=0.5) is False
