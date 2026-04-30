# Use a multi-stage build to reduce the final image size
FROM python:3.11-slim AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install build dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY requirements.txt pyproject.toml ./

# Install Python dependencies
RUN pip install --upgrade pip \
    && pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# Final runtime image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    WEB_CONCURRENCY=2 \
    GUNICORN_TIMEOUT=180 \
    PAGEINDEX_SECTIONS_JSON=/app/data/ingestion/sec/extracted_10k_sections.json \
    PAGEINDEX_DOCS_DIR=/app/data/pageindex/docs \
    PAGEINDEX_WORKSPACE_DIR=/app/data/pageindex/workspace \
    PAGEINDEX_OUTPUT_DIR=/app/data/pageindex/output \
    OBSERVABILITY_DIR=/app/data/observability \
    ALERT_EVENT_LOG=/app/data/observability/alerts.jsonl

WORKDIR /app

# Install runtime dependencies
COPY --from=builder /app/wheels /wheels
RUN pip install --no-cache /wheels/* \
    && rm -rf /wheels

# Copy application files
COPY backend ./backend
COPY data/ingestion/sec/extracted_10k_sections.json ./data/ingestion/sec/extracted_10k_sections.json

# Create necessary directories and set permissions
RUN mkdir -p /app/data/pageindex/docs \
    /app/data/pageindex/workspace \
    /app/data/pageindex/output \
    /app/data/observability \
    /app/data/ingestion/sec \
    && chmod +x /app/backend/startup.sh \
    && adduser --disabled-password --gecos "" appuser \
    && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose the application port
EXPOSE 8000

# Set the entrypoint command
CMD ["sh", "backend/startup.sh"]
