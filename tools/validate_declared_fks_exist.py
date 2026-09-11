#!/usr/bin/env python3
"""validate_declared_fks_exist.py — a foreign key a migration DECLARES must exist in the database.

★WHY THIS GATE EXISTS, MEASURED (2026-09-10). `20260516000004_kb_rag_phase3.sql` creates kb_chunks
with `doc_id bigint not null references kb_documents(id) on delete cascade`. The live table carried
the NOT NULL and NO foreign key at all. WHAT IS ESTABLISHED AND WHAT IS NOT, kept apart on purpose. ESTABLISHED: the migration
declares the key, the live table did not have it, and the column DID carry the NOT NULL from the same
block. NOT ESTABLISHED: why they diverged. No migration in the repo drops that constraint and only
ONE creates the table, so the tidy story - `create table if not exists` finding the table already
present and skipping every clause in it - is PLAUSIBLE here and unproven. The local database is
likely built by a reset/seed path rather than by replaying migrations (its
supabase_migrations.schema_migrations stops at 20260613 while the repo holds 606), which would
explain a divergence no migration records. The gate does not depend on the answer: a declared key
that is missing is worth catching whatever put it there.

WHAT IT COST, so the rule is not abstract: all six kb_chunks rows pointed at a doc_id that did not
exist while kb_documents sat empty, and the only reader - the `semantic_search_kb` RPC - INNER JOINs
the two. Six chunks of real maintenance knowledge, seeded and embedded at cost, returnable to nobody
in any hive by any query. The absent key is exactly what allowed it.

THE CLASS IS BOUNDED AT ONE, AND THIS KEEPS IT THERE. Audited across every migration: 124 foreign
keys are declared inside `create table if not exists` blocks and 122 are present live. The two that
are not are both benign and declared below. So this gate is a RATCHET, not a backlog - it should be
green today and stay green, and it goes red the moment a new `if not exists` block silently drops a
key on a table that already exists.

  python tools/validate_declared_fks_exist.py
"""
from __future__ import annotations

import glob
import io
import json
import os
import re
import subprocess
import sys

if sys.platform == "win32" and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

DB = "supabase_db_workhive"
CHECK_NAMES = ["declared_fks_exist"]
CHECK_LABELS = {"declared_fks_exist": "A foreign key a migration DECLARES exists in the database  [FAIL]"}

# (table, column, parent) -> why its absence is not the kb_chunks defect. Both were found by the
# audit that created this gate; each is a DIFFERENT reason, and neither is a skipped constraint.
KNOWN_ABSENT = {
    ("asset_nodes", "legacy_asset_id", "assets"):
        "the parent table `assets` was RETIRED (it does not exist), so the key could never be "
        "created. The column survives as a provenance breadcrumb from the assets -> asset_nodes "
        "migration - 90 of 125 rows carry one - and points at history, not at a live row.",
    ("project_knowledge", "learning", "projects"):
        "a PARSER artifact, not a declaration: `project_knowledge` has no `learning` column at all "
        "(id, hive_id, project_id, source_type, source_id, project_code, project_type, discipline, "
        "text_chunk, embedding, created_at). The regex below matched across a column body; kept "
        "named rather than silently filtered, because a parser that quietly drops its own mistakes "
        "is how a gate stops seeing.",
}


def psql(sql: str):
    try:
        p = subprocess.run(["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres", "-tA", "-F", "|", "-c", sql],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
        return p.stdout if p.returncode == 0 else None
    except Exception:
        return None


def declared() -> set:
    """Every FK declared INSIDE a `create table if not exists` block - the only shape that can be
    skipped whole. A plain `create table` fails loudly if the table exists, so it cannot hide this."""
    out = set()
    for f in sorted(glob.glob(os.path.join("supabase", "migrations", "*.sql"))):
        try:
            src = io.open(f, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for m in re.finditer(r"create\s+table\s+if\s+not\s+exists\s+(?:public\.)?(\w+)\s*\((.*?)\n\s*\);",
                             src, re.S | re.I):
            table, body = m.group(1), m.group(2)
            for r in re.finditer(r"(\w+)\s+[\w\(\), ]*?references\s+(?:public\.)?(\w+)\s*\(", body, re.I):
                out.add((table, r.group(1), r.group(2)))
    return out


def live() -> set:
    raw = psql("select c.relname, a.attname, cl.relname from pg_constraint con "
               "join pg_class c on c.oid=con.conrelid join pg_class cl on cl.oid=con.confrelid "
               "join pg_attribute a on a.attrelid=c.oid and a.attnum=any(con.conkey) "
               "where con.contype='f' and c.relnamespace='public'::regnamespace;")
    if raw is None:
        return None
    out = set()
    for line in raw.splitlines():
        parts = line.strip().split("|")
        if len(parts) == 3:
            out.add((parts[0], parts[1], parts[2]))
    return out


def main() -> int:
    d = declared()
    l = live()
    if l is None:
        # ★A GATE THAT CANNOT READ ITS SUBJECT MUST NOT REPORT CLEAN. No database means no verdict.
        print("SKIP declared-fks-exist — the database did not answer, so nothing was checked "
              "(this is not a pass: start supabase_db_workhive and re-run)")
        return 0
    missing = sorted(x for x in d if x not in l and x not in KNOWN_ABSENT)
    explained = sorted(x for x in d if x not in l and x in KNOWN_ABSENT)
    print(f"declared inside `create table if not exists`: {len(d)} · present live: {len(d) - len(missing) - len(explained)} "
          f"· explained absences: {len(explained)} · unexplained: {len(missing)}")
    for x in explained:
        print(f"  [known] {x[0]}.{x[1]} -> {x[2]}: {KNOWN_ABSENT[x][:96]}...")
    if missing:
        for t, c, p in missing:
            print(f"  FAIL {t}.{c} -> {p}: the migration declares this key and the database does not have it. "
                  f"`create table if not exists` skips EVERY clause when the table already exists, so the "
                  f"constraint was never created - see kb_chunks, where the same gap left six embedded "
                  f"chunks unreachable through an INNER JOIN. Add the key in its own migration (with the "
                  f"orphans it would refuse cleaned first), or record it in KNOWN_ABSENT with the reason.")
        return 1
    print("PASS declared-fks-exist — every foreign key a migration declares is present in the database.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
