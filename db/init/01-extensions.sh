#!/bin/bash
# Runs once on first start of an empty data volume.
# Creates the test database and enables PostGIS + pgvector in both databases.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
CREATE DATABASE ${POSTGRES_DB}_test OWNER "$POSTGRES_USER";
SQL

for db in "$POSTGRES_DB" "${POSTGRES_DB}_test"; do
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$db" <<SQL
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;
SQL
done
