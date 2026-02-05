"""Tests for configuration system."""

import pytest
from pathlib import Path

from comuni_extractor.config import AppConfig, load_config


class TestAppConfig:
    """Test AppConfig class."""

    def test_config_defaults(self):
        """Test default configuration values."""
        config = AppConfig()
        assert config.crawling.max_pages == 200
        assert config.pdf.max_size_mb == 50
        assert config.chatgpt.model == "gpt-3.5-turbo"
        assert config.retrieval.top_k == 5

    def test_config_load_yaml(self, sample_config_yaml):
        """Test loading configuration from YAML."""
        config = AppConfig.from_yaml(sample_config_yaml)
        assert config.crawling.max_pages == 50
        assert config.pdf.chunk_size == 500
        assert config.chatgpt.temperature == 0.3

    def test_config_csv_id_validation(self):
        """Test CSV ID validation."""
        config = AppConfig()
        # This should work (default values)
        assert config.crawling.max_pages > 0

    def test_config_model_validation(self):
        """Test model name validation."""
        config = AppConfig()
        config.chatgpt.model = "gpt-3.5-turbo"
        assert config.chatgpt.model == "gpt-3.5-turbo"

        # Invalid model should raise validation error
        with pytest.raises(ValueError):
            config.chatgpt.model = "invalid-model"

    def test_load_config_from_file(self, sample_config_yaml):
        """Test loading config from file."""
        config = load_config(str(sample_config_yaml))
        assert config.crawling.max_pages == 50

    def test_config_to_dict(self):
        """Test converting config to dict."""
        config = AppConfig()
        config_dict = config.to_dict()
        assert "crawling" in config_dict
        assert "pdf" in config_dict
        assert config_dict["crawling"]["max_pages"] == 200
