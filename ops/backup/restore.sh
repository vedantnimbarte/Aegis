#!/usr/bin/env bash
# Restore an Aegis Postgres dump produced by backup.sh. DESTRUCTIVE: --clean
# drops existing objects first.
#
#   DATABASE_URL=postgresql://aegis:aegis@localhost:5432/aegis ./restore.sh aegis-<ts>.dump
set -euo pipefail

URL="${DATABASE_URL:?set DATABASE_URL (postgresql://user:pass@host:port/db)}"
URL="${URL/+psycopg/}"
DUMP="${1:?usage: restore.sh <dump-file>}"

[ -f "$DUMP" ] || { echo "No such dump: $DUMP" >&2; exit 1; }

pg_restore --clean --if-exists --no-owner --dbname="$URL" "$DUMP"
echo "Restored $DUMP"
