# Comuni Extractor Platform

Extract structured data from Italian municipality websites using web crawling and LLM-powered extraction.

## Google Colab Notebook (Marker-based, No API costs)

For a **zero-cost, one-click solution** using Google Colab and Marker PDF conversion (no OpenAI API required), see:

📓 **[notebooks/vigone_marker_extractor.ipynb](notebooks/vigone_marker_extractor.ipynb)**

This notebook provides automated extraction for **Vigone municipality** with:
- ✅ Web crawling to discover PDFs
- ✅ Marker library for PDF→Markdown conversion (no OCR costs)
- ✅ Zero-LLM extraction using regex and heuristics
- ✅ Google Drive integration for templates and output
- ✅ Caching and resume capability
- ✅ Quick test mode (30 pages, 20 PDFs)

**Usage:**
1. Open the notebook in Google Colab
2. Mount your Google Drive (OAuth)
3. Ensure `dataset_dati_comuni` folder exists with 6 CSV templates
4. Set `ANNO_TARGET` (e.g., 2024)
5. Run all cells or use the quick test

**Output:** Populated CSV files in `Comuni/Vigone/<ANNO_TARGET>/output/`

---

## Quick Start

```bash
git clone <repo-url>
cd comuni-extractor
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env && cp config.example.yaml config.yaml
```

## Workflow Overview

The platform supports a **3-phase collaborative workflow** designed to work with browser extensions for PDF downloads:

### Phase 1: Discovery (Generate Download Kit)

Crawl the municipality website to discover PDF links and generate a download kit for colleagues:

```bash
comuni-extractor discover \
  --site-url "https://www.comune.roma.it" \
  --year 2023 \
  --drive-path "/path/to/dataset_dati_comuni"
```

**Output:**
- `manifest.jsonl`: JSONL file tracking all discovered PDFs with metadata (URL, source page, anchor text, status)
- `links_roma_2023.html`: Styled HTML page with clickable download links for browser extension
- `links_roma_2023.csv`: CSV export of all PDF URLs with suggested filenames

**Next step:** Share the HTML file with colleagues who will use a browser extension to download PDFs.

### Phase 2: Manual Download

Colleagues open the generated HTML file and use a browser extension (e.g., DownThemAll, uBlock Origin) to batch download PDFs to a local folder (e.g., `~/Downloads/roma_pdfs/`).

> **Why manual download?** Some municipality websites (e.g., servizipubblicaamministrazione.it) block automated downloads but allow browser-based access.

### Phase 3: Ingest Downloaded PDFs

Import the manually downloaded PDFs into the project structure:

```bash
comuni-extractor ingest \
  --comune roma \
  --year 2023 \
  --downloads-dir ~/Downloads/roma_pdfs \
  --move  # Optional: move instead of copy
```

**What happens:**
- PDFs are matched to manifest entries using exact filename, similarity matching, or interactive prompts
- SHA256 hashes computed for duplicate detection
- Files copied/moved to `Comuni/roma/2023/pdf/` directory
- Manifest updated with status: `downloaded`, `unmatched`, or `skipped_duplicate`

### Phase 4: Analyze and Extract Data

Process the local PDFs and extract structured data using LLMs:

```bash
export OPENAI_API_KEY="sk-proj-..."  # Required

comuni-extractor analyze \
  --comune roma \
  --year 2023 \
  --drive-path "/path/to/dataset_dati_comuni" \
  --overwrite  # Optional: overwrite existing CSV values
```

**What happens:**
1. Extract text from PDFs with readability gating (skip scanned/unreadable PDFs)
2. Chunk text and build TF-IDF index for retrieval
3. Call OpenAI API to extract fields using relevant chunks
4. Aggregate results (prioritize `definitivo` over `previsione`)
5. Update CSVs with extracted values (respects `--overwrite` flag)
6. Generate JSON report with confidence scores and metadata

**Output:**
- `bilancio_previsione_2023.csv`: Updated with extracted fields
- `bilancio_definitivo_2023.csv`: Updated with extracted fields  
- `report_roma_2023.json`: Comprehensive extraction report

## Alternative: Legacy Single-Command Workflow

For websites that allow automated downloads, use the single `run` command:

```bash
comuni-extractor run \
  --site-url "https://www.comune.roma.it" \
  --year 2023 \
  --drive-path "/path/to/dataset_dati_comuni"
```

This executes all phases automatically (discovery, download, analysis) in one pass. **Note:** This will fail for sites that block automated downloads.

## Other Commands

```bash
comuni-extractor validate-config config.yaml  # Validate YAML config
comuni-extractor test-openai                   # Test OpenAI API connection
comuni-extractor cache --clear                 # Clear all caches
comuni-extractor report --comune roma --year 2023  # View existing report
comuni-extractor --help                        # Show all commands
```

## Output Structure

```
Comuni/<nome_comune>/<anno>/
├── pdf/                      # Downloaded PDFs
├── output/                   # Enriched CSVs + JSON report
│   ├── bilancio_previsione_<anno>.csv
│   ├── bilancio_definitivo_<anno>.csv
│   └── report_<comune>_<anno>.json
├── cache/                    # HTTP, PDF, and LLM response caches
├── logs/                     # Run logs
├── manifest.jsonl            # PDF tracking manifest (JSONL format)
├── links_<comune>_<anno>.html  # Download kit HTML (from discover phase)
└── links_<comune>_<anno>.csv   # Download kit CSV (from discover phase)
```

## Manifest Status Codes

The `manifest.jsonl` file tracks each discovered PDF with one of these statuses:

- **`to_download`**: PDF discovered but not yet downloaded
- **`downloaded`**: PDF successfully ingested with SHA256 hash
- **`unmatched`**: PDF found in downloads directory but no matching manifest entry
- **`skipped_duplicate`**: PDF skipped due to duplicate SHA256 hash
- **`failed`**: Download or processing error (see `error_reason` field)

