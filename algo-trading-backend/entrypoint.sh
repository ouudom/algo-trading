#!/usr/bin/env bash
# =============================================================================
# entrypoint.sh — AlgoTrader backend container entrypoint
# 1. Validates DATABASE_URL is set
# 2. Waits for PostgreSQL to be reachable
# 3. Runs Alembic migrations
# 4. Starts uvicorn (becomes PID 1 via exec)
# =============================================================================
set -euo pipefail

echo "[entrypoint] AlgoTrader backend starting..."
echo "[entrypoint] TRADING_MODE=${TRADING_MODE:-not set}"

# ---------------------------------------------------------------------------
# 1. Validate DATABASE_URL
# ---------------------------------------------------------------------------
DB_URL="${DATABASE_URL:-}"
if [ -z "$DB_URL" ]; then
    echo "[entrypoint] ERROR: DATABASE_URL is not set. Aborting."
    exit 1
fi

# ---------------------------------------------------------------------------
# 2. Wait for PostgreSQL
#    Parse host and port from the URL:
#    postgresql+asyncpg://user:pass@host:5432/dbname  →  host, 5432
# ---------------------------------------------------------------------------
_hostport="${DB_URL##*@}"
_host="${_hostport%%:*}"
_port="${_hostport#*:}"
_port="${_port%%/*}"

echo "[entrypoint] Waiting for PostgreSQL at ${_host}:${_port} ..."
RETRIES=30
until python -c "
import socket, sys
try:
    s = socket.create_connection(('${_host}', ${_port}), timeout=3)
    s.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null; do
    RETRIES=$((RETRIES - 1))
    if [ "$RETRIES" -le 0 ]; then
        echo "[entrypoint] ERROR: PostgreSQL not reachable after 30 attempts. Aborting."
        exit 1
    fi
    echo "[entrypoint] PostgreSQL not ready, retrying in 2s... (${RETRIES} left)"
    sleep 2
done
echo "[entrypoint] PostgreSQL is reachable."

# ---------------------------------------------------------------------------
# 3. Run Alembic migrations
#    migrations/env.py already converts asyncpg → psycopg2 DSN automatically.
# ---------------------------------------------------------------------------
echo "[entrypoint] Running Alembic migrations..."
alembic upgrade head
echo "[entrypoint] Migrations complete."

# ---------------------------------------------------------------------------
# 4. Start uvicorn
#    --workers 1: APScheduler runs inside FastAPI lifespan; multiple workers
#    would cause duplicate scheduled job execution (one scheduler per worker).
#    --proxy-headers: trust X-Forwarded-* from Nginx.
#    exec replaces the shell so uvicorn is PID 1 and receives OS signals.
# ---------------------------------------------------------------------------
echo "[entrypoint] Starting uvicorn on port 8000..."
exec uvicorn api.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1 \
    --proxy-headers \
    --forwarded-allow-ips '*' \
    --log-level "${LOG_LEVEL:-info}"
