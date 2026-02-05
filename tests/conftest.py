"""Pytest configuration and shared fixtures."""

import json
import tempfile
from pathlib import Path
import pytest
from io import BytesIO

# Since we can't easily create PDFs in conftest, we'll create minimal test data


@pytest.fixture
def temp_dir():
    """Create temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_guide(temp_dir):
    """Create sample GUIDA.md for testing."""
    guide_content = """# Guida Mapping Campi CSV

## Campo: entrate_totali
- **CSV**: 1
- **Colonna**: entrate_anno
- **Descrizione**: Entrate totali del comune per l'anno
- **Tipo**: currency
- **Regex**: `€?\\s*([\\d.,]+)\\s*€?`
- **Query Templates**:
  - "entrate totali anno {year}"
  - "totale entrate {year}"
- **Priorità Definitivo**: rendiconto, consuntivo, definitivo
- **Priorità Previsione**: previsione, preventivo

## Campo: spese_correnti
- **CSV**: 1
- **Colonna**: spese_correnti_anno
- **Descrizione**: Spese correnti (gestione)
- **Tipo**: currency
- **Regex**: `€?\\s*([\\d.,]+)\\s*€?`
- **Query Templates**:
  - "spese correnti anno {year}"
  - "spese di gestione {year}"

## Campo: sindaco_nome
- **CSV**: 1
- **Colonna**: sindaco
- **Descrizione**: Nome sindaco in carica
- **Tipo**: text
- **Query Templates**:
  - "sindaco {year}"
  - "nome sindaco"
"""
    guide_path = temp_dir / "GUIDA.md"
    guide_path.write_text(guide_content, encoding="utf-8")
    return guide_path


@pytest.fixture
def sample_csv_dir(temp_dir):
    """Create sample CSV directory."""
    csv_dir = temp_dir / "csv"
    csv_dir.mkdir()

    # 01_governo.csv
    gov_csv = csv_dir / "01_governo.csv"
    gov_csv.write_text(
        "comune,istat,anno,entrate_anno,spese_correnti_anno,sindaco\n"
        "TestVille,001001,2023,,,\n",
        encoding="utf-8",
    )

    # 02_territorio_popolazione.csv
    terr_csv = csv_dir / "02_territorio_popolazione.csv"
    terr_csv.write_text(
        "comune,istat,anno,popolazione\n"
        "TestVille,001001,2023,\n",
        encoding="utf-8",
    )

    # Create empty CSVs for 03-06
    for i in range(3, 7):
        filename = csv_dir / f"{i:02d}_data.csv"
        filename.write_text("comune,istat,anno\nTestVille,001001,2023\n", encoding="utf-8")

    return csv_dir


@pytest.fixture
def sample_config_yaml(temp_dir):
    """Create sample configuration YAML."""
    config_content = """crawling:
  max_pages: 50
  max_depth: 2
  concurrency: 3
  rate_limit: 1.0
  keywords:
    - bilancio
    - trasparenza

pdf:
  max_size_mb: 50
  readability_threshold: 0.7
  chunk_size: 500
  chunk_overlap: 100

chatgpt:
  model: gpt-3.5-turbo
  temperature: 0.3
  max_tokens: 1000

retrieval:
  top_k: 3
  tfidf:
    ngram_range: [1, 2]
    max_features: 500

caching:
  enabled: true
  ttl_http: 3600

paths:
  output_root: ./test_output
  drive_dataset_path: ./test_data
"""
    config_path = temp_dir / "config.yaml"
    config_path.write_text(config_content, encoding="utf-8")
    return config_path


@pytest.fixture
def sample_html():
    """Create sample HTML content."""
    return """<!DOCTYPE html>
<html>
<head>
    <title>Comune di TestVille</title>
</head>
<body>
    <h1>Comune di TestVille</h1>
    <p>Benvenuti nel sito ufficiale del Comune di TestVille</p>
    <a href="/bilancio">Bilancio</a>
    <a href="https://servizipubblicaamministrazione.it/tdata/bilancio_2023.pdf">Bilancio 2023</a>
</body>
</html>
"""


@pytest.fixture
def mock_openai_response():
    """Create mock OpenAI API response."""
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "value": "1500000.00",
                        "type": "definitivo",
                        "confidence": 0.95,
                    })
                }
            }
        ]
    }


@pytest.mark.usefixtures("temp_dir")
class TestBase:
    """Base test class with fixtures."""
    pass
