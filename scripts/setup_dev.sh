#!/bin/bash
# Development environment setup script

set -e

echo "Setting up development environment..."

# Create virtual environment
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate || . .venv/Scripts/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip setuptools wheel

# Install dependencies
echo "Installing dependencies..."
pip install -e ".[dev]"

# Setup pre-commit hooks (optional)
if command -v pre-commit &> /dev/null; then
    echo "Installing pre-commit hooks..."
    pre-commit install
fi

echo "✓ Development environment setup complete!"
echo ""
echo "Next steps:"
echo "  1. Activate environment: source .venv/bin/activate"
echo "  2. Copy config: cp config.example.yaml config.yaml"
echo "  3. Edit config.yaml with your settings"
echo "  4. Set OPENAI_API_KEY: export OPENAI_API_KEY=sk-..."
echo "  5. Run tests: pytest tests/ -v"
echo "  6. Run CLI: comuni-extractor --help"
