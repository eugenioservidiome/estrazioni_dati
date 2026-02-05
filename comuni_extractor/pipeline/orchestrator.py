"""Pipeline orchestrator."""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from comuni_extractor.config import AppConfig
from comuni_extractor.crawl.discovery import URLDiscovery
from comuni_extractor.extraction.aggregator import ResultAggregator
from comuni_extractor.extraction.llm_client import LLMClient
from comuni_extractor.extraction.parser import ResponseParser
from comuni_extractor.extraction.prompt_builder import PromptBuilder
from comuni_extractor.http.client import HTTPClient
from comuni_extractor.io.checkpoint import CheckpointManager
from comuni_extractor.io.csv_handler import CSVHandler
from comuni_extractor.io.guide_parser import GuideParser
from comuni_extractor.io.report import ReportGenerator
from comuni_extractor.models import (
    CheckpointState,
    Document,
    ExtractionResult,
    FieldSpec,
    RunReport,
    RunStats,
)
from comuni_extractor.normalization.comune_name import normalize_comune_name
from comuni_extractor.retrieval.chunker import TextChunker
from comuni_extractor.retrieval.indexer import TFIDFIndexer


class PipelineOrchestrator:
    """Coordinate the complete extraction pipeline."""

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
            comune: Municipality (comune) name
            year: Year for extraction
            openai_key: OpenAI API key
        """
        self.config = config
        self.comune = normalize_comune_name(comune)
        self.year = year
        self.openai_key = openai_key or config.chatgpt.api_key

        # Initialize components
        self.http_client = HTTPClient(
            cache_dir=str(config.paths.cache_dir),
            rate_limit_delay=config.crawling.rate_limit,
        )

        self.discovery = URLDiscovery(
            self.http_client,
            max_pages=config.crawling.max_pages,
            max_depth=config.crawling.max_depth,
            respect_robots=config.crawling.respect_robots,
        )

        self.llm_client = LLMClient(
            api_key=self.openai_key,
            model=config.chatgpt.model,
            temperature=config.chatgpt.temperature,
            cache_dir=str(config.paths.cache_dir / "llm_responses"),
        )

        self.csv_handler = CSVHandler(config.paths.data_dir)
        self.checkpoint_manager = CheckpointManager(config.paths.cache_dir)
        self.report_generator = ReportGenerator(config.paths.output_dir)

        # Tracking
        self.stats = RunStats()
        self.results: List[ExtractionResult] = []

    def run(
        self,
        site_url: str,
        guide_path: Path,
        max_pdfs: Optional[int] = None,
        dry_run: bool = False,
    ) -> RunReport:
        """Run complete pipeline.
        
        Args:
            site_url: Municipality site URL
            guide_path: Path to GUIDA.md
            max_pdfs: Max PDFs to process
            dry_run: Don't write outputs
            
        Returns:
            Run report
        """
        try:
            # Load guide
            guide_parser = GuideParser()
            fields = guide_parser.parse(guide_path)

            # Phase 1: URL discovery
            self._log("Discovering PDF URLs...")
            pdf_urls = self.discovery.discover_pdfs(site_url)
            self.stats.pages_crawled = len(pdf_urls)

            if not pdf_urls:
                self._log("No PDF URLs found")
                return self._generate_report(fields, "No PDFs found")

            # Phase 2: Download PDFs
            self._log(f"Downloading {len(pdf_urls)} PDFs...")
            documents = self._download_pdfs(pdf_urls, max_pdfs)

            if not documents:
                self._log("No PDFs successfully downloaded")
                return self._generate_report(fields, "PDF download failed")

            # Phase 3: Extract and index text
            self._log("Extracting and indexing text...")
            chunker = TextChunker()
            chunks = self._chunk_documents(documents, chunker)

            indexer = TFIDFIndexer()
            indexer.build(chunks)

            # Phase 4: Extract fields
            self._log("Extracting fields...")
            self._extract_fields(fields, chunks, indexer)

            # Phase 5: Update CSVs
            if not dry_run:
                self._log("Updating CSVs...")
                self._update_csvs(fields)

            # Phase 6: Generate report
            self._log("Generating report...")
            report = self._generate_report(fields)

            return report

        except Exception as e:
            self._log(f"Pipeline error: {str(e)}", level="error")
            return self._generate_report([], f"Pipeline error: {str(e)}")

    def _download_pdfs(
        self,
        pdf_urls: List[str],
        max_pdfs: Optional[int] = None,
    ) -> List[Document]:
        """Download PDFs.
        
        Args:
            pdf_urls: List of PDF URLs
            max_pdfs: Max PDFs to download
            
        Returns:
            List of documents
        """
        documents = []
        urls = pdf_urls[: max_pdfs or len(pdf_urls)]

        for url in urls:
            try:
                pdf_content = self.http_client.get(url)
                # TODO: Create Document object and add to list
                self.stats.pdfs_downloaded += 1

            except Exception:
                self.stats.pdfs_failed += 1

        return documents

    def _chunk_documents(
        self,
        documents: List[Document],
        chunker: TextChunker,
    ) -> List:
        """Chunk documents.
        
        Args:
            documents: List of documents
            chunker: Text chunker
            
        Returns:
            List of chunks
        """
        chunks = []

        for doc in documents:
            try:
                doc_chunks = chunker.chunk(doc.text, doc.doc_id)
                chunks.extend(doc_chunks)

            except Exception:
                pass

        return chunks

    def _extract_fields(
        self,
        fields: List[FieldSpec],
        chunks: List,
        indexer: TFIDFIndexer,
    ) -> None:
        """Extract fields from chunks.
        
        Args:
            fields: Field specifications
            chunks: Text chunks
            indexer: TF-IDF indexer
        """
        for field in fields:
            try:
                # Retrieve relevant chunks
                relevant_chunks = indexer.search(field.field_name, top_k=5)

                # Extract using LLM
                results = self.llm_client.extract_fields(
                    chunks=[c for c, _ in relevant_chunks],
                    fields=[field],
                    document_hash="",
                )

                self.results.extend(results)
                self.stats.fields_processed += 1

            except Exception:
                pass

    def _update_csvs(self, fields: List[FieldSpec]) -> None:
        """Update CSV files with results.
        
        Args:
            fields: Field specifications
        """
        for field in fields:
            # Find result for this field
            field_results = [r for r in self.results if r.field_name == field.field_name]

            if field_results:
                result = field_results[0]

                try:
                    # Update CSV
                    self.csv_handler.update_csv_value(
                        csv_id=field.csv_id,
                        comune=self.comune,
                        year=self.year,
                        column=field.column,
                        value=result.value,
                    )
                    self.stats.fields_extracted += 1

                except Exception:
                    pass

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
            Run report
        """
        report = RunReport(
            comune=self.comune,
            year=self.year,
            start_time=datetime.now(),
            end_time=datetime.now(),
            stats=self.stats,
            field_results=self.results,
            error=error_message,
        )

        return report

    def _log(self, message: str, level: str = "info") -> None:
        """Log message.
        
        Args:
            message: Message to log
            level: Log level
        """
        if level == "error":
            logging.error(message)
        elif level == "warning":
            logging.warning(message)
        else:
            logging.info(message)
    
    def run_analyze(
        self,
        pdf_dir: Path,
        guide_path: Path,
        overwrite: bool = False,
    ) -> RunReport:
        """Run analysis on local PDFs.
        
        This method skips discovery/download and works with already ingested PDFs.
        
        Args:
            pdf_dir: Directory containing PDFs
            guide_path: Path to GUIDA.md
            overwrite: Overwrite existing CSV values
            
        Returns:
            Run report
        """
        from comuni_extractor.documents.pdf_extractor import (
            extract_text_from_pdf,
            is_readable_text,
            compute_pdf_hash,
        )
        
        try:
            # Load guide
            guide_parser = GuideParser()
            fields = guide_parser.parse(guide_path)
            
            self._log(f"Analyzing {len(list(pdf_dir.glob('*.pdf')))} PDFs...")
            
            # Phase 1: Extract text from local PDFs
            documents_data = []
            pdf_files = list(pdf_dir.glob("*.pdf"))
            
            for pdf_path in pdf_files:
                try:
                    # Extract text
                    text = extract_text_from_pdf(pdf_path)
                    
                    # Check readability gating
                    if not is_readable_text(text, min_chars=100, min_alpha_ratio=0.5):
                        self._log(f"Skipping unreadable PDF: {pdf_path.name}", level="warning")
                        self.stats.pdfs_failed += 1
                        continue
                    
                    # Compute hash
                    pdf_hash = compute_pdf_hash(pdf_path)
                    
                    documents_data.append({
                        'filename': pdf_path.name,
                        'text': text,
                        'hash': pdf_hash,
                        'path': str(pdf_path),
                    })
                    
                    self.stats.pdfs_downloaded += 1
                    
                except Exception as e:
                    self._log(f"Failed to process {pdf_path.name}: {str(e)}", level="warning")
                    self.stats.pdfs_failed += 1
            
            if not documents_data:
                self._log("No readable PDFs found")
                return self._generate_report(fields, "No readable PDFs")
            
            # Phase 2: Chunk and index
            self._log("Chunking and indexing text...")
            chunker = TextChunker()
            all_chunks = []
            
            for doc_data in documents_data:
                chunks = chunker.chunk(doc_data['text'], doc_data['filename'])
                all_chunks.extend(chunks)
            
            indexer = TFIDFIndexer()
            indexer.build(all_chunks)
            
            # Phase 3: Extract fields using LLM
            self._log("Extracting fields with LLM...")
            
            for field in fields:
                try:
                    # Retrieve relevant chunks
                    query = f"{field.field_name} {field.description}"
                    relevant_chunks = indexer.search(query, top_k=5)
                    
                    if not relevant_chunks:
                        continue
                    
                    # Extract using LLM
                    chunk_texts = [chunk.text for chunk, _ in relevant_chunks]
                    
                    # Get document hash for caching
                    doc_hash = documents_data[0]['hash'] if documents_data else ""
                    
                    results = self.llm_client.extract_fields(
                        chunks=chunk_texts,
                        fields=[field],
                        document_hash=doc_hash,
                    )
                    
                    self.results.extend(results)
                    self.stats.fields_processed += 1
                    
                except Exception as e:
                    self._log(f"Field extraction failed for {field.field_name}: {str(e)}", level="warning")
            
            # Phase 4: Aggregate results (definitivo > previsione)
            self._log("Aggregating results...")
            aggregator = ResultAggregator()
            
            for result in self.results:
                if result.candidates:
                    aggregated = aggregator.aggregate_result(result)
                    # Update result with aggregated value
                    result.value = aggregated.value
                    result.confidence = aggregated.confidence
            
            # Phase 5: Update CSVs
            self._log("Updating CSVs...")
            self._update_csvs_with_overwrite(fields, overwrite)
            
            # Phase 6: Generate report
            self._log("Generating report...")
            report = self._generate_report(fields)
            
            return report
            
        except Exception as e:
            self._log(f"Analysis error: {str(e)}", level="error")
            return self._generate_report([], f"Analysis error: {str(e)}")
    
    def _update_csvs_with_overwrite(self, fields: List[FieldSpec], overwrite: bool) -> None:
        """Update CSV files with results, respecting overwrite flag.
        
        Args:
            fields: Field specifications
            overwrite: Whether to overwrite existing values
        """
        for field in fields:
            # Find result for this field
            field_results = [r for r in self.results if r.field_name == field.field_name]
            
            if not field_results:
                continue
            
            result = field_results[0]
            
            if result.value is None:
                continue
            
            try:
                # Check if value already exists
                df = self.csv_handler.load_csv(field.csv_id)
                existing_row = self.csv_handler.find_or_create_row(df, self.comune, self.year)
                
                has_existing_value = False
                if existing_row is not None and field.column in df.columns:
                    existing_value = existing_row[field.column] if hasattr(existing_row, field.column) else None
                    has_existing_value = existing_value is not None and str(existing_value).strip() != ''
                
                # Only update if overwrite=True or no existing value
                if overwrite or not has_existing_value:
                    self.csv_handler.update_csv_value(
                        csv_id=field.csv_id,
                        comune=self.comune,
                        year=self.year,
                        column=field.column,
                        value=result.value,
                    )
                    self.stats.fields_extracted += 1
                else:
                    self._log(f"Skipping {field.field_name} (existing value, use --overwrite)", level="warning")
                
            except Exception as e:
                self._log(f"CSV update failed for {field.field_name}: {str(e)}", level="warning")
