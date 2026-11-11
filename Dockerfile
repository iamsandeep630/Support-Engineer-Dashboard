# ==============================================================================
# Dockerfile for Support Engineer Dashboard
# Production-ready container image for deployment to AWS ECS Fargate / EC2
# Hosts Jira Ticket Synchronization & SmartFix Two-Stage HITL Agent
# ==============================================================================

FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend \
    HOST=0.0.0.0 \
    SUPPORT_PORT=8002

# Set working directory
WORKDIR /app

# Install system dependencies including Node.js & npm for GitHub MCP server runner
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    nodejs \
    npm \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies with CPU-optimized PyTorch
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Copy application backend and frontend
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Expose FastAPI port
EXPOSE 8002

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8002/health || exit 1

# Start FastAPI application with uvicorn
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8002"]

