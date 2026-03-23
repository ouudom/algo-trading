# =============================================================================
# AlgoTrader Backend — Production Dockerfile
# Python 3.12 slim + TA-Lib C library built from source
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Build TA-Lib C library + compile Python wheels
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    tar \
    gcc \
    g++ \
    make \
    libpq-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Build TA-Lib 0.4.0 C library from source.
# The Python TA-Lib pip package is a wrapper around this C lib and requires
# it to be installed system-wide before the Python wheel can be compiled.
WORKDIR /tmp/ta-lib-build
RUN wget -q https://github.com/TA-Lib/ta-lib/releases/download/v0.4.0/ta-lib-0.4.0-src.tar.gz \
    && tar -xzf ta-lib-0.4.0-src.tar.gz \
    && cd ta-lib-0.4.0 \
    && ./configure --prefix=/usr/local \
    && make -j"$(nproc)" \
    && make install \
    && ldconfig \
    && cd /tmp && rm -rf ta-lib-build

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
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy compiled TA-Lib shared library from builder
COPY --from=builder /usr/local/lib/libta_lib* /usr/local/lib/
COPY --from=builder /usr/local/include/ta-lib /usr/local/include/ta-lib
RUN ldconfig

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
