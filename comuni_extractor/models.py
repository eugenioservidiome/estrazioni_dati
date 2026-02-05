"""Domain models for Comuni Extractor Platform."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class ValueType(str, Enum):
    """Type of extracted value."""

    DEFINITIVO = "definitivo"
    PREVISIONE = "previsione"
    CONSUNTIVO = "consuntivo"
    PREVENTIVO = "preventivo"


class FieldDataType(str, Enum):
    """Data types for field specifications."""

    TEXT = "text"
    CURRENCY = "currency"
    PERCENTAGE = "percentage"
    DATE = "date"
    INTEGER = "integer"
    FLOAT = "float"
    PHONE = "phone"
    EMAIL = "email"
    PEC = "pec"
    IBAN = "iban"
    COUNTRY_CODE = "country_code"
    URL = "url"


class FieldSpec(BaseModel):
    """Specification of a field to extract from documents."""

    name: str = Field(..., description="Field name (e.g., 'entrate_totali')")
    csv_id: int = Field(..., description="CSV file ID (1-6)")
    column: str = Field(..., description="Target column name in CSV")
    description: str = Field(default="", description="Field description")
    data_type: FieldDataType = Field(default=FieldDataType.TEXT)
    regex_pattern: Optional[str] = Field(
        default=None, description="Regex pattern for value extraction"
    )
    query_templates: List[str] = Field(
        default_factory=list,
        description="Query templates (support {year} placeholder)",
    )
    validators: List[str] = Field(
        default_factory=list,
        description="Validator types (e.g., 'currency', 'phone')",
    )
    priority_definitivo: List[str] = Field(
        default_factory=list,
        description="Keywords for definitivo values",
    )
    priority_previsione: List[str] = Field(
        default_factory=list,
        description="Keywords for previsione values",
    )
    required: bool = Field(default=False, description="Is field required")
    min_confidence: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Minimum confidence threshold"
    )

    @field_validator("csv_id")
    @classmethod
    def validate_csv_id(cls, v: int) -> int:
        """Validate CSV ID is between 1 and 6."""
        if not 1 <= v <= 6:
            raise ValueError(f"csv_id must be between 1 and 6, got {v}")
        return v


class Document(BaseModel):
    """Represents a downloaded document (PDF or HTML)."""

    doc_id: str = Field(..., description="Unique document identifier")
    filename: str = Field(..., description="Original filename")
    source_url: str = Field(..., description="Source URL")
    doc_type: str = Field(..., description="Document type (pdf, html)")
    file_path: str = Field(..., description="Local file path")
    file_hash: str = Field(..., description="SHA256 hash of file content")
    file_size: int = Field(..., description="File size in bytes")
    downloaded_at: datetime = Field(default_factory=datetime.utcnow)
    extracted_text: Optional[str] = Field(
        default=None, description="Extracted text content"
    )
    text_length: int = Field(default=0, description="Length of extracted text")
    readability_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Readability score (alpha ratio)"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class Chunk(BaseModel):
    """Represents a chunk of text from a document."""

    chunk_id: str = Field(..., description="Unique chunk identifier")
    doc_id: str = Field(..., description="Source document ID")
    text: str = Field(..., description="Chunk text content")
    start_pos: int = Field(..., description="Start position in document")
    end_pos: int = Field(..., description="End position in document")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExtractionCandidate(BaseModel):
    """A candidate value extracted from documents."""

    value: str = Field(..., description="Extracted value")
    value_type: ValueType = Field(..., description="Type of value")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    source_pdf: str = Field(..., description="Source PDF filename")
    source_url: Optional[str] = Field(
        default=None, description="Source URL where PDF was found"
    )
    evidence: str = Field(..., description="Text snippet supporting this value")
    model: str = Field(default="gpt-3.5-turbo", description="LLM model used")
    raw_response: Optional[Dict[str, Any]] = Field(
        default=None, description="Raw LLM response"
    )


class ExtractionResult(BaseModel):
    """Result of extracting a field from documents."""

    field_name: str = Field(..., description="Field name")
    csv_id: int = Field(..., description="Target CSV ID")
    column: str = Field(..., description="Target column")
    data_type: FieldDataType = Field(..., description="Field data type")
    value: Optional[str] = Field(
        default=None, description="Final extracted value"
    )
    value_type: Optional[ValueType] = Field(
        default=None, description="Type of final value"
    )
    confidence: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Confidence in final value"
    )
    source_pdf: Optional[str] = Field(
        default=None, description="Source PDF filename"
    )
    source_url: Optional[str] = Field(
        default=None, description="Source URL"
    )
    evidence_snippet: Optional[str] = Field(
        default=None, description="Supporting text snippet"
    )
    candidates: List[ExtractionCandidate] = Field(
        default_factory=list, description="All candidate values"
    )
    validation_passed: bool = Field(
        default=False, description="Validation result"
    )
    validation_errors: List[str] = Field(
        default_factory=list, description="Validation errors"
    )
    extraction_errors: List[str] = Field(
        default_factory=list, description="Extraction errors"
    )


class FieldValue(BaseModel):
    """Final field value for CSV output."""

    field_name: str
    csv_id: int
    column: str
    value: Optional[str] = None
    data_type: FieldDataType
    confidence: Optional[float] = None
    source: Optional[str] = None


class CrawlStats(BaseModel):
    """Statistics from crawling phase."""

    pages_visited: int = Field(default=0)
    pages_skipped: int = Field(default=0)
    urls_discovered: int = Field(default=0)
    urls_deduped: int = Field(default=0)
    pdfs_found: int = Field(default=0)
    errors: int = Field(default=0)


class DownloadStats(BaseModel):
    """Statistics from download phase."""

    pdfs_attempted: int = Field(default=0)
    pdfs_successful: int = Field(default=0)
    pdfs_failed: int = Field(default=0)
    pdfs_skipped: int = Field(default=0)
    bytes_downloaded: int = Field(default=0)


class ExtractionStats(BaseModel):
    """Statistics from extraction phase."""

    fields_processed: int = Field(default=0)
    fields_extracted: int = Field(default=0)
    fields_failed: int = Field(default=0)
    llm_api_calls: int = Field(default=0)
    llm_errors: int = Field(default=0)


class RunStats(BaseModel):
    """Statistics for an entire run."""

    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = Field(default=None)
    crawl_stats: CrawlStats = Field(default_factory=CrawlStats)
    download_stats: DownloadStats = Field(default_factory=DownloadStats)
    extraction_stats: ExtractionStats = Field(default_factory=ExtractionStats)

    @property
    def duration_seconds(self) -> float:
        """Get duration of run in seconds."""
        end = self.end_time or datetime.utcnow()
        return (end - self.start_time).total_seconds()


class ProcessingError(BaseModel):
    """An error that occurred during processing."""

    error_type: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    context: Dict[str, Any] = Field(default_factory=dict, description="Error context")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    recoverable: bool = Field(default=True)


class RunReport(BaseModel):
    """Comprehensive report of a pipeline run."""

    # Metadata
    comune_name: str = Field(..., description="Municipality name")
    comune_name_normalized: str = Field(..., description="Normalized municipality name")
    site_url: str = Field(..., description="Municipality website URL")
    year: int = Field(..., description="Reference year")
    run_timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str = Field(default="0.1.0")
    
    # Configuration used
    config: Dict[str, Any] = Field(default_factory=dict)

    # Statistics
    stats: RunStats = Field(default_factory=RunStats)

    # Results
    fields: List[ExtractionResult] = Field(
        default_factory=list, description="Extracted field results"
    )

    # Errors and warnings
    errors: List[ProcessingError] = Field(
        default_factory=list, description="Errors encountered"
    )
    warnings: List[str] = Field(default_factory=list, description="Warnings")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "comune_name": "roma",
                "site_url": "https://www.comune.roma.it",
                "year": 2023,
                "fields": [],
                "errors": [],
            }
        }


@dataclass
class CheckpointState:
    """State for resuming processing after interruption."""

    comune_name: str
    year: int
    urls_discovered: List[str] = field(default_factory=list)
    pdfs_downloaded: List[Dict[str, str]] = field(default_factory=list)
    pdfs_processed: List[str] = field(default_factory=list)
    fields_extracted: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "comune_name": self.comune_name,
            "year": self.year,
            "urls_discovered": self.urls_discovered,
            "pdfs_downloaded": self.pdfs_downloaded,
            "pdfs_processed": self.pdfs_processed,
            "fields_extracted": self.fields_extracted,
            "timestamp": self.timestamp.isoformat(),
        }
