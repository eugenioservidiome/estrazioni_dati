"""Pipeline orchestrator."""

import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from comuni_extractor.config import AppConfig
from comuni_extractor.documents.pdf_extractor import (
    compute_pdf_hash,
    extract_text_from_pdf,
    is_readable_text,
)
from comuni_extractor.extraction.aggregator import ResultAggregator
from comuni_extractor.extraction.llm_client import LLMClient
from comuni_extractor.io.csv_handler import CSVHandler
from comuni_extractor.io.guide_parser import GuideParser
from comuni_extractor.io.report import ReportGenerator
from comuni_extractor.models import (
    ExtractionResult,
    ExtractionStats,
    FieldSpec,
    ProcessingError,
    RunReport,
    RunStats,
)
from comuni_extractor.normalization.comune_name import normalize_comune_name
from comuni_extractor.normalization.normalizers import FieldNormalizer
from comuni_extractor.normalization.validators import FieldValidator
from comuni_extractor.paths import ComunePaths
from comuni_extractor.retrieval.chunker import TextChunker
from comuni_extractor.retrieval.indexer import TFIDFIndexer


class PipelineOrchestrator:
    """Coordinate the extraction pipeline."""

    def __init__(
        self,
        config: AppConfig,
        comune: str,
        year: int,
        openai_key: Optional[str] = None,
    ):
        """Initialize orchestrator.
        
        Args:
            config: Application configuration
            comune: Municipality name
            year: Reference year
            openai_key: OpenAI API key (overrides config)
        """
        self.config = config
        self.comune = normalize_comune_name(comune)
        self.year = year
        self.openai_key = openai_key or config.openai_api_key

        # Setup paths
        self.paths = ComunePaths.from_root(
            output_root=config.paths.output_root,
            comune=self.comune,
            year=year,
        )
        self.paths.ensure_directories()

        # Initialize components
        self.llm_client = LLMClient(
            api_key=self.openai_key,
            model=config.chatgpt.model,
            temperature=config.chatgpt.temperature,
            cache_dir=self.paths.cache_dir / "llm",
        )

        self.csv_handler = CSVHandler(
            source_dataset_path=config.paths.drive_dataset_path,
            output_dir=self.paths.output_dir,
        )

        self.report_generator = ReportGenerator(self.paths.output_dir)

        # Stats tracking
        self.stats = RunStats()
        self.errors: List[ProcessingError] = []
        self.warnings: List[str] = []
        self.results: List[ExtractionResult] = []

    def run_analyze(
        self,
        pdf_dir: Path,
        guide_path: Path,
        overwrite: bool = False,
    ) -> RunReport:
        """Run analysis on local PDFs.
        
        Args:
            pdf_dir: Directory containing PDFs
            guide_path: Path to guide file (GUIDA.md or CSV)
            overwrite: Overwrite existing CSV values
            
        Returns:
            RunReport with results
        """
        self.stats.start_time = datetime.utcnow()
        
        try:
            # Phase 1: Parse guide
            self._log("Parsing field specifications from guide...")
            guide_parser = GuideParser(guide_path)
            fields = guide_parser.parse()
            self._log(f"Loaded {len(fields)} field specifications")

            # Phase 2: Extract and filter text from PDFs
            self._log("Extracting text from PDFs...")
            documents_data = self._extract_pdf_texts(pdf_dir)
            
            if not documents_data:
                self._log("No readable PDFs found", level="warning")
                return self._generate_report(fields, "No readable PDFs")

            # Phase 3: Chunk and index
            self._log("Chunking and indexing text...")
            all_chunks = self._chunk_documents(documents_data)
            
            indexer = TFIDFIndexer(
                ngram_range=(
                    self.config.retrieval.ngram_range_min,
                    self.config.retrieval.ngram_range_max,
                ),
                max_features=self.config.retrieval.max_features,
            )
            indexer.build(all_chunks)
            self._log(f"Indexed {len(all_chunks)} text chunks")

            # Phase 4: Extract fields with LLM
            self._log("Extracting fields with LLM...")
            self._extract_fields(fields, indexer)

            # Phase 5: Normalize and validate
            self._log("Normalizing and validating values...")
            self._normalize_and_validate_results()

            # Phase 6: Aggregate candidates
            self._log("Aggregating extraction candidates...")
            self._aggregate_results()

            # Phase 7: Update CSVs
            self._log("Updating CSV files...")
            self._update_csvs(fields, overwrite)

            # Phase 8: Generate report
            self._log("Generating report...")
            self.stats.end_time = datetime.utcnow()
            report = self._generate_report(fields)
            
            report_path = self.report_generator.save_report(report)
            self._log(f"Report saved: {report_path}")

            return report

        except Exception as e:
            self._log(f"Pipeline error: {str(e)}", level="error")
            self.stats.end_time = datetime.utcnow()
            self._add_error("pipeline_error", str(e), {"phase": "unknown"})
            return self._generate_report([], f"Pipeline error: {str(e)}")

    def _extract_pdf_texts(self, pdf_dir: Path) -> List[dict]:
        """Extract text from PDFs with readability gating.
        
        Args:
            pdf_dir: Directory containing PDFs
            
        Returns:
            List of dicts with filename, text, hash
        """
        documents_data = []
        pdf_files = list(pdf_dir.glob("*.pdf"))
        
        for pdf_path in pdf_files:
            try:
                # Extract text
                text = extract_text_from_pdf(pdf_path)
                
                # Readability gating
                if not is_readable_text(text, min_chars=100, min_alpha_ratio=0.5):
                    self._add_warning(f"Skipping unreadable PDF: {pdf_path.name}")
                    self.stats.download_stats.pdfs_failed += 1
                    continue
                
                # Compute hash
                pdf_hash = compute_pdf_hash(pdf_path)
                
                documents_data.append({
                    "filename": pdf_path.name,
                    "text": text,
                    "hash": pdf_hash,
                    "path": str(pdf_path),
                })
                
                self.stats.download_stats.pdfs_successful += 1
                
            except Exception as e:
                self._add_error(
                    "pdf_extraction_error",
                    f"Failed to process {pdf_path.name}: {str(e)}",
                    {"pdf": pdf_path.name},
                )
                self.stats.download_stats.pdfs_failed += 1
        
        return documents_data

    def _chunk_documents(self, documents_data: List[dict]) -> List:
        """Chunk documents into text segments.
        
        Args:
            documents_data: List of document dicts
            
        Returns:
            List of TextChunk objects
        """
        chunker = TextChunker(
            chunk_size=self.config.pdf.chunk_size,
            overlap=self.config.pdf.chunk_overlap,
        )
        
        all_chunks = []
        for doc_data in documents_data:
            try:
                chunks = chunker.chunk(doc_data["text"], doc_data["filename"])
                all_chunks.extend(chunks)
            except Exception as e:
                self._add_warning(f"Chunking failed for {doc_data['filename']}: {str(e)}")
        
        return all_chunks

    def _extract_fields(
        self,
        fields: List[FieldSpec],
        indexer: TFIDFIndexer,
    ) -> None:
        """Extract fields using LLM.
        
        Args:
            fields: Field specifications
            indexer: Built TF-IDF indexer
        """
        for field in fields:
            try:
                # Build query from field name, description, and templates
                query_parts = [field.name, field.description]
                if field.query_templates:
                    # Substitute {year} placeholder
                    templates = [t.replace("{year}", str(self.year)) for t in field.query_templates]
                    query_parts.extend(templates)
                query = " ".join(query_parts)
                
                # Retrieve relevant chunks
                top_k = self.config.retrieval.top_k
                relevant_chunks_scored = indexer.search(query, top_k=top_k)
                
                if not relevant_chunks_scored:
                    self._add_warning(f"No relevant chunks found for field: {field.name}")
                    self.stats.extraction_stats.fields_failed += 1
                    continue
                
                # Extract chunks only (drop scores)
                relevant_chunks = [chunk for chunk, score in relevant_chunks_scored]
                
                # Call LLM
                result = self.llm_client.extract_field_candidates(
                    field=field,
                    chunks=relevant_chunks,
                    year=self.year,
                )
                
                self.results.append(result)
                self.stats.extraction_stats.fields_processed += 1
                self.stats.extraction_stats.llm_api_calls += 1
                
                if result.candidates:
                    self._log(f"Extracted {len(result.candidates)} candidates for {field.name}")
                
            except Exception as e:
                self._add_error(
                    "field_extraction_error",
                    f"Failed to extract field {field.name}: {str(e)}",
                    {"field": field.name},
                )
                self.stats.extraction_stats.fields_failed += 1
                self.stats.extraction_stats.llm_errors += 1

    def _normalize_and_validate_results(self) -> None:
        """Normalize and validate extraction results."""
        normalizer = FieldNormalizer()
        validator = FieldValidator()
        
        for result in self.results:
            for candidate in result.candidates:
                try:
                    # Normalize value based on data type
                    normalized = normalizer.normalize(
                        candidate.value,
                        result.data_type,
                    )
                    candidate.value = normalized
                    
                    # Validate (this might lower confidence or mark as invalid)
                    is_valid = validator.validate(
                        candidate.value,
                        result.data_type,
                    )
                    
                    if not is_valid:
                        # Lower confidence for invalid values
                        candidate.confidence *= 0.5
                        self._add_warning(
                            f"Validation failed for {result.field_name} = {candidate.value}"
                        )
                    
                except Exception as e:
                    self._add_warning(
                        f"Normalization/validation error for {result.field_name}: {str(e)}"
                    )

    def _aggregate_results(self) -> None:
        """Aggregate candidates in extraction results."""
        aggregator = ResultAggregator()
        
        for result in self.results:
            if result.candidates:
                aggregator.aggregate_result(result)
                
                if result.value:
                    self.stats.extraction_stats.fields_extracted += 1

    def _update_csvs(
        self,
        fields: List[FieldSpec],
        overwrite: bool,
    ) -> None:
        """Update CSV files with extraction results.
        
        Args:
            fields: Field specifications
            overwrite: Whether to overwrite existing values
        """
        for field in fields:
            # Find result for this field
            field_results = [r for r in self.results if r.field_name == field.name]
            
            if not field_results or not field_results[0].value:
                continue
            
            result = field_results[0]
            
            try:
                updated = self.csv_handler.update_csv_value(
                    csv_id=field.csv_id,
                    comune=self.comune,
                    year=self.year,
                    column=field.column,
                    value=result.value,
                    overwrite=overwrite,
                )
                
                if not updated:
                    self._add_warning(
                        f"Skipped {field.name}: existing value (use --overwrite to replace)"
                    )
                
            except Exception as e:
                self._add_error(
                    "csv_update_error",
                    f"Failed to update CSV for {field.name}: {str(e)}",
                    {"field": field.name, "csv_id": field.csv_id},
                )

    def _generate_report(
        self,
        fields: List[FieldSpec],
        error_message: Optional[str] = None,
    ) -> RunReport:
        """Generate run report.
        
        Args:
            fields: Field specifications
            error_message: Optional error message
            
        Returns:
            RunReport
        """
        # Add final error if provided
        if error_message:
            self._add_error("pipeline_failure", error_message, {})
        
        report = RunReport(
            comune_name=self.comune,
            comune_name_normalized=self.comune,
            site_url=f"https://www.comune.{self.comune}.it",  # Placeholder
            year=self.year,
            run_timestamp=self.stats.start_time,
            version="0.1.0",
            config={},
            stats=self.stats,
            fields=self.results,
            errors=self.errors,
            warnings=self.warnings,
        )
        
        return report

    def _log(self, message: str, level: str = "info") -> None:
        """Log message.
        
        Args:
            message: Message to log
            level: Log level
        """
        if level == "error":
            logging.error(f"[{self.comune}/{self.year}] {message}")
        elif level == "warning":
            logging.warning(f"[{self.comune}/{self.year}] {message}")
        else:
            logging.info(f"[{self.comune}/{self.year}] {message}")

    def _add_error(self, error_type: str, message: str, context: dict) -> None:
        """Add error to tracking.
        
        Args:
            error_type: Type of error
            message: Error message
            context: Additional context
        """
        error = ProcessingError(
            error_type=error_type,
            message=message,
            context=context,
            recoverable=True,
        )
        self.errors.append(error)
        self._log(f"ERROR [{error_type}]: {message}", level="error")

    def _add_warning(self, message: str) -> None:
        """Add warning to tracking.
        
        Args:
            message: Warning message
        """
        self.warnings.append(message)
        self._log(message, level="warning")
