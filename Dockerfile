# syntax=docker/dockerfile:1
# Multi-stage Dockerfile for yt-dlp REST API
# Implements requirements 32 (container security) and 41 (Docker containerization)

# =============================================================================
# Stage 1: Builder - Install Python dependencies
# =============================================================================
FROM python:3.14-slim AS builder

# Set build arguments
ARG PIP_NO_CACHE_DIR=1
ARG PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install to user local (including yt-dlp)
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt yt-dlp

# =============================================================================
# Stage 2: Runtime - Minimal production image
# =============================================================================
FROM python:3.14-slim AS runtime

# Labels for container metadata
LABEL maintainer="yt-dlp-api" \
      description="REST API for video downloads using yt-dlp" \
      version="0.1.0"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/home/appuser/.local/bin:$PATH" \
    # Application defaults (can be overridden)
    APP_SERVER_HOST=0.0.0.0 \
    APP_SERVER_PORT=8000

WORKDIR /app

# Install runtime dependencies:
# - ffmpeg: Audio/video processing
# - nodejs: JavaScript runtime for yt-dlp challenge resolution (>= 20)
# - curl: Health check
# Node.js 20+ from NodeSource
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    gnupg \
    ca-certificates \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /etc/apt/keyrings/nodesource.gpg /etc/apt/sources.list.d/nodesource.list

# Create non-root user (UID 1000) for security (Req 32)
RUN useradd --create-home --uid 1000 --shell /bin/bash appuser

# Copy Python dependencies from builder (includes yt-dlp)
COPY --from=builder /root/.local /home/appuser/.local

# Create application directories with correct ownership
# These directories will be used as mount points or for runtime data
RUN mkdir -p /app/downloads /app/cookies /app/logs \
    && chown -R appuser:appuser /app

# Copy application code with correct ownership
# Using --chown to ensure files are owned by appuser
# Note: config.yaml is NOT copied - it must be mounted at runtime to avoid
# baking secrets into image layers (security best practice)
COPY --chown=appuser:appuser app/ /app/app/
COPY --chown=appuser:appuser requirements.txt /app/requirements.txt

# Switch to non-root user (Req 32)
USER appuser

# Health check configuration (Req 41)
# Checks the /health endpoint every 30 seconds
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl --fail http://localhost:${APP_SERVER_PORT}/health || exit 1

# Expose the API port (default 8000)
EXPOSE 8000

# Run the application
# Using shell form with exec for variable substitution and proper signal handling
CMD exec python -m uvicorn app.main:app --host $APP_SERVER_HOST --port $APP_SERVER_PORT
