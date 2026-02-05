"""Configuration management for Comuni Extractor Platform."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class CrawlingConfig(BaseSettings):
    """Crawling configuration."""

    max_pages: int = Field(default=200, gt=0, description="Maximum pages to crawl")
    max_depth: int = Field(default=3, gt=0, description="Maximum crawl depth")
    concurrency: int = Field(default=5, gt=0, description="Concurrent requests")
    rate_limit: float = Field(default=1.0, gt=0, description="Seconds between requests")
    keywords: List[str] = Field(
        default_factory=lambda: [
            "bilancio",
            "trasparenza",
            "rendiconto",
            "preventivo",
        ],
        description="Keywords to prioritize",
    )
    respect_robots_txt: bool = Field(default=True)
    timeout: int = Field(default=10, gt=0, description="HTTP timeout (seconds)")
    allow_www_equivalence: bool = Field(
        default=True, description="Treat www/non-www as same site"
    )
    allow_subdomains: bool = Field(
        default=False, description="Allow crawling of site subdomains"
    )
    extract_pdf_from_raw_html: bool = Field(
        default=True, description="Extract PDFs via regex pattern matching"
    )


class PDFConfig(BaseSettings):
    """PDF processing configuration."""

    max_size_mb: int = Field(default=50, gt=0, description="Maximum PDF size")
    readability_threshold: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Minimum text ratio"
    )
    ocr_enabled: bool = Field(default=False)
    chunk_size: int = Field(default=1000, gt=0, description="Text chunk size")
    chunk_overlap: int = Field(default=200, ge=0, description="Chunk overlap")


class ChatGPTConfig(BaseSettings):
    """ChatGPT/OpenAI configuration."""

    model: str = Field(
        default="gpt-3.5-turbo", description="Model name (gpt-3.5-turbo or gpt-4)"
    )
    temperature: float = Field(
        default=0.3, ge=0.0, le=2.0, description="Temperature for sampling"
    )
    max_tokens: int = Field(default=2000, gt=0, description="Max tokens in response")
    retry_attempts: int = Field(default=3, gt=0, description="Number of retries")
    rate_limit_delay: float = Field(
        default=1.0, ge=0, description="Delay between API calls (seconds)"
    )
    timeout: int = Field(default=60, gt=0, description="API timeout (seconds)")

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        """Validate model name."""
        if not v or not v.strip():
            raise ValueError("model must be a non-empty string")
        return v


class RetrievalConfig(BaseSettings):
    """Retrieval/search configuration."""

    algorithm: str = Field(default="tfidf", description="Search algorithm")
    top_k: int = Field(default=5, gt=0, description="Top-k results to retrieve")
    ngram_range_min: int = Field(default=1, ge=1, description="Min n-gram size")
    ngram_range_max: int = Field(default=2, ge=1, description="Max n-gram size")
    max_features: int = Field(default=1000, gt=0, description="Max TF-IDF features")


class CachingConfig(BaseSettings):
    """Caching configuration."""

    enabled: bool = Field(default=True)
    ttl_http: int = Field(default=86400, ge=0, description="HTTP cache TTL (seconds)")
    ttl_pdf_text: int = Field(
        default=604800, ge=0, description="PDF text cache TTL (seconds)"
    )
    ttl_llm_responses: int = Field(
        default=604800, ge=0, description="LLM cache TTL (seconds)"
    )
    cache_types_http: bool = Field(default=True)
    cache_types_pdf: bool = Field(default=True)
    cache_types_text: bool = Field(default=True)
    cache_types_llm: bool = Field(default=True)


class PathsConfig(BaseSettings):
    """Paths configuration."""

    output_root: str = Field(default="./Comuni", description="Output root directory")
    drive_dataset_path: str = Field(
        default="./dataset_dati_comuni", description="Dataset path"
    )
    guide_path: Optional[str] = Field(
        default=None, description="Path to GUIDA.md (auto-discovered if None)"
    )


class ResilienceConfig(BaseSettings):
    """Resilience and error handling configuration."""

    circuit_breaker_enabled: bool = Field(default=True)
    circuit_breaker_failure_threshold: int = Field(default=5, gt=0)
    circuit_breaker_recovery_timeout: int = Field(default=60, gt=0)
    backoff_strategy: str = Field(default="exponential")
    backoff_base: int = Field(default=2, gt=1)
    backoff_max_delay: int = Field(default=300, gt=0)
    backoff_jitter: bool = Field(default=True)


class LoggingConfig(BaseSettings):
    """Logging configuration."""

    level: str = Field(default="INFO", description="Log level")
    format: str = Field(default="json", description="Log format (json or text)")


class AppConfig(BaseSettings):
    """Main application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Sub-configurations
    crawling: CrawlingConfig = Field(default_factory=CrawlingConfig)
    pdf: PDFConfig = Field(default_factory=PDFConfig)
    chatgpt: ChatGPTConfig = Field(default_factory=ChatGPTConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    caching: CachingConfig = Field(default_factory=CachingConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    resilience: ResilienceConfig = Field(default_factory=ResilienceConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    # API Keys and sensitive data
    openai_api_key: Optional[str] = Field(
        default=None, description="OpenAI API key"
    )

    @classmethod
    def from_yaml(cls, yaml_path: str | Path) -> "AppConfig":
        """Load configuration from YAML file."""
        yaml_path = Path(yaml_path)
        if not yaml_path.exists():
            raise FileNotFoundError(f"Config file not found: {yaml_path}")

        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        # Flatten nested config for Pydantic
        config_dict = {}

        # Process crawling config
        if "crawling" in data:
            config_dict["crawling"] = CrawlingConfig(**data["crawling"])

        # Process PDF config
        if "pdf" in data:
            config_dict["pdf"] = PDFConfig(**data["pdf"])

        # Process ChatGPT config
        if "chatgpt" in data:
            config_dict["chatgpt"] = ChatGPTConfig(**data["chatgpt"])

        # Process retrieval config
        if "retrieval" in data:
            retrieval_data = data["retrieval"].copy()
            # Handle tfidf sub-config
            if "tfidf" in retrieval_data:
                tfidf_data = retrieval_data.pop("tfidf")
                retrieval_data["ngram_range_min"] = tfidf_data.get("ngram_range", [1, 2])[0]
                retrieval_data["ngram_range_max"] = tfidf_data.get("ngram_range", [1, 2])[1]
                if "max_features" in tfidf_data:
                    retrieval_data["max_features"] = tfidf_data["max_features"]
            config_dict["retrieval"] = RetrievalConfig(**retrieval_data)

        # Process caching config
        if "caching" in data:
            cache_data = data["caching"].copy()
            cache_types = cache_data.pop("cache_types", {})
            cache_data["cache_types_http"] = cache_types.get("http", True)
            cache_data["cache_types_pdf"] = cache_types.get("pdf", True)
            cache_data["cache_types_text"] = cache_types.get("text", True)
            cache_data["cache_types_llm"] = cache_types.get("llm", True)
            config_dict["caching"] = CachingConfig(**cache_data)

        # Process paths config
        if "paths" in data:
            config_dict["paths"] = PathsConfig(**data["paths"])

        # Process resilience config
        if "resilience" in data:
            resilience_data = data["resilience"].copy()
            cb_data = resilience_data.pop("circuit_breaker", {})
            backoff_data = resilience_data.pop("backoff", {})

            resilience_data["circuit_breaker_enabled"] = cb_data.get("enabled", True)
            resilience_data["circuit_breaker_failure_threshold"] = cb_data.get(
                "failure_threshold", 5
            )
            resilience_data["circuit_breaker_recovery_timeout"] = cb_data.get(
                "recovery_timeout", 60
            )
            resilience_data["backoff_strategy"] = backoff_data.get("strategy", "exponential")
            resilience_data["backoff_base"] = backoff_data.get("base", 2)
            resilience_data["backoff_max_delay"] = backoff_data.get("max_delay", 300)
            resilience_data["backoff_jitter"] = backoff_data.get("jitter", True)

            config_dict["resilience"] = ResilienceConfig(**resilience_data)

        # Process logging config
        if "logging" in data:
            config_dict["logging"] = LoggingConfig(**data["logging"])

        # Return config instance
        return cls(**config_dict)

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "AppConfig":
        """Load configuration from file or environment."""
        if config_path:
            return cls.from_yaml(config_path)

        # Try to load from default locations
        for path in ["config.yaml", ".config.yaml"]:
            if Path(path).exists():
                return cls.from_yaml(path)

        # Fall back to environment variables
        return cls()

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return self.model_dump(mode="python")


def load_config(config_path: Optional[str] = None) -> AppConfig:
    """Load application configuration.
    
    Args:
        config_path: Optional path to YAML config file
        
    Returns:
        AppConfig instance
    """
    return AppConfig.load(config_path)
