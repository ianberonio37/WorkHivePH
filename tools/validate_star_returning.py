#!/usr/bin/env python3
"""validate_star_returning.py - a bare .select() after a write is `select *`, and a star RETURNING
on a table with a column-level SELECT revoke fails with 42501 *after the row has already committed*.

FOUND LIVE 2026-07-29. `project-manager.html` ended both create paths with
`.insert(payload).select().single()`. `projects.budget_php` is supervisor-only (SELECT revoked, migs
024/030), so PostgREST answered `42501 permission denied for table projects`, the page said
"Create failed" - and the project was created anyway. A phantom create: orphan row, no scope items, and
a message inviting a retry that makes another one. The prior arc had fixed the READ path on that same
page and missed both write-RETURNING paths.

WHAT THIS GATE ASSERTS
  FAIL - a client write on a table that HAS a SELECT-revoked column returns a bare/star `.select()`.
  WARN - a bare/star `.select()` after a write on any other table: correct today, but it becomes the
         bug above the moment someone revokes a column on that table. Named so the debt is visible.

Reads the grant catalog LIVE rather than hardcoding the table list, so a future revoke arms the check
automatically. Infra absent => SKIP (exit 0), never a false FAIL.
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GREEN, RED, YEL, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[0m"

# Backup/mirror trees are not served; scanning them reports bugs that cannot be hit.
SKIP_DIRS = {".emoji_bak", ".hexvar_bak", "node_modules", ".git", "test-data-seeder", "substrate"}

REVOKED_SQL = """
select c.table_name || '|' || string_agg(c.column_name, ',')
from information_schema.columns c
join pg_class pc on pc.relname = c.table_name
 and pc.relnamespace = 'public'::regnamespace and pc.relkind = 'r'
where c.table_schema = 'public'
  and exists (select 1 from information_schema.role_column_grants g
               where g.grantee = 'authenticated' and g.table_name = c.table_name
                 and g.privilege_type = 'SELECT')
  and not exists (select 1 from information_schema.role_column_grants g
               where g.grantee = 'authenticated' and g.table_name = c.table_name
                 and g.column_name = c.column_name and g.privilege_type = 'SELECT')
group by c.table_name;
"""

MUTATION = re.compile(r"\.(insert|update|upsert|delete)\s*\(")
# a RETURNING that asks for everything: .select()  |  .select('*')  |  .select("*")
STAR_SELECT = re.compile(r"\.select\(\s*(\)|['\"]\s*\*\s*['\"]\s*\))")
FROM_TABLE = re.compile(r"\.from\(\s*['\"]([A-Za-z0-9_]+)['\"]\s*\)")


def revoked_tables():
    """{table: [cols]} for tables with at least one SELECT-revoked column. None if psql is unreachable."""
    try:
        r = subprocess.run(
            ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
             "-t", "-A", "-c", REVOKED_SQL],
            capture_output=True, text=True, timeout=60)
    except Exception:
        return None
    if r.returncode != 0:
        return None
    out = {}
    for line in (r.stdout or "").splitlines():
        line = line.strip()
        if "|" in line:
            t, cols = line.split("|", 1)
            out[t.strip()] = [c.strip() for c in cols.split(",") if c.strip()]
    return out


def scan_file(path, window=12):
    """Yield (line_no, table, snippet) for every write whose RETURNING is a star.

    Line-window based rather than one big regex: a supabase-js chain is written across several lines and
    a greedy multiline pattern happily bridges two unrelated statements.
    """
    try:
        lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    except Exception:
        return
    for i, line in enumerate(lines):
        m = FROM_TABLE.search(line)
        if not m:
            continue
        chunk = "\n".join(lines[i:i + window])
        # Stop at the NEXT .from( so one statement's window cannot swallow the following one. The match
        # is on lines[i], which is the head of chunk, so m.end() is already the right offset into chunk.
        nxt = FROM_TABLE.search(chunk, m.end())
        if nxt:
            chunk = chunk[: nxt.start()]
        if not STAR_SELECT.search(chunk):
            continue
        # A star READ on a column-revoked table 42501s exactly the same way; it is only less damaging
        # because nothing was written. Both kinds FAIL on a revoked table (below); only writes are worth
        # naming as latent debt, since `select('*')` on an unrestricted table is ordinary and harmless.
        yield i + 1, m.group(1), ("write" if MUTATION.search(chunk) else "read"), line.strip()[:90]


def main():
    print("=" * 72)
    print("  Star RETURNING on a column-revoked table (phantom-write class)")
    print("=" * 72)

    revoked = revoked_tables()
    if revoked is None:
        print("  SKIP: docker/psql unavailable - cannot read the grant catalog")
        return 0
    print(f"  tables with a SELECT-revoked column: "
          f"{', '.join(f'{t}({len(c)})' for t, c in sorted(revoked.items())) or 'none'}")

    fails, warns = [], []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        # Every dot-dir here is a backup/tooling mirror (.emoji_bak, .leftover_bak, .palette_bak,
        # .hexvar_bak, .playwright-mcp, .git). None of them is served, so a finding in one is noise.
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            if not fn.endswith(".html"):
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, ROOT).replace("\\", "/")
            for line_no, table, kind, snippet in scan_file(p):
                rec = (rel, line_no, table, kind, snippet)
                if table in revoked:
                    fails.append(rec)
                elif kind == "write":
                    warns.append(rec)

    for rel, line_no, table, kind, snippet in fails:
        cols = ", ".join(revoked[table])
        print(f"  {RED}FAIL{RESET}  {rel}:{line_no} - {kind} on `{table}` uses `select *`, "
              f"but SELECT is revoked on: {cols}")
        if kind == "write":
            print("          the INSERT commits and the RETURNING 42501s -> PHANTOM WRITE "
                  "(user sees a failure, the row is there). Name the columns you consume: .select('id')")
        else:
            print("          the read 42501s outright. Name the columns you consume.")
    for rel, line_no, table, _kind, _ in warns:
        print(f"  {YEL}WARN{RESET}  {rel}:{line_no} - bare `.select()` after a write on `{table}` "
              f"(fine today; becomes a phantom write if any column on it is ever SELECT-revoked)")

    print()
    if fails:
        nw = sum(1 for f in fails if f[3] == "write")
        print(f"{RED}FAIL{RESET} - {len(fails)} star-select site(s) on a column-revoked table "
              f"({nw} write / {len(fails) - nw} read) | {len(warns)} latent")
        return 1
    print(f"{GREEN}PASS{RESET} - 0 star-select reads or writes on the {len(revoked)} column-revoked "
          f"table(s) | {len(warns)} latent bare-select write(s) named above")
    return 0


if __name__ == "__main__":
    sys.exit(main())
