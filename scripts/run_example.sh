#!/bin/bash
# Example run script

set -e

# Configuration
SITE_URL="${1:-https://www.comune.roma.it}"
YEAR="${2:-2023}"
DRIVE_PATH="${3:-./dataset_dati_comuni}"

echo "Running Comuni Extractor..."
echo "  Site: $SITE_URL"
echo "  Year: $YEAR"
echo "  Dataset: $DRIVE_PATH"
echo ""

# Run the extraction
comuni-extractor run \
    --site-url "$SITE_URL" \
    --year "$YEAR" \
    --drive-path "$DRIVE_PATH" \
    --verbose

echo ""
echo "✓ Extraction completed!"
echo "Results saved to: Comuni/"
