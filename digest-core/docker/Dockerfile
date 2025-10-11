FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1001 digest && \
    mkdir -p /data/out /data/.state && \
    chown -R digest:digest /data

# Switch to non-root user
USER digest

# Expose Prometheus metrics and health check ports
EXPOSE 9108 9109

# Default command
ENTRYPOINT ["python", "-m", "digest_core.cli", "run"]
CMD ["--from-date", "today", "--sources", "ews", "--out", "/data/out"]

