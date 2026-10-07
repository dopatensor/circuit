#!/bin/bash
# SessionStart hook for Claude Code cloud sessions.
# Prepares everything CLAUDE.md's stack needs so phases can be built and tested:
#   - Postgres 16 + PostGIS + pgvector (native; stands in for docker compose in the cloud)
#   - a "circuit" role and the circuit / circuit_test databases with both extensions
#   - Python 3.12 via uv, and backend/frontend dependencies once their manifests exist
# Idempotent: safe to run on every startup/resume.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
PG_USER=circuit
PG_PASS=circuit

log() { echo "[session-start] $*" >&2; }

# --- Postgres extensions -----------------------------------------------------
if [ ! -f /usr/share/postgresql/16/extension/postgis.control ] || \
   [ ! -f /usr/share/postgresql/16/extension/vector.control ]; then
  log "installing PostGIS + pgvector"
  apt-get update -qq >/dev/null 2>&1 || true
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    postgresql-16-postgis-3 postgresql-16-pgvector >/dev/null
fi

# --- Start Postgres ----------------------------------------------------------
if ! pg_isready -q -h localhost -p 5432; then
  log "starting postgres"
  service postgresql start >/dev/null 2>&1 || pg_ctlcluster 16 main start
  for _ in $(seq 1 30); do pg_isready -q -h localhost -p 5432 && break; sleep 1; done
fi

psql_su() { su postgres -c "psql -v ON_ERROR_STOP=1 -qAt -c \"SET client_min_messages=warning\" $*"; }

if [ "$(psql_su "-c \"SELECT 1 FROM pg_roles WHERE rolname='$PG_USER'\"")" != "1" ]; then
  psql_su "-c \"CREATE ROLE $PG_USER LOGIN SUPERUSER PASSWORD '$PG_PASS'\""
fi
for db in circuit circuit_test; do
  if [ "$(psql_su "-c \"SELECT 1 FROM pg_database WHERE datname='$db'\"")" != "1" ]; then
    psql_su "-c \"CREATE DATABASE $db OWNER $PG_USER\""
  fi
  psql_su "-d $db -c \"CREATE EXTENSION IF NOT EXISTS postgis; CREATE EXTENSION IF NOT EXISTS vector;\""
done

# --- Python 3.12 + backend deps ---------------------------------------------
uv python install 3.12 >/dev/null 2>&1 || true
if [ -f "$PROJECT_DIR/backend/pyproject.toml" ]; then
  log "uv sync (backend)"
  (cd "$PROJECT_DIR/backend" && uv sync --python 3.12)
fi

# --- Frontend deps -----------------------------------------------------------
if [ -f "$PROJECT_DIR/frontend/package.json" ]; then
  log "npm install (frontend)"
  (cd "$PROJECT_DIR/frontend" && npm install --no-audit --no-fund)
fi

# --- Session env -------------------------------------------------------------
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  {
    echo "export DATABASE_URL=postgresql+psycopg://$PG_USER:$PG_PASS@localhost:5432/circuit"
    echo "export TEST_DATABASE_URL=postgresql+psycopg://$PG_USER:$PG_PASS@localhost:5432/circuit_test"
    echo "export UV_PYTHON=3.12"
  } >> "$CLAUDE_ENV_FILE"
fi

log "ready"
