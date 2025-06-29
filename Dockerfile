# Use Python 3.11 slim image for smaller size
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .
COPY src/ src/

# Create data directory for outputs
RUN mkdir -p /data

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash omnidupe
RUN chown -R omnidupe:omnidupe /app /data
USER omnidupe

# Set default environment variables
ENV INPUT_DIR=/images
ENV OUTPUT_DIR=/data

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Default command
ENTRYPOINT ["python", "main.py"]

# Default arguments (can be overridden)
CMD ["--help"]
