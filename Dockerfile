# Multi-stage build for COORDINATE-2.0
# Stage 1: Build React frontend
FROM node:22-alpine AS frontend-builder

WORKDIR /app/ui

# Copy package files
COPY ui/package*.json ./

# Install dependencies (including devDependencies needed for build)
RUN npm ci

# Copy UI source
COPY ui/ ./

# Build the React app
RUN npm run build

# Stage 2: Build the Linux RTLola CLI required by Dynamic Adaptation.
FROM rust:1.88-slim-bookworm AS rtlola-builder

RUN cargo install rtlola-cli --version 0.1.2 --root /opt/rtlola

# Stage 3: Production image with Python backend
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy Python requirements
COPY requirements.txt requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend ./backend
COPY sim ./sim
COPY spec2.rtlola ./spec2.rtlola

# Keep the monitor binary in PATH inside the Linux container.
COPY --from=rtlola-builder /opt/rtlola/bin/rtlola-cli /usr/local/bin/rtlola-cli

# Create necessary directories
RUN mkdir -p results configuration bench_config test_config


# Copy built frontend from stage 1
COPY --from=frontend-builder /app/ui/dist ./ui/dist

# Expose port
EXPOSE 5002

# Set environment variables
ENV FLASK_APP=backend.app
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5002/api/topologies')" || exit 1

# Run the Flask application
CMD ["python", "-m", "backend.app"]
