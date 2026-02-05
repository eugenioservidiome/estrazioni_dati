FROM python:3.12-slim-bullseye

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml LICENSE README.md ./
COPY comuni_extractor/ ./comuni_extractor/

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Create data directories
RUN mkdir -p /app/Comuni /app/dataset_dati_comuni /app/cache

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO

# Default command
ENTRYPOINT ["comuni-extractor"]
CMD ["--help"]
