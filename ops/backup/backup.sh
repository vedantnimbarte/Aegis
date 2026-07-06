#!/usr/bin/env bash
# Dump the Aegis Postgres database to a timestamped custom-format file.
#
#   DATABASE_URL=postgresql://aegis:aegis@localhost:5432/aegis ./backup.sh [out_dir]
#
# In Docker Compose:
#   docker compose exec -T db pg_dump -U aegis -Fc aegis > aegis-$(date -u +%Y%m%dT%H%M%SZ).dump
set -euo pipefail

URL="${DATABASE_URL:?set DATABASE_URL (postgresql://user:pass@host:port/db)}"
# pg_dump wants a plain libpq URL, not SQLAlchemy's +driver suffix.
URL="${URL/+psycopg/}"

OUT_DIR="${1:-$(dirname "$0")/dumps}"
mkdir -p "$OUT_DIR"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$OUT_DIR/aegis-$TS.dump"

pg_dump --format=custom --no-owner --dbname="$URL" --file="$OUT"
echo "Wrote $OUT ($(du -h "$OUT" | cut -f1))"