Query manifest status:

```bash
# Count PDFs by status
cat Comuni/roma/2023/manifest.jsonl | jq -r '.status' | sort | uniq -c

# List all to_download URLs
cat Comuni/roma/2023/manifest.jsonl | jq -r 'select(.status=="to_download") | .pdf_url'
```

## Environment Variables

The following environment variables are supported:

```bash
# Required for LLM extraction (analyze phase)
export OPENAI_API_KEY="sk-proj-..."

# Optional configuration overrides
export COMUNI_EXTRACTOR_CONFIG="/path/to/custom_config.yaml"
export COMUNI_EXTRACTOR_LOG_LEVEL="DEBUG"  # Default: INFO
export COMUNI_EXTRACTOR_CACHE_DIR="/custom/cache/path"
```

Alternatively, create a `.env` file in the project root:

```bash
OPENAI_API_KEY=sk-proj-...
COMUNI_EXTRACTOR_LOG_LEVEL=DEBUG
```

## Complete End-to-End Example

Full workflow for extracting data from Comune di Milano (2023):

```bash
# 0. Setup (one-time)
export OPENAI_API_KEY="sk-proj-..."
export DRIVE_PATH="/data/dataset_dati_comuni"

# 1. Discovery phase
comuni-extractor discover \
  --site-url "https://www.comune.milano.it/bilanci" \
  --year 2023 \
  --drive-path "$DRIVE_PATH" \
  --max-pages 100

# Output:
# ✓ Crawled 47 pages
# ✓ Discovered 23 PDFs
# ✓ Generated: Comuni/milano/2023/links_milano_2023.html
# ✓ Generated: Comuni/milano/2023/links_milano_2023.csv
# ✓ Manifest: Comuni/milano/2023/manifest.jsonl
#
# Next: Open links_milano_2023.html in browser and download PDFs to ~/Downloads/milano_pdfs/

# 2. Manual download (browser extension)
# - Open file:///data/dataset_dati_comuni/Comuni/milano/2023/links_milano_2023.html
# - Use browser extension to batch download PDFs
# - Save to ~/Downloads/milano_pdfs/

# 3. Ingest phase
comuni-extractor ingest \
  --comune milano \
  --year 2023 \
  --downloads-dir ~/Downloads/milano_pdfs \
  --move \
  --interactive-match  # Optional: prompts for ambiguous matches

# Output:
# ✓ Matched: 21 PDFs
# ✓ Unmatched: 2 PDFs (orphaned files)
# ✓ Skipped: 0 duplicates
# ✓ PDFs moved to: Comuni/milano/2023/pdf/
# ✓ Manifest updated with SHA256 hashes

# 4. Analyze phase
comuni-extractor analyze \
  --comune milano \
  --year 2023 \
  --drive-path "$DRIVE_PATH"

# Output:
# ✓ Processed: 18 PDFs (3 skipped as unreadable)
# ✓ Extracted: 145 fields across 2 CSV files
# ✓ Updated: bilancio_previsione_2023.csv (67 fields)
# ✓ Updated: bilancio_definitivo_2023.csv (78 fields)
# ✓ Report: Comuni/milano/2023/output/report_milano_2023.json

# 5. Verify results
cat Comuni/milano/2023/output/bilancio_definitivo_2023.csv | head -5
cat Comuni/milano/2023/output/report_milano_2023.json | jq '.stats'
```

## Readability Gating

PDFs with poor text quality (scanned documents, corrupted files) are automatically skipped before LLM calls to save API costs:

- **Minimum characters**: 100 (configurable)
- **Minimum alpha ratio**: 50% alphabetic characters (configurable)

Skipped PDFs are logged in the report with `status: "failed"` and `error: "unreadable_text"`. You can adjust thresholds in [config.yaml](config.example.yaml).

## Aggregation Priority

When multiple PDFs exist for the same field, results are aggregated with this priority:

1. **`definitivo` > `previsione`**: Definitivo budget data always wins, even with lower confidence
2. **Higher confidence**: Within same `tipo_bilancio`, highest confidence score wins
3. **All candidates preserved**: JSON report includes all extraction attempts with metadata

Example:

```json
{
  "entrate_totali": {
    "value": "1450000",
    "tipo_bilancio": "definitivo",
    "confidence_score": 0.75,
    "pdf_source": "bilancio_definitivo_2023.pdf",
    "candidates": [
      {"value": "1450000", "tipo": "definitivo", "confidence": 0.75},
      {"value": "1500000", "tipo": "previsione", "confidence": 0.95}
    ]
  }
}
```

## Output Structure

```
Comuni/<nome_comune>/<anno>/
├── pdf/                      # Downloaded PDFs
├── output/                   # Enriched CSVs + JSON report
├── cache/                    # HTTP, PDF, and LLM response caches
├── logs/                     # Run logs
└── manifest.jsonl            # File manifest
```

## Features

- 🔍 Intelligent web crawling with rate limiting and robots.txt support
- 📄 Robust PDF text extraction with readability gating
- 🧠 ChatGPT-powered structured data extraction
- 📊 Automatic CSV enrichment with validation
- 💾 Multi-layer smart caching (HTTP, PDF, LLM)
- 🛡️ Resilient error handling with circuit breakers and backoff
- 📋 Comprehensive JSON reports with confidence scores
- ⚙️ Fully configurable via YAML and environment variables

## Testing

```bash
pytest tests/ -v --cov=comuni_extractor  # Target: ≥ 85% coverage
```

## Documentation

See [config.example.yaml](config.example.yaml) for configuration options, [LICENSE](LICENSE) for licensing.

For complete documentation see the implementation plan section below.

---