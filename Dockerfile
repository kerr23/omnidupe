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
RUN useradd --create-home --shell /bin/bash --uid 1000 omnidupe

# Create a script to handle permissions
RUN echo '#!/bin/bash\n\
# Check if we can write to mounted volumes\n\
if [ -n "$INPUT_DIR" ] && [ -d "$INPUT_DIR" ]; then\n\
    if ! touch "$INPUT_DIR/.write_test" 2>/dev/null; then\n\
        echo "WARNING: No write permission to input directory $INPUT_DIR"\n\
        echo "Consider mounting with proper user permissions or using --user $(id -u):$(id -g)"\n\
    else\n\
        rm -f "$INPUT_DIR/.write_test"\n\
    fi\n\
fi\n\
\n\
if [ -n "$OUTPUT_DIR" ] && [ -d "$OUTPUT_DIR" ]; then\n\
    if ! touch "$OUTPUT_DIR/.write_test" 2>/dev/null; then\n\
        echo "ERROR: No write permission to output directory $OUTPUT_DIR"\n\
        echo "Mount with: -v /host/path:/data:Z or use --user $(id -u):$(id -g)"\n\
        exit 1\n\
    else\n\
        rm -f "$OUTPUT_DIR/.write_test"\n\
    fi\n\
fi\n\
\n\
# Execute the original command\n\
exec "$@"' > /usr/local/bin/entrypoint.sh

RUN chmod +x /usr/local/bin/entrypoint.sh

# Change ownership of app directory
RUN chown -R omnidupe:omnidupe /app /data
USER omnidupe

# Set default environment variables
ENV INPUT_DIR=/images
ENV OUTPUT_DIR=/data

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Default command
ENTRYPOINT ["/usr/local/bin/entrypoint.sh", "python", "main.py"]

# Default arguments (can be overridden)
CMD ["--help"]
