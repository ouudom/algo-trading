# =============================================================================
# AlgoTrader Backend — Production Dockerfile
# Python 3.12 slim + TA-Lib via apt (no source compile)
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Install Python wheels
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    libpq-dev \
    python3-dev \
    libta-lib-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies into an isolated prefix so they can be
# cleanly copied into the slim runtime stage without any build tools.
WORKDIR /build
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --prefix=/install --no-warn-script-location -r requirements.txt

# ---------------------------------------------------------------------------
# Stage 2: Production runtime image
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# Runtime libraries only — no build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    libpq5 \
    libta-lib0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/src

WORKDIR /app

COPY . .

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Run as non-root user
RUN useradd --create-home --shell /bin/bash algotrader \
    && chown -R algotrader:algotrader /app
USER algotrader

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]