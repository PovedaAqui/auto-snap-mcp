# Multi-stage Dockerfile for Auto-Snap MCP Server
# Designed for deployment to Docker MCP Hub under mcp/ namespace

# Base stage - Python runtime with system dependencies
FROM python:3.12-slim as base

# Install system dependencies required for screenshot capture and OCR
RUN apt-get update && apt-get install -y \
    wmctrl \
    xdotool \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-spa \
    x11-utils \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Dependencies stage - Install Python packages
FROM base as dependencies

# Install uv for fast dependency resolution
RUN pip install --no-cache-dir uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock* ./

# Install Python dependencies
RUN uv sync --no-dev --no-cache

# Production stage - Minimal runtime image
FROM base as production

# Create non-root user for security (MCP Hub requirement)
RUN groupadd -r mcp-user && useradd -r -g mcp-user mcp-user

# Set working directory
WORKDIR /app

# Copy Python installation from dependencies stage
COPY --from=dependencies /app/.venv /app/.venv

# Make sure we use venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy application code
COPY server.py main.py capture.py processing.py pdf_utils.py config.py ./
COPY docker-entrypoint.sh ./

# Create necessary directories with proper permissions
RUN mkdir -p /app/captures /app/temp && \
    chown -R mcp-user:mcp-user /app

# Make entrypoint script executable
RUN chmod +x docker-entrypoint.sh

# Switch to non-root user
USER mcp-user

# Set default environment variables for Docker MCP Hub
ENV AUTO_SNAP_OUTPUT_DIR="/app/captures" \
    AUTO_SNAP_TEMP_DIR="/app/temp" \
    AUTO_SNAP_LEGACY_MODE="false" \
    AUTO_SNAP_AUTO_CLEANUP_TEMP="true" \
    PYTHONUNBUFFERED="1" \
    PYTHONPATH="/app"

# Health check for container orchestration
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import server; print('OK')" || exit 1

# Expose MCP server port (though MCP Hub uses STDIO transport)
EXPOSE 8000

# Use entrypoint script for dependency validation and startup
ENTRYPOINT ["./docker-entrypoint.sh"]

# Default command for MCP STDIO transport (Docker MCP Hub standard)
CMD ["python", "server.py"]