FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt* ./
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

# Install core dependencies
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    prometheus-client \
    pydantic \
    pyyaml \
    httpx

# Copy application code
COPY runtime_allocator/ ./runtime_allocator/

# Expose service port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Run the service
ENV PAPERCLIP_PORT=8080
CMD ["python", "-m", "runtime_allocator.service"]
