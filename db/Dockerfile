# Postgres 16 + PostGIS + pgvector.
# The official postgres:16 image is multi-arch (amd64 + arm64) and already has the
# PGDG apt repo configured, which publishes both extensions for amd64 and arm64.
FROM postgres:16

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      postgresql-16-postgis-3 \
      postgresql-16-pgvector \
 && rm -rf /var/lib/apt/lists/*

# Scripts here run once, the first time the data volume is initialised.
COPY init/ /docker-entrypoint-initdb.d/
