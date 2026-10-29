#!/usr/bin/env bash
# backup_dump.sh - BRH 9 AE (BRH515, 2026-10-29): the database backup Supabase Free does not keep.
#
# Supabase's Free plan keeps no daily backups, so nothing could bring production's rows back after a bad migration, a
# wrong delete or a lost project. This dumps the database the way Supabase documents for moving a project (roles,
# schema, data - `supabase db dump`, which leaves out Supabase's own schemas and roles), packs the three files, and
# encrypts them with a passphrase before anything leaves the machine: the repository is public, and a workflow's
# artifacts can be downloaded by anyone who can read it. It then decrypts its own output and checks every table's COPY
# block came back, so a run that uploads an unreadable file fails instead.
#
#   SUPABASE_DB_URL=...  BACKUP_PASSPHRASE=...  bash tools/backup_dump.sh <out-dir>
#
# The scheduled run is .github/workflows/backup.yml (the two values are repository secrets); the local proof that runs
# this same script against the local database is tools/prove_backup_roundtrip.py. Writes <out-dir>/workhive-db-<UTC
# stamp>.tar.gz.gpg and nothing else that outlives the run. Prints sizes and counts, never a row or the URL.
#
# Restore (into a new project or a self-hosted Supabase, per Supabase's "Restore a Platform Project" guide):
#   gpg --decrypt workhive-db-<stamp>.tar.gz.gpg | tar -xz       # asks for the passphrase
#   psql --single-transaction --variable ON_ERROR_STOP=1 --file roles.sql --file schema.sql \
#        --command 'SET session_replication_role = replica' --file data.sql --dbname "<the new database's URL>"
set -euo pipefail

out=${1:?usage: backup_dump.sh <out-dir>}
SUPABASE=${SUPABASE:-supabase}
missing=""
[ -n "${SUPABASE_DB_URL:-}" ] || missing="$missing SUPABASE_DB_URL"
[ -n "${BACKUP_PASSPHRASE:-}" ] || missing="$missing BACKUP_PASSPHRASE"
if [ -n "$missing" ]; then
  echo "::error::backup NOT taken - missing:$missing. Add them as repository secrets (Settings -> Secrets and variables -> Actions): the session pooler connection string from the project's Connect panel, and a long passphrase kept somewhere other than this repository."
  exit 1
fi
if [ "${#BACKUP_PASSPHRASE}" -lt 20 ]; then
  echo "::error::backup NOT taken - BACKUP_PASSPHRASE is shorter than 20 characters; the file is public, so the passphrase is all that protects it."
  exit 1
fi

umask 077
mkdir -p "$out"
plain=$(mktemp -d "${TMPDIR:-/tmp}/whbackup.XXXXXX")
trap 'rm -rf "$plain"' EXIT
stamp=$(date -u +%Y%m%dT%H%M%SZ)
enc="$out/workhive-db-$stamp.tar.gz.gpg"

"$SUPABASE" db dump --db-url "$SUPABASE_DB_URL" -f "$plain/roles.sql" --role-only
"$SUPABASE" db dump --db-url "$SUPABASE_DB_URL" -f "$plain/schema.sql"
"$SUPABASE" db dump --db-url "$SUPABASE_DB_URL" -f "$plain/data.sql" --use-copy --data-only

for f in roles schema data; do
  test -s "$plain/$f.sql" || { echo "::error::backup NOT taken - $f.sql came back empty"; exit 1; }
done
tables=$(grep -c '^COPY ' "$plain/data.sql" || true)
public=$(grep -c '^COPY "public"\.' "$plain/data.sql" || true)
if [ "$public" -lt 1 ]; then
  echo "::error::backup NOT taken - data.sql holds no table of the public schema"
  exit 1
fi

(cd "$plain" && tar -czf backup.tar.gz roles.sql schema.sql data.sql)   # relative: tar reads "C:" as a host
printf '%s' "$BACKUP_PASSPHRASE" | gpg --batch --yes --quiet --pinentry-mode loopback --passphrase-fd 0 \
  --symmetric --cipher-algo AES256 --output "$enc" "$plain/backup.tar.gz"

# the file that leaves is the one that must come back: decrypt it, and every COPY block must be there
back=$(printf '%s' "$BACKUP_PASSPHRASE" | gpg --batch --quiet --pinentry-mode loopback --passphrase-fd 0 \
  --decrypt "$enc" | tar -xzOf - data.sql | grep -c '^COPY ' || true)
if [ "$back" != "$tables" ]; then
  echo "::error::backup unreadable - decrypting it gave $back tables, the dump held $tables"
  rm -f "$enc"
  exit 1
fi

bytes=$(wc -c < "$enc" | tr -d ' ')
echo "backup taken: $(basename "$enc") - $bytes bytes encrypted; $tables tables ($public in public); decrypted and checked"
