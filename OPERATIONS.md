# Operations Runbook

Backups, restores, and database migration/rollback for Aegis. Aegis stores
sensitive data (user accounts, encrypted GitHub tokens and BYOK LLM keys, scan
findings), so backups and a rehearsed restore are mandatory before launch.

## Backups

### Production (managed Postgres)
Use the provider's automated backups and point-in-time recovery (RDS
snapshots + PITR, Supabase/Cloud SQL equivalents). Set retention to your
compliance requirement (≥ 7 days to start). **Test a restore at least once** —
an untested backup is not a backup.

### Manual / local
`ops/backup/backup.sh` writes a compressed custom-format dump:

```bash
DATABASE_URL=postgresql://aegis:aegis@localhost:5432/aegis ops/backup/backup.sh
# → ops/backup/dumps/aegis-<utc-timestamp>.dump   (git-ignored)
```

Or straight from Compose:

```bash
docker compose exec -T db pg_dump -U aegis -Fc aegis > aegis-$(date -u +%Y%m%dT%H%M%SZ).dump
```

Dumps contain encrypted secrets but **not** the `ENCRYPTION_KEY` — store that
key separately (a secrets manager). A dump is useless to decrypt tokens without
it, and vice-versa.

## Restore

```bash
DATABASE_URL=postgresql://aegis:aegis@localhost:5432/aegis ops/backup/restore.sh aegis-<ts>.dump
```

`restore.sh` uses `pg_restore --clean --if-exists` — it **drops and recreates**
objects. Restore into a fresh/empty database when possible.

## Migrations

Schema changes are Alembic migrations under `backend/alembic/versions/`. The
chain is linear (single head).

**On every deploy**, after the new image is live but before it serves traffic:

```bash
alembic upgrade head          # docker compose exec api alembic upgrade head
```

**Always snapshot the database immediately before applying a migration in
production** (see Backups). Then, if a migration or the deploy is bad:

### Rollback

1. Roll the application back to the previous image/release first (a new schema
   may be incompatible with old code and vice-versa).
2. Downgrade the schema one step (or to a named revision):

   ```bash
   alembic downgrade -1
   alembic downgrade 0008_integrations   # or to a specific revision
   ```

   ⚠️ Downgrades are **destructive** where the upgrade added columns/tables —
   e.g. `0009_scan_terms` and `0008_integrations` drop columns on downgrade,
   losing that data. For anything beyond a just-applied migration, prefer
   restoring from the pre-migration backup over a blind downgrade.

3. Verify: `alembic current` should report the expected revision, and
   `/health` should return `ok`.

### Check state

```bash
alembic current      # revision the DB is at
alembic history      # full chain
alembic heads        # must be exactly one
```
